import anthropic
from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import re
import sys
import os
from dotenv import load_dotenv

load_dotenv()
# === Read text from Word doc ===
def read_docx_text(file_path):
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

# === Add formatted text with bold styling ===
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

# === Write Claude output to Word ===
def write_to_word(text, output_file="generated_study_plan.docx"):
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

# === Build Prompt for Claude ===
def build_prompt(certificate_name, context_text):
    return f"""
Generate a **complete and detailed preparation guide** for the certification course: {certificate_name}.

Your output must be **clearly structured, visually scannable, and content-rich**. Focus on both **exam success** and **real-world applicability**.

Organize the guide by **core topics or chapters** (not by calendar weeks), **but provide a suggested study sequence and timeline** upfront. Ensure the reader knows **what to study first, what matters most for the exam, and how to manage their time**.

---

### 📌 Guide Structure

Your output should follow this structure strictly:

---

## 📚 Table of Contents (Clickable)

List all major topics/chapters, with estimated study time and exam weight if applicable. Make this section clickable or clearly navigable.

Format:
- Topic 1: Title (⏱️ 15 hrs, 🎯 30% of Exam)
- Topic 2: Title (⏱️ 10 hrs, 🎯 20% of Exam)
- …

---

## 🧭 Study Plan & Timeline

Suggest a **recommended study sequence** with rough weekly pacing. For example:
- Week 1–2: Focus on Topic A and B (⏱️ 25 hrs)
- Week 3–4: Dive into Topic C (⏱️ 15 hrs)
Also, mention **how long** the entire prep should ideally take (e.g., 6–8 weeks with 1–2 hours/day).

---

Then for each topic, repeat the following structure:

---

## ✅ Topic X of N: Topic Title (⏱️ X hrs, 🎯 Y% of Exam)

### 1. Overview
Introduce the topic, explain **why it matters** in the context of the exam and **real world example**. Keep it concise but informative.

### 2. Key Subtopics
Break down the topic into its core areas. Use short paragraphs (not bullets) to explain what each subtopic includes. Keep it concise.

### 3. Detailed Learning Content
Explain concepts in simple terms and in detail. Include:
- Real-world examples or case studies
- Step-by-step breakdowns
- "Why this matters for the exam" notes
- Summary tables in text format if needed
- Use your own knowledge to fill in gaps

### 4. Study Strategies & Techniques
Provide guidance on how to study (keep it concise):
- Common expert tips
- Learning order if applicable

### 6. High-Quality Resources (with Links)
Curate **3–5 trusted links**. These can be:
- Official documentation
- Popular YouTube tutorials
- Blog articles or GitHub repos
Format: [Resource Title](URL) – brief description

### 7. Practice Tools or Platforms (if applicable)
List hands-on environments, mock tests, coding simulators, or sandboxes. Include official question banks if available.

### 8. Mini Quiz / Self-Test
Create 5 sample questions with:
- Correct answer
- Short explanation of why it’s correct
Use plain text, no formatting or markdown.

---

### 📌 Final Section: Quick Reference & Formula Sheet
Summarize any **must-know formulas**, acronyms, or frameworks. This should act as a last-minute cram sheet. And tell common mistakes to avoid.

---

### ⚠️ Formatting Rules
- Cover all Topics in output
- Keep each explanation **concise but complete**. Focus on clarity over length.
- Keep everything **text-based** (no images or charts)
- Use bullet points
- Use **progress indicators** like “Topic X of N”
- Ensure easy navigation via headings and clear structure
- Every section should feel **useful, not overwhelming**

### 🚫 Don’t Do This:
- No vague summaries
- No overuse of bullet points without explanation
- No skipping the study timeline or quiz sections

Take Help From the Context Below. It includes information you need to create a comprehensive study plan:
\"\"\"
{context_text}
\"\"\"

Now write the most structured, visual-friendly, and exam-focused guide possible for {certificate_name}.
"""

# === Main processing function ===
def main(certificate_name="PMP Certificate"):
    # Step 1: Read input context
    context_text = read_docx_text("gpt_study_plan.docx")
    print(f"📘 Certificate: {certificate_name}")

    # Step 2: Construct prompt
    prompt = build_prompt(certificate_name, context_text)

    # Step 3: Setup Anthropic Client
    claude_api_key=os.getenv("CLAUDE_API_KEY")
    client = anthropic.Anthropic(
        api_key=claude_api_key  # <-- Replace with your actual key
    )

    # Step 4: Stream response
    print("⚙️ Generating content using Claude...")
    stream = client.messages.create(
        model="claude-opus-4-20250514",
        stream=True,
        max_tokens=20000,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}]
    )

    # Step 5: Accumulate and save response
    response_text = ""
    for event in stream:
        if hasattr(event, "delta") and hasattr(event.delta, "text"):
            response_text += event.delta.text

    # Step 6: Write to Word
    write_to_word(response_text, "generated_study_plan.docx")
    print("✅ Study plan generated: generated_study_plan.docx")

# === CLI Entry ===
if __name__ == "__main__":
    cert_name = sys.argv[1] if len(sys.argv) > 1 else "PMP Certificate"
    main(cert_name)
