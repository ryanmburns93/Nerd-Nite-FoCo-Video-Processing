# Nerd Nite FoCo Video Processing

Command-line tools for processing presentation recordings:

- `subtitle_video.py` — automatically transcribes a video and produces a
  copy with subtitles permanently burned in.
- `add_title_image.py` — prepends a still title image (e.g. a title slide)
  to a video, holding it for a few seconds and then crossfading into the
  video.
- `add_watermark.py` — overlays the Nerd Nite FoCo logo as a corner
  watermark for the whole video.

No manual editing or cloud notebook required. `subtitle_video.py`
reproduces the workflow originally prototyped in Google Colab (transcribe
with `faster-whisper`, format into readable subtitle blocks, burn in with
`ffmpeg`), but runs entirely on your own machine's CPU.

## Setup

1. Install [ffmpeg](https://ffmpeg.org/download.html) and make sure it's on your `PATH`:
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt install ffmpeg`
   - Windows: `winget install ffmpeg` (or download a build from the link above and add its `bin/` folder to your `PATH`)
2. Create a virtual environment and install Python dependencies (run these
   one at a time, or paste the whole block at once — it's chained with `&&`
   so a merged paste still runs each step correctly):

   macOS/Linux:
   ```bash
   python3 -m venv venv &&
   source venv/bin/activate &&
   pip install -r requirements.txt
   ```

   Windows (Git Bash) — `venv` puts the activation script under `Scripts/`
   instead of `bin/`:
   ```bash
   python -m venv venv &&
   source venv/Scripts/activate &&
   pip install -r requirements.txt
   ```

   Windows (Command Prompt):
   ```bat
   python -m venv venv && venv\Scripts\activate.bat && pip install -r requirements.txt
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

## Adding a title image intro

Point `add_title_image.py` at a video and a still image (`.jpg`, `.jpeg`, or
`.png`) to prepend it as a title card:

```bash
python add_title_image.py "My Presentation.mp4" title_image.png
```

This produces `My Presentation_with_title.mp4`: the image is shown for 5
seconds, then crossfades into the video over 1.5 seconds, after which the
video plays normally (with its original audio, delayed to stay in sync).
The image is automatically scaled and letterboxed to match the video's
resolution.

### Options

```bash
python add_title_image.py INPUT.mp4 title_image.png -o OUTPUT.mp4  # custom output path
python add_title_image.py INPUT.mp4 title_image.png --hold 3       # hold the image for 3s instead of 5s
python add_title_image.py INPUT.mp4 title_image.png --fade 2.5     # a longer 2.5s crossfade
```

Only `ffmpeg`/`ffprobe` are required — no extra Python libraries. Run
`python add_title_image.py --help` for the full list of options.

Uses `ffmpeg`'s [`xfade`](https://ffmpeg.org/ffmpeg-filters.html#xfade)
filter, matching the video's resolution and frame rate under the hood so
the crossfade renders cleanly.

## Adding the logo watermark

Point `add_watermark.py` at a video to overlay the Nerd Nite FoCo logo
(`assets/NNFoCoLogo_winter.png`) in the bottom-right corner for the video's
whole duration:

```bash
python add_watermark.py "My Presentation.mp4" assets/NNFoCoLogo_winter.png
```

This produces `My Presentation_watermarked.mp4`, with the watermark sized
to 8% of the video's width and inset slightly from the corner edges, so it
reads as a tasteful tag rather than a content-blocking sticker. It's scaled
relative to the video's own resolution, so it looks right on any output size.

### Options

```bash
python add_watermark.py INPUT.mp4 logo.png -o OUTPUT.mp4       # custom output path
python add_watermark.py INPUT.mp4 logo.png --scale 0.05        # smaller watermark (5% of width)
python add_watermark.py INPUT.mp4 logo.png --margin -0.015     # let it hang off the edge instead of padding inward
python add_watermark.py INPUT.mp4 logo.png --position top-left # place it in a different corner
```

Only `ffmpeg` is required — no extra Python libraries. Run
`python add_watermark.py --help` for the full list of options.
