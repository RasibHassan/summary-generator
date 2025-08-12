import os
import fitz  # PyMuPDF
import docx
from openai import OpenAI
import tiktoken
import time
from dotenv import load_dotenv

load_dotenv()
# === OpenAI Client Setup ===
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)
# === File Extraction ===
def extract_text_from_pdf(file_path):
    try:
        doc = fitz.open(file_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        print(f"[ERROR] PDF extract: {e}")
        return ""

def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception as e:
        print(f"[ERROR] DOCX extract: {e}")
        return ""

def extract_text(file_path):
    if file_path.endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(".docx"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file type. Only .pdf and .docx supported.")

# === Utility Functions ===
def clean_text(text):
    text = ''.join(c for c in text if c.isprintable())
    return " ".join(text.split())

def count_tokens(text):
    enc = tiktoken.encoding_for_model('gpt-4')
    return len(enc.encode(text))

def split_text_by_tokens(text, max_tokens=280000):
    enc = tiktoken.encoding_for_model('gpt-4')
    tokens = enc.encode(text)
    return [enc.decode(tokens[i:i + max_tokens]) for i in range(0, len(tokens), max_tokens)]

# === Prompt for summarization ===
def build_summary_prompt(text_chunk):
    return f"""
Summarize this text in detail. Cover ALL topics and important points mentioned.

REQUIREMENTS:
- Include every major concept, fact, and idea
- Use clear headings for different sections
- Explain key terms and definitions
- Include specific examples and details
- Don't skip anything important
- Use simple, easy-to-understand language
- use less bullets and more paragraphs
- Make it comprehensive and thorough

This summary will be used for studying, so be thorough and complete.

TEXT:

\"\"\"
{text_chunk}
\"\"\"

"""

# === GPT Request ===
def get_gpt_response(prompt, model="gpt-4.1-mini"):
    delay = 15
    print(f"⏳ Waiting {delay}s to respect rate limits...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        time.sleep(delay + 2)  # Respect TPM limit
        return response.choices[0].message.content
    except Exception as e:
        print("❌ GPT error:", e)
        return ""

# === Main summary function to call externally ===
def generate_summary_from_file(file_path):
    raw_text = extract_text(file_path)
    if not raw_text:
        raise Exception("No text extracted from the document.")

    context = clean_text(raw_text)
    total_tokens = count_tokens(context)
    print(f"🔢 Total tokens: {total_tokens}")

    chunks = split_text_by_tokens(context, max_tokens=280000)
    print(f"✂️ Total chunks: {len(chunks)}")

    full_summary = ""
    for i, chunk in enumerate(chunks):
        print(f"🚀 Summarizing chunk {i+1}/{len(chunks)}...")
        prompt = build_summary_prompt(chunk)
        result = get_gpt_response(prompt)
        full_summary += result + "\n\n"

    return full_summary.strip()

