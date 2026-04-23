# YouTube Transcript Fetcher

A tool to fetch transcripts from YouTube channels using either YouTube's API or AI transcription (Whisper) as a fallback.

## Features

- Fetch transcripts from YouTube channels or single videos
- Supports both regular videos and Shorts
- Uses YouTube transcript API when available
- Falls back to AI transcription (Whisper) when no transcript exists
- Bulk channel processing

## Requirements

- Python 3.8+
- FFmpeg
- Deno (for cache)
- YouTube cookies (for accessing age-restricted/private content)

## Installation

```bash
pip install -r requirements.txt
```

## Setup

1. **FFmpeg**: Install FFmpeg and update the path in `ytpro.py`
2. **Deno**: Install Deno and update the path in `ytpro.py`
3. **Cookies**: Export your YouTube cookies to `cookies.txt` (see [cookie-export](https://github.com/nicholasxjy/cookie-export))
4. **Model**: The Whisper model will download automatically on first run

## Usage

```bash
python ytpro.py
```

Select:
- `1` - Single channel
- `2` - Multiple channels

Enter channel URL(s) when prompted. Transcripts will be saved in folder(s) named after the channel.

## Configuration

Edit `ytpro.py` to change:
- `MODEL_SIZE` - Whisper model size (tiny, base, small, medium, large)
- `TOP_N` - Number of videos to fetch per channel

## License

MIT License - See LICENSE file