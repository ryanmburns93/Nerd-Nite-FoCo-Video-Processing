# Nerd Nite FoCo Video Processing

A simple command-line tool that takes a video file, automatically transcribes
it, and produces a copy with subtitles permanently burned in — no manual
editing or cloud notebook required.

It reproduces the workflow originally prototyped in Google Colab
(transcribe with `faster-whisper`, format into readable subtitle blocks,
burn in with `ffmpeg`), but runs entirely on your own machine's CPU.

## Setup

1. Install [ffmpeg](https://ffmpeg.org/download.html) and make sure it's on your `PATH`:
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt install ffmpeg`
2. Create a virtual environment and install Python dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Usage

Point the tool at any video file:

```bash
python subtitle_video.py "My Presentation.mp4"
```

This produces:
- `My Presentation.srt` — the generated subtitle file
- `My Presentation_subtitled.mp4` — the video with subtitles burned in

### Options

```bash
python subtitle_video.py INPUT.mp4 -o OUTPUT.mp4          # custom output path
python subtitle_video.py INPUT.mp4 --srt custom.srt        # custom .srt path
python subtitle_video.py INPUT.mp4 --model-size small      # faster, less accurate
python subtitle_video.py INPUT.mp4 --model-size large-v3   # slower, more accurate
python subtitle_video.py INPUT.mp4 --srt-only              # just generate the .srt
python subtitle_video.py INPUT.mp4 --burn-only --srt a.srt # just burn in an existing .srt
python subtitle_video.py INPUT.mp4 --force-transcribe      # redo transcription even if .srt exists
```

Run `python subtitle_video.py --help` for the full list of options.

## Notes on speed

Transcription runs on CPU by default via `faster-whisper`, since GPU access
isn't guaranteed outside Colab. This is slower than the GPU-enabled Colab
version but requires no special hardware. To trade accuracy for speed,
use a smaller model (`--model-size small` or `tiny`); for the best
transcription quality on a long presentation, use `--model-size large-v3`
and let it run in the background.

If your machine does have an NVIDIA GPU with CUDA + cuDNN installed, pass
`--device cuda --compute-type float16` for a large speedup.

## How subtitle formatting works

The transcript is split into subtitle blocks using the same rules as the
original manual-editing style: blocks break at sentence-ending punctuation,
after ~80 characters (two 40-character lines), after ~6.5 seconds, or after
a pause of ~1 second or more — whichever comes first.
