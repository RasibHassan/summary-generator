from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
from openai import OpenAI
import whisper
import yt_dlp
import re
import os
from dotenv import load_dotenv

load_dotenv()
# Initialize OpenAI client with your API key
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)
whisper_model = whisper.load_model("base")  # Or 'small', 'medium', 'large'

def extract_video_id(youtube_url):
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", youtube_url)
    return match.group(1) if match else None

def get_youtube_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([segment["text"] for segment in transcript_list])
        return full_text
    except Exception as e:
        return None  # Indicate failure

def download_audio_with_ytdlp(youtube_url, filename="temp_audio.mp3"):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        return filename
    except Exception as e:
        print(f"❌ Failed to download audio: {e}")
        return None

def transcribe_audio_with_whisper(audio_path):
    try:
        result = whisper_model.transcribe(audio_path)
        return result['text']
    except Exception as e:
        print(f"❌ Whisper transcription error: {e}")
        return None

def summarize_text(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes transcripts clearly and concisely."
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
                        "- Avoid personal opinions or assumptions\n"
                        "- Maintain the order and flow of the original transcript\n\n"
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
        return f"Error summarizing: {e}"

def save_to_txt(filename, summary):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"\n💾 Summary saved to '{filename}'")

def summarize_youtube_video(youtube_url, save=False):
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return "❌ Invalid YouTube URL."

    print("📥 Trying to get transcript from YouTube...")
    transcript = get_youtube_transcript(video_id)

    if not transcript:
        print("⚠️ Transcript not found. Falling back to Whisper transcription...")
        audio_path = "temp_audio.mp3"
        downloaded = download_audio_with_ytdlp(youtube_url, audio_path)
        if not downloaded:
            return "❌ Failed to retrieve transcript via Whisper."

        transcript = transcribe_audio_with_whisper(audio_path)
        os.remove(audio_path)

        if not transcript:
            return "❌ Unable to transcribe audio."

    print("\n🧠 Summarizing transcript...")
    summary = summarize_text(transcript)

    if save:
        try:
            yt = YouTube(youtube_url)
            title = re.sub(r'[\\/*?:"<>|]', "", yt.title)
            filename = f"{title}_summary.txt"
        except:
            filename = "youtube_summary.txt"

        save_to_txt(filename, summary)

    return summary