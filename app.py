import os
import streamlit as st
import pandas as pd
import json
from docx import Document
from youtube_summarizer import summarize_youtube_video
from document_summarizer import generate_summary_from_file
from video_summarizer import get_summary_from_video
from datetime import datetime
from openai import OpenAI
import re
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from tavily import TavilyClient
from youtube_fetch import main as youtube_main
from reddit_fetch import main as reddit_main
from urls_fetch import main as urls_main
from gpt import main as gpt_main
from claude import main as claude_main
from dotenv import load_dotenv
import tempfile
import shutil

load_dotenv()
# Configuration
os.environ["STREAMLIT_WATCH_USE_POLLING"] = "true"

# API Keys and Clients
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

uploaded_filenames = []

# Helper Functions for Summary Generator
def add_formatted_run(paragraph, text):
    pattern = re.compile(r'(\*\*.*?\*\*|\*.*?\*\*)')
    pos = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if pos < start:
            paragraph.add_run(text[pos:start])
        matched_text = match.group()
        cleaned_text = matched_text.strip('*')
        run = paragraph.add_run(cleaned_text)
        run.bold = True
        pos = end
    if pos < len(text):
        paragraph.add_run(text[pos:])

def write_to_word(text, output_file="generated_summary.docx"):
    doc = Document()
    title = doc.add_heading("Generated Topic-Wise Study Plan", level=1)
    title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("### "):
            doc.add_heading(line[4:], level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif re.match(r"^Chapter \d+: ", line, re.IGNORECASE):
            doc.add_heading(line, level=2)
        elif line.startswith(("-", "*", "•")):
            p = doc.add_paragraph(style="List Bullet")
            add_formatted_run(p, line[1:].strip())
        elif re.match(r"^\d+\.", line):
            p = doc.add_paragraph(style="List Number")
            add_formatted_run(p, line.strip())
        else:
            p = doc.add_paragraph()
            add_formatted_run(p, line)

    doc.save(output_file)

# Helper Functions for Study Plan Generator
def search_and_extract(prompt, category, include_domains=None, exclude_domains=None):
    max_result = 10  # Limit to 10 results
    if category == "YouTube Videos":
        max_result = 5

    response = tavily_client.search(
        query=prompt,
        search_depth="advanced",
        max_results=max_result,
        include_answer='advanced',
        include_raw_content=False,
        include_images=False,
        include_domains=include_domains,
        exclude_domains=exclude_domains
    )
    return [{"category": category, "url": r["url"]} for r in response.get("results", [])],response.get("answer", "")

# App Configuration
st.set_page_config(page_title="Smart Academic Assistant", layout="centered")

# Main App Title and Feature Selection
st.title("🎓 Smart Academic Assistant")
st.markdown("Choose between generating summaries from videos/documents or creating study plans for certifications.")

# Feature Toggle
feature_choice = st.radio(
    "Select Feature:",
    ["📝 Summary Generator", "🎯 Study Plan Generator"],
    horizontal=True
)

st.divider()

# FEATURE 1: SUMMARY GENERATOR
if feature_choice == "📝 Summary Generator":
    st.title("🎥 Smart Summary Generator")
    st.markdown("Start by uploading video files to generate summaries. Optionally, you can also add YouTube URLs and documents.")

    # Initialize session state for summary generator
    if "summary_generated" not in st.session_state:
        st.session_state.summary_generated = False
    if "summary_path" not in st.session_state:
        st.session_state.summary_path = ""
    if "timestamp" not in st.session_state:
        st.session_state.timestamp = ""
    
    # Clear study plan session states when in summary mode
    if "search_results" in st.session_state:
        del st.session_state["search_results"]
    if "answers" in st.session_state:
        del st.session_state["answers"]

    # === Primary Input: Video Upload ===
    st.subheader("🎥 Upload Video Files")
    video_files = st.file_uploader("Upload videos", type=["mp4", "mov", "avi"], accept_multiple_files=True)

    # === Optional Input: YouTube URLs ===
    use_youtube = st.checkbox("📺 I want to add YouTube Video URLs")
    youtube_urls = []
    if use_youtube:
        st.subheader("📺 YouTube Video URLs")
        youtube_input = st.text_area("Enter one YouTube URL per line", placeholder="https://www.youtube.com/watch?v=...")
        youtube_urls = youtube_input.strip().splitlines()

    # === Optional Input: Document Upload ===
    use_docs = st.checkbox("📄 I want to upload documents (PDF/DOCX)")
    document_files = []
    if use_docs:
        st.subheader("📄 Upload Document Files")
        document_files = st.file_uploader("Upload documents", type=["pdf", "docx"], accept_multiple_files=True)

    # === Generate Summaries ===
    if st.button("🚀 Generate Summary"):
        doc = Document()
        doc.add_heading("Merged Summaries", level=1)
        added_any_summary = False
        temp_files_to_cleanup = []

        # Create temporary directory for this session
        temp_dir = tempfile.mkdtemp()
        temp_files_to_cleanup.append(temp_dir)

        try:
            for video_file in video_files:
                # Create temporary file for video
                temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{video_file.name}", dir=temp_dir)
                temp_video.write(video_file.read())
                temp_video.close()
                temp_files_to_cleanup.append(temp_video.name)
                
                st.write(f"🔄 Generating summary for video: {video_file.name}")
                summary = get_summary_from_video(temp_video.name)
                if summary:
                    doc.add_heading("Video File Summary", level=2)
                    doc.add_heading(f"File: {video_file.name}", level=2)
                    doc.add_paragraph(summary)
                    added_any_summary = True
                    st.success(f"✔ Summary added for video: {video_file.name}")
                else:
                    st.warning(f"⚠ No summary generated for video: {video_file.name}")

            count = 1
            for url in youtube_urls:
                if url.strip():
                    st.write(f"🔄 Generating summary for YouTube URL-{count}")
                    summary = summarize_youtube_video(url)
                    if summary:
                        doc.add_heading("YouTube Video Summary", level=2)
                        doc.add_heading(f"URL: {url}", level=2)
                        doc.add_paragraph(summary)
                        added_any_summary = True
                        st.success(f"✔ Summary added for: URL-{count}")
                        count += 1
                    else:
                        st.warning(f"⚠ No summary for: {url}")

            for doc_file in document_files:
                # Create temporary file for document
                temp_doc = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{doc_file.name}", dir=temp_dir)
                temp_doc.write(doc_file.read())
                temp_doc.close()
                temp_files_to_cleanup.append(temp_doc.name)
                
                st.write(f"🔄 Generating summary for document: {doc_file.name}")
                summary = generate_summary_from_file(temp_doc.name)
                if summary:
                    doc.add_heading("Document Summary", level=2)
                    doc.add_heading(f"File: {doc_file.name}", level=2)
                    doc.add_paragraph(summary)
                    added_any_summary = True
                    st.success(f"✔ Summary added for document: {doc_file.name}")
                else:
                    st.warning(f"⚠ No summary generated for document: {doc_file.name}")

            if added_any_summary:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Create temporary file for output
                temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=f"_merged_summary_{timestamp}.docx", dir=temp_dir)
                temp_output.close()
                doc.save(temp_output.name)
                temp_files_to_cleanup.append(temp_output.name)

                # Store in session state
                st.session_state.summary_generated = True
                st.session_state.summary_path = temp_output.name
                st.session_state.timestamp = timestamp

                with open(temp_output.name, "rb") as f:
                    st.download_button(
                        label="📥 Download Original Summary",
                        data=f,
                        file_name="Generated_summary.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                st.success("✅ Summary generation complete!")

        finally:
            # Clean up temporary files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.isfile(temp_file):
                        os.remove(temp_file)
                    elif os.path.isdir(temp_file):
                        shutil.rmtree(temp_file)
                except Exception as e:
                    st.warning(f"⚠ Error cleaning up temporary file {temp_file}: {e}")

    # === GPT Reformatting ===
    if st.session_state.summary_generated:
        st.subheader("✨ Enhance Summary with GPT")
        if st.button("🔄 Reformat Using GPT"):
            with st.spinner("🧠 GPT is processing and enhancing the summary..."):
                try:
                    with open(st.session_state.summary_path, "rb") as f:
                        docx_file = Document(f)
                        full_text = "\n".join([para.text for para in docx_file.paragraphs if para.text.strip()])

                    if not full_text.strip():
                        st.error("❌ Summary content is empty. Cannot process.")
                    else:
                        prompt = f"""
You are a professional tutor who has reviewed multiple video lecture summaries on the same topic. Your task is to:

1. Understand the key ideas across all summaries.
2. Identify repeated concepts, unique insights, and any contradictions or differences in explanations.
- Clearly explain what the differences are and why they might exist.
3 Generate a comprehensive, structured explanation that covers all aspects of the topic.

Then merge all summaries into one well-structured explanation.

Organize the explanation like a tutor would:
- Start with Basics (definitions, foundations)
- Then Intermediate Concepts (examples, applications)
- Then Advanced Insights (expert-level analysis, edge cases)

Make the explanation easy to follow, detailed, and educational — like you're teaching a student who wants to fully understand the topic.

Here are the summaries:
{full_text}
"""

                        response = client.chat.completions.create(
                            model="gpt-4.1-mini",
                            messages=[
                                {"role": "system", "content": "You are an expert summarizer and tutor."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.5
                        )

                        formatted_content = response.choices[0].message.content.strip()
                        
                        # Create temporary file for GPT output
                        temp_gpt = tempfile.NamedTemporaryFile(delete=False, suffix="_enhanced_summary.docx")
                        temp_gpt.close()
                        
                        write_to_word(formatted_content, temp_gpt.name)

                        with open(temp_gpt.name, "rb") as f:
                            st.download_button(
                                label="📥 Download GPT-Enhanced Summary",
                                data=f,
                                file_name="Formatted_summary.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                        st.success("✅ GPT-enhanced summary is ready!")

                        # Clean up temporary GPT file
                        try:
                            os.remove(temp_gpt.name)
                        except Exception as e:
                            st.warning(f"⚠ Error cleaning up temporary GPT file: {e}")
                        
                        st.info("🧹 Temporary files have been cleaned up.")
                        
                except Exception as e:
                    st.error(f"❌ GPT API Error: {e}")

# FEATURE 2: STUDY PLAN GENERATOR
elif feature_choice == "🎯 Study Plan Generator":
    st.title("🎓 Certification Resource Finder")

    # Initialize session state for study plan generator
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    
    # Clear summary session states when in study plan mode
    if "summary_generated" in st.session_state:
        st.session_state.summary_generated = False
    if "summary_path" in st.session_state:
        st.session_state.summary_path = ""
    if "timestamp" in st.session_state:
        st.session_state.timestamp = ""

    # Input field for certificate/topic
    user_input = st.text_input("Enter the certification or topic name", placeholder="e.g., PMI-PBA")

    # Tavily search
    if st.button("Search Resources") and user_input:
        with st.spinner("Searching..."):
            all_results = []

            yt_prompt = f'Search YouTube for the most popular {user_input} exam preparation guides videos in English. Include only direct video URLs to study guides,Preparation tips and exam walkthroughs. Do not include playlists or channel links'
            yt_urls, yt_answer = search_and_extract(yt_prompt, "YouTube Videos", include_domains=["youtube.com"])
            all_results += yt_urls

            reddit_prompt = f'Find the Reddit posts discussing preparation strategies, shared experiences, focus areas, and recommended resources for the {user_input} exam.'
            reddit_urls, reddit_answer = search_and_extract(reddit_prompt, "Reddit Posts", include_domains=["reddit.com"])
            all_results += reddit_urls

            web_prompt = f'Search for top-quality official guides, detailed articles, books, and preparation resources for the {user_input} exam in English. Focus on the best study plans, exam strategies, syllabus breakdown, difficulty level, and expert advice from certified professionals. Provide direct links only.'
            
            web_urls, web_answer = search_and_extract(web_prompt, "Web Resources", exclude_domains=["youtube.com", "reddit.com"])
            all_results += web_urls

            st.session_state["answers"] = {
                "web": web_answer
            }

            df = pd.DataFrame(all_results)
            st.session_state["search_results"] = df

    # Display results
    if "search_results" in st.session_state:
        st.subheader("🔗 Tavily Search Results")
        df = st.session_state["search_results"]
        for category in df["category"].unique():
            st.markdown(f"**{category}**")
            for _, row in df[df["category"] == category].iterrows():
                st.markdown(f"- [{row['url']}]({row['url']})")

        st.divider()
        st.subheader("➕ Add More Links Manually (comma-separated)")

        # Text areas for additional links
        more_youtube = st.text_area("More YouTube Links", placeholder="https://youtube.com/xyz1, https://youtube.com/xyz2")
        more_reddit = st.text_area("More Reddit Links", placeholder="https://reddit.com/abc1, https://reddit.com/abc2")
        more_other = st.text_area("More Other Links", placeholder="https://example.com/article1, https://blog.com/post2")

        # File Upload
        st.divider()
        st.subheader("📤 Upload Supporting Files")
        files = st.file_uploader("Upload PDF or DOCX files", type=["pdf", "docx"], accept_multiple_files=True)

        if files:
            os.makedirs("data", exist_ok=True)

            for f in files:
                file_path = os.path.join("data", f.name)
                with open(file_path, "wb") as out_file:
                    out_file.write(f.read())
                uploaded_filenames.append(f.name)
                st.markdown(f"- ✅ Saved: `{file_path}`")

            st.session_state.uploaded_files = uploaded_filenames

        # Submit and Save
        st.divider()
        if st.button("✅ Submit and Save JSON"):
            # Combine Tavily + manual
            def parse_links(text): return [url.strip() for url in text.split(",") if url.strip()]
            final_data = {
                "youtube": [*df[df["category"] == "YouTube Videos"]["url"].tolist()] + parse_links(more_youtube),
                "reddit": [*df[df["category"] == "Reddit Posts"]["url"].tolist()] + parse_links(more_reddit),
                "other": [*df[df["category"] == "Web Resources"]["url"].tolist()] + parse_links(more_other),
                "files": st.session_state.uploaded_files,
                "answers": st.session_state["answers"]  # Add this line
            }

            # ---- Run the fetchers after saving ----
            st.divider()
            st.subheader("🚀 Running Data Fetch Modules")

            # Ensure folders exist
            os.makedirs("logs", exist_ok=True)
            os.makedirs("data", exist_ok=True)

            # Call YouTube Fetch
            st.write("▶️ Running YouTube transcript fetcher...")
            youtube_main(final_data["youtube"])

            # Call Reddit Fetch
            st.write("▶️ Running Reddit post fetcher...")
            reddit_main(final_data["reddit"])

            # Call Tavily Web Extractor
            st.write("▶️ Running Webpage text extractor...")
            urls_main(final_data["other"],final_data["answers"]["web"])

            st.write("🧠 Generating topic insights with GPT...")
            gpt_main(certificate_name=user_input)
            
            # === Run CLAUDE.py ===
            st.write("📚 Generating final study plan with Claude...")
            claude_main(certificate_name=user_input)

            # Final Output Info
            st.success("📝 Study Plan Generated: `generated_study_plan.docx`")

        # Placeholder for future output
        st.subheader("📦 Final Output")

        docx_path = "generated_study_plan.docx"
        if os.path.exists(docx_path):
            with open(docx_path, "rb") as docx_file:
                st.download_button(
                    label="📥 Download Study Plan (DOCX)",
                    data=docx_file,
                    file_name="study_plan.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )