import whisper
from openai import OpenAI
import os
import re
from dotenv import load_dotenv

load_dotenv()
# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=openai_api_key)

# Load Whisper model
whisper_model = whisper.load_model("base")  # You can use "small", "medium", or "large"

def transcribe_video(video_path):
    """Transcribe the audio from a video file using Whisper."""
    print("🎧 Transcribing video...")
    try:
        result = whisper_model.transcribe(video_path)
        return result["text"]
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return e

def summarize_text(text):
    """Use OpenAI GPT to summarize the text."""
    print("🧠 Summarizing transcript...")
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes transcripts clearly."
                },
                {
                    "role": "user",
                    "content": (
                        "Please summarize the following transcript thoroughly. Your summary should:\n"
                        "- Use clear and simple English\n"
                        "- Be organized into logical, well-structured paragraphs\n"
                        "- Include all major topics, events, and ideas from beginning to end\n"
                        "- Highlight key points, arguments, or facts\n"
                        "- Preserve the overall meaning and context without leaving out important details\n"
                        "- Maintain the order and flow of the original transcript\n\n"
                        "- Summary should be detailed\n "
                        "- Create headings for each section if the text is divided into parts.\n"
                        f"Transcript:\n{text}"
                    )
                }
            ],
            temperature=0.5,
            max_tokens=10000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Summarization failed: {e}")
        return None

def save_summary(filename, summary):
    """Save summary to a text file."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"\n💾 Summary saved to '{filename}'")

def get_summary_from_video(video_path):
    """
    Main function to call: Transcribes and summarizes the given video file.
    Returns the summary string.
    """
    if not os.path.exists(video_path):
        print("❌ File not found.")
        return None

    transcript = transcribe_video(video_path)
    return transcript
    # if not transcript:
    #     return None

    # summary = summarize_text(transcript)
    # return summary