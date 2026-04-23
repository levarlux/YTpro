import os
import re
import time
import sys
import logging
import tempfile
import shutil
import subprocess
from pathlib import Path

import whisper
from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class Config:
    MODEL_SIZE = os.environ.get("MODEL_SIZE", "base")
    TOP_N = int(os.environ.get("TOP_N", "10"))
    COOKIE_FILE = os.environ.get("COOKIE_FILE", "cookies.txt")
    FFMPEG_DIR = os.environ.get("FFMPEG_DIR", "")
    OUTPUT_DIR = os.environ.get("OUTPUT_DIR", ".")

    @classmethod
    def init(cls, base_dir: Path | None = None):
        if base_dir:
            os.environ["XDG_CACHE_HOME"] = str(base_dir / "models")
            cls.OUTPUT_DIR = str(base_dir)

        if cls.FFMPEG_DIR and os.path.isdir(cls.FFMPEG_DIR):
            os.environ["PATH"] = cls.FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")


def clean_filename(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")[:50]


def transcribe_with_ai(video_id: str, folder: str, filename: str, model) -> bool:
    logger.info(f"[AI] Transcribing {video_id}...")

    ydl_opts = {
        "cookiefile": Config.COOKIE_FILE,
        "ffmpeg_location": Config.FFMPEG_DIR if Config.FFMPEG_DIR else None,
        "format": "bestaudio/best",
        "outtmpl": f"{video_id}.%(ext)s",
        "quiet": False,
        "noplaylist": True,
    }

    temp_dir = None
    base_audio_path = None
    cleanup_needed = []

    try:
        video_url = f"https://youtube.com/watch?v={video_id}"
        logger.info(f"Downloading: {video_url}")

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        audio_files = [f for f in os.listdir(".") if f.startswith(video_id) and os.path.isfile(f)]
        if not audio_files:
            logger.error(f"Audio file not downloaded: {video_id}")
            return False

        base_audio_path = audio_files[0]
        logger.info(f"Found audio: {base_audio_path}")
        cleanup_needed.append(base_audio_path)

        if base_audio_path.endswith(".webm"):
            logger.info("Converting to wav...")
            temp_dir = tempfile.mkdtemp()
            wav_path = os.path.join(temp_dir, f"{video_id}.wav")
            subprocess.run(
                [shutil.which("ffmpeg") or "ffmpeg.exe", "-y", "-i", base_audio_path, "-vn",
                 "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav_path],
                capture_output=True,
                check=True,
            )
            base_audio_path = wav_path
            logger.info(f"Converted to: {base_audio_path}")

        result = model.transcribe(base_audio_path, fp16=False)
        filepath = os.path.join(folder, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(result["text"].strip())

        logger.info(f"Saved (AI): {video_id}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e}")
    except Exception as e:
        logger.error(f"AI transcription failed for {video_id}: {e}")
    finally:
        for path in cleanup_needed:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

    return False


def get_transcript(v_id: str, v_title: str, folder: str, model) -> bool:
    fname = f"{clean_filename(v_title)}_{v_id}.txt"

    try:
        t_list = YouTubeTranscriptApi.list_transcripts(v_id)
        try:
            transcript = t_list.find_transcript(["en", "en-US"])
        except Exception:
            available = list(t_list)
            transcript = available[0].translate("en") if available else None

        if transcript:
            data = transcript.fetch()
            text = " ".join(item["text"] for item in data)
            filepath = os.path.join(folder, fname)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Saved (YouTube): {v_id}")
            return True
    except Exception as e:
        logger.debug(f"Notranscript API for {v_id}: {e}")

    return transcribe_with_ai(v_id, folder, fname, model)


def get_popular_videos(channel_url: str, limit: int = 10) -> list[tuple[str, str]]:
    if not channel_url.startswith("http"):
        channel_url = "https://" + channel_url

    for tab in ["videos", "shorts"]:
        url = f"{channel_url.rstrip('/')}/{tab}?view=0&sort=p"
        opts = {
            "cookiefile": Config.COOKIE_FILE,
            "quiet": True,
            "extract_flat": True,
            "playlist_items": f"1-{limit}",
        }
        try:
            with YoutubeDL(opts) as ydl:
                logger.debug(f"Checking {tab} tab...")
                res = ydl.extract_info(url, download=False)
                if res and "entries" in res and res["entries"]:
                    return [(v["id"], v["title"]) for v in res["entries"]]
        except Exception as e:
            logger.debug(f"Tab {tab} failed: {e}")
            continue
    return []


def main():
    import argparse

    parser = argparse.ArgumentParser(description="YouTube Transcript Fetcher")
    parser.add_argument("urls", nargs="*", help="Channel URLs")
    parser.add_argument("--model", default=Config.MODEL_SIZE, help="Whisper model size")
    parser.add_argument("--top-n", type=int, default=Config.TOP_N, help="Videos per channel")
    parser.add_argument("--output", default=Config.OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    Config.MODEL_SIZE = args.model
    Config.TOP_N = args.top_n
    Config.OUTPUT_DIR = args.output
    Config.init(Path(__file__).parent)

    logger.info(f"Loading Whisper model: {Config.MODEL_SIZE}...")
    model = whisper.load_model(Config.MODEL_SIZE)

    logger.info("=== YouTube Transcript Fetcher ===")
    logger.info("1. Single Channel | 2. Bulk Channels")

    if args.urls:
        urls = args.urls
    else:
        choice = input("Enter choice (1/2): ").strip()
        if choice == "1":
            urls = [input("Enter channel URL: ").strip()]
        elif choice == "2":
            logger.info("Enter channel URLs (one per line). Press Enter twice when done:")
            urls = []
            while (line := input().strip()):
                urls.append(line)
        else:
            logger.error("Invalid choice")
            return

    for url in urls:
        if not url:
            continue

        clean_url = url.split("?")[0]
        name = clean_url.rstrip("/").split("/")[-1]
        if "@" in clean_url:
            name = clean_url.split("@")[-1]

        logger.info(f"Processing: {name}")
        os.makedirs(name, exist_ok=True)

        videos = get_popular_videos(clean_url, Config.TOP_N)
        if not videos:
            logger.warning("No videos found. Check cookies or URL.")
            continue

        for v_id, v_title in videos:
            get_transcript(v_id, v_title, name, model)
            logger.debug("Waiting 10s...")
            time.sleep(10)

    logger.info("All tasks complete.")


if __name__ == "__main__":
    main()