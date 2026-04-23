import os
import re
import time
import subprocess
import whisper
from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi

ffmpeg_path = r"C:\Users\voyya\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
deno_path = r"C:\Users\voyya\.deno\bin"
os.environ["PATH"] = ffmpeg_path + ";" + deno_path + ";" + os.environ.get("PATH", "")
os.environ["XDG_CACHE_HOME"] = r"D:\proograms\mine\projects\YTpro\models"

# --- CONFIGURATION ---
FFMPEG_DIR = r"C:\Users\voyya\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
QJS_PATH = r"D:\proograms\mine\projects\YTpro\qjs.exe"
COOKIE_FILE = 'cookies.txt'
MODEL_SIZE = "base"
TOP_N = 10

os.environ["XDG_CACHE_HOME"] = r"D:\proograms\mine\projects\YTpro\models"

print("Loading AI model...")
model = whisper.load_model(MODEL_SIZE)

def clean_filename(text):
    return re.sub(r'[^\w\s-]', '', text).strip().replace(' ', '_')[:50]

def transcribe_with_ai(video_id, folder, filename):
    print(f"      [AI] Transcribing {video_id}...")
    
    ydl_opts = {
        'cookiefile': COOKIE_FILE,
        'ffmpeg_location': FFMPEG_DIR if os.path.exists(FFMPEG_DIR) else None,
        'format': 'bestaudio/best',
        'outtmpl': f"{video_id}.%(ext)s",
        'quiet': False,
        'noplaylist': True,
    }
    
    try:
        video_url = f"https://youtube.com/watch?v={video_id}"
        print(f"      Downloading: {video_url}")
        
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        audio_files = [f for f in os.listdir('.') if f.startswith(video_id) and os.path.isfile(f)]
        if not audio_files:
            print(f"      ERROR: Audio file not downloaded")
            return False
        
        base_audio_path = audio_files[0]
        print(f"      Found audio: {base_audio_path}")
        
        if base_audio_path.endswith('.webm'):
            print(f"      Converting to wav...")
            wav_path = video_id + ".wav"
            subprocess.run([
                os.path.join(ffmpeg_path, "ffmpeg.exe"), "-y", "-i", base_audio_path, "-vn",
                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path
            ], capture_output=True)
            os.remove(base_audio_path)
            base_audio_path = wav_path
            print(f"      Converted to: {base_audio_path}")
        
        result = model.transcribe(base_audio_path, fp16=False)
        with open(os.path.join(folder, filename), "w", encoding="utf-8") as f:
            f.write(result['text'].strip())
        
        if os.path.exists(base_audio_path):
            os.remove(base_audio_path)
        return True
    except Exception as e:
        if 'base_audio_path' in locals() and os.path.exists(base_audio_path):
            os.remove(base_audio_path)
        print(f"      AI Error: {e}")
        return False

def get_transcript(v_id, v_title, folder):
    fname = f"{clean_filename(v_title)}_{v_id}.txt"
    
    try:
        t_list = YouTubeTranscriptApi.list_transcripts(v_id)
        try:
            t = t_list.find_transcript(['en', 'en-US'])
        except:
            available = list(t_list)
            t = available[0].translate('en') if available else None
        
        if t:
            data = t.fetch()
            text = " ".join([item['text'] for item in data])
            with open(os.path.join(folder, fname), "w", encoding="utf-8") as f:
                f.write(text)
            print(f"      Saved (YouTube): {v_id}")
            return
    except:
        pass

    if transcribe_with_ai(v_id, folder, fname):
        print(f"      Saved (AI): {v_id}")
    else:
        print(f"      Failed: {v_id}")

def get_popular_videos(channel_url, limit=10):
    if not channel_url.startswith('http'):
        channel_url = 'https://' + channel_url
        
    for tab in ['videos', 'shorts']:
        url = f"{channel_url.rstrip('/')}/{tab}?view=0&sort=p"
        opts = {
            'cookiefile': COOKIE_FILE,
            'quiet': True, 
            'extract_flat': True, 
            'playlist_items': f'1-{limit}'
        }
        try:
            with YoutubeDL(opts) as ydl:
                print(f"   Checking {tab} tab...")
                res = ydl.extract_info(url, download=False)
                if res and 'entries' in res and res['entries']:
                    return [(v['id'], v['title']) for v in res['entries']]
        except Exception as e:
            print(f"   (Tab {tab} failed: {str(e)[:50]}...)")
            continue
    return []

def main():
    print("\n" + "="*40 + "\nYouTube Transcript Fetcher (AI + Cookies)\n" + "="*40)
    print("1. Single Channel")
    print("2. Bulk Channels")
    
    choice = input("\nEnter choice (1/2): ").strip()
    
    if choice == "1":
        urls = [input("Enter channel URL: ").strip()]
    elif choice == "2":
        print("\nEnter channel URLs (one per line). Press Enter twice when done:")
        urls = []
        while True:
            line = input().strip()
            if line:
                urls.append(line)
            elif urls:
                break
    else:
        print("Invalid choice")
        return

    for url in urls:
        if not url:
            continue
        
        clean_url = url.split('?')[0]
        name = clean_url.split('@')[-1] if '@' in clean_url else clean_url.split('/')[-1]
        print(f"\nProcessing: {name}")
        os.makedirs(name, exist_ok=True)
        
        videos = get_popular_videos(clean_url, TOP_N)
        if not videos:
            print("   No videos found. Check cookies or URL.")
            continue

        for v_id, v_title in videos:
            get_transcript(v_id, v_title, name)
            print("      Waiting 10s...")
            time.sleep(10)
            
    print("\nAll tasks complete.")

if __name__ == "__main__":
    main()