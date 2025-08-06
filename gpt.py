import os
import fitz  # PyMuPDF
import docx
from openai import OpenAI
from docx import Document
import sys
import re
import tiktoken
import time
from dotenv import load_dotenv

load_dotenv()
# === Save formatted Word document ===
def save_to_word(content, filename="gpt_study_plan.docx"):
    doc = Document()
    doc.add_heading("Study Plan", level=0)

    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        elif line.startswith("### ") or line.startswith("## "):
            doc.add_heading(line.replace("#", "").strip(), level=1)
        elif line.startswith("- "):
            doc.add_paragraph(line, style='List Bullet')
        elif re.match(r"^\d+\.", line):
            doc.add_paragraph(line, style='List Number')
        else:
            doc.add_paragraph(line)

    doc.save(filename)


# === OpenAI Client Setup ===
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)  # Replace with your actual key


# === File Extraction ===
def extract_text_from_pdf(file_path):
    try:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        return ""


def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        return ""


def load_all_text(folder_path):
    all_text = ""
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if filename.endswith(".pdf"):
            all_text += extract_text_from_pdf(file_path) + "\n"
        elif filename.endswith(".docx"):
            all_text += extract_text_from_docx(file_path) + "\n"
    return all_text.strip()


# === Clean and Sanitize Text ===
def clean_text(text):
    text = ''.join(c for c in text if c.isprintable() and c not in '\x00')
    return " ".join(text.split())


# === Count Tokens Using tiktoken ===
def count_tokens(text):
    enc = tiktoken.encoding_for_model('gpt-4')
    return len(enc.encode(text))


# === Prompt Builder ===
def build_prompt(certificate_name, context):
    return f"""
You are an expert mentor for the {certificate_name} exam.

You will receive chunks of unstructured context gathered from various sources like YouTube transcripts, blog posts, and user discussions (e.g., Reddit, Quora). These chunks may be partial or fragmented.

Your task is to extract and organize the most actionable and exam-relevant insights. Focus specifically on key concepts, practical examples, and what to prioritize in preparation. Do not generate a study plan — your job is to extract learning content that will later help form a study plan.

Once all context is received, structure your response with the following sections:

### 1. Most Important Topics to Focus On
- List and describe the most commonly emphasized or high-impact topics based on the context.
- Briefly explain why each topic matters for the exam and how it affects performance.

### 2. Learning Content, Examples, and Details
- Extract and explain any formulas, examples, or rules of thumb that enhance understanding.
- Include short explanations and practical use cases, especially for difficult concepts.

### 3. Why This Matters (Exam Relevance)
- For each concept, technique, or example, explain how it connects to real exam questions, scoring, or practical use in the field.

### 4. Helpful Resources
- Mention any specific books, articles, YouTube videos or playlists, tools, or websites that are considered valuable.
- Include links if they were shared in the context.

### 5. Effective Preparation Tips
- Summarize preparation techniques or strategies shared by others that proved effective (e.g., mock exams, time management, spaced repetition).

### 6. User Experience Insights
- Highlight what past candidates found helpful or frustrating.
- Include real-world advice on what to avoid or common mistakes made.

### 7. Quick Formula Reference (if applicable)
- List frequently used formulas or methods relevant to the exam.
- Provide short notes on their application and examples of how they are used in questions.

Important Notes:
- If no relevant data is found for a section, omit it.
- Your output should be clear, detailed, and self-contained — assume the user won't check external links.
- Use short paragraphs instead of excessive bullet points to encourage readability.

### Context:
\"\"\"
{context}
\"\"\"
"""


# === GPT Request ===
def split_text_by_tokens(text, max_tokens=280000, model="gpt-4.1-mini"):
    enc = tiktoken.encoding_for_model('gpt-4')
    tokens = enc.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = enc.decode(tokens[i:i + max_tokens])
        chunks.append(chunk)
    return chunks


def get_gpt_response(prompt, model="gpt-4.1-mini", max_tpm=400000):
    token_count = count_tokens(prompt)
    delay = 15
    print(f"⏳ Sleeping for {delay:.2f} seconds to respect TPM rate limit")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        time.sleep(delay + 2)  # Add buffer
        return response.choices[0].message.content
    except Exception as e:
        print("❌ Error:", str(e).encode('utf-8', errors='ignore').decode())

        return ""


def main(certificate_name="Certificate"):
    folder_path = "data"
    raw_text = load_all_text(folder_path)
    if not raw_text:
        return

    context = clean_text(raw_text)
    print(f"Processing {certificate_name} with context length: {len(context)} characters")
    total_tokens = count_tokens(context)
    print(f"🔢 Total tokens: {total_tokens}")

    chunks = split_text_by_tokens(context, max_tokens=280000)
    print(f"✂️ Total chunks: {len(chunks)} (each ≤ 950k tokens)")

    final_output = ""

    for i, chunk in enumerate(chunks):
        print(f"\n🚀 Sending chunk {i+1}/{len(chunks)} to GPT...")

        prompt = build_prompt(certificate_name, chunk)
        result = get_gpt_response(prompt)
        if not result:
            print("⚠️ Empty response from GPT.")
        final_output += result + "\n\n"
    print(f"Total tokens processed: {total_tokens}")
    print(f"Final output length: {len(final_output)} characters")
    save_to_word(final_output.strip())


if __name__ == "__main__":
    main()
