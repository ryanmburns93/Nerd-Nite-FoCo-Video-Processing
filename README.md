# Nerd Nite FoCo Video Processing

`process_video.py` is the main command-line tool: point it at a video and it
transcribes it, burns in subtitles, and overlays the Nerd Nite FoCo logo
watermark — with an option to prepend a title image intro — producing one
finished video. No manual editing or cloud notebook required.

It reproduces the workflow originally prototyped in Google Colab (transcribe
with `faster-whisper`, format into readable subtitle blocks, burn in with
`ffmpeg`), but runs entirely on your own machine's CPU.

`add_title_image.py` and `add_watermark.py` also remain available as
standalone tools, for using either feature on its own without the rest of
the pipeline.

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
python process_video.py "My Presentation.mp4"
```

This produces:
- `My Presentation.srt` — the generated subtitle file
- `My Presentation_processed.mp4` — the finished video, with subtitles
  burned in and the Nerd Nite FoCo logo watermark overlaid (see
  [Adding the logo watermark](#adding-the-logo-watermark) below)

To also prepend a title card, pass `--title-screen`:

```bash
python process_video.py "My Presentation.mp4" --title-screen title_image.png
```

The title image is shown for 5 seconds and crossfades into the video (see
[Adding a title image intro](#adding-a-title-image-intro) below); subtitle
timing is automatically shifted to stay in sync with the delayed video.

### Options

```bash
python process_video.py INPUT.mp4 -o OUTPUT.mp4          # custom output path
python process_video.py INPUT.mp4 --srt custom.srt        # custom .srt path
python process_video.py INPUT.mp4 --model-size small      # faster, less accurate
python process_video.py INPUT.mp4 --model-size large-v3   # slower, more accurate
python process_video.py INPUT.mp4 --srt-only              # just generate the .srt
python process_video.py INPUT.mp4 --burn-only --srt a.srt # skip transcription, use an existing .srt
python process_video.py INPUT.mp4 --force-transcribe      # redo transcription even if .srt exists
python process_video.py INPUT.mp4 --title-screen title.png --title-hold 3 --title-fade 2.5  # tune the title intro
python process_video.py INPUT.mp4 --no-watermark          # skip the watermark
python process_video.py INPUT.mp4 --watermark-image logo.png --watermark-scale 0.05 --watermark-position top-left  # tune the watermark
```

Run `python process_video.py --help` for the full list of options.

## Notes on speed

Transcription runs on CPU by default via `faster-whisper`, since GPU access
isn't guaranteed outside Colab. This is slower than the GPU-enabled Colab
version but requires no special hardware. To trade accuracy for speed,
use a smaller model (`--model-size small` or `tiny`); for the best
transcription quality on a long presentation, use `--model-size large-v3`
and let it run in the background.

If your machine does have an NVIDIA GPU with CUDA + cuDNN installed, pass
`--device cuda --compute-type float16` for a large speedup.

Every long-running step (transcription, title screen rendering, subtitle
burn-in, and watermarking) prints a live progress bar so you can see it's
still working rather than staring at a silent terminal.

## How subtitle formatting works

The transcript is split into subtitle blocks using the same rules as the
original manual-editing style: blocks break at sentence-ending punctuation,
after ~80 characters (two 40-character lines), after ~6.5 seconds, or after
a pause of ~1 second or more — whichever comes first.

## Adding a title image intro

Passing `--title-screen title_image.png` (`.jpg`, `.jpeg`, or `.png`) to
`process_video.py` prepends it as a title card: shown for 5 seconds
(`--title-hold`), then crossfading into the video over 1.5 seconds
(`--title-fade`), after which the video plays normally with its original
audio, delayed to stay in sync. The image is automatically scaled and
letterboxed to match the video's resolution.

`add_title_image.py` is also available standalone, for prepending a title
image without running the rest of the pipeline:

```bash
python add_title_image.py "My Presentation.mp4" title_image.png
```

This produces `My Presentation_with_title.mp4`. Only `ffmpeg`/`ffprobe` are
required — no extra Python libraries. Run `python add_title_image.py --help`
for the full list of options.

Uses `ffmpeg`'s [`xfade`](https://ffmpeg.org/ffmpeg-filters.html#xfade)
filter, matching the video's resolution and frame rate under the hood so
the crossfade renders cleanly.

## Adding the logo watermark

`process_video.py` overlays the Nerd Nite FoCo logo
(`assets/NNFoCoLogo_winter.png`) in the bottom-right corner by default, for
the whole output video's duration — sized to 8% of the video's width and
inset slightly from the corner edges, so it reads as a tasteful tag rather
than a content-blocking sticker. Pass `--no-watermark` to skip it, or
`--watermark-image`/`--watermark-scale`/`--watermark-margin`/
`--watermark-position` to customize it.

`add_watermark.py` is also available standalone, for watermarking a video
without running the rest of the pipeline:

```bash
python add_watermark.py "My Presentation.mp4" assets/NNFoCoLogo_winter.png
```

This produces `My Presentation_watermarked.mp4`. It's scaled relative to
the video's own resolution, so it looks right on any output size. Only
`ffmpeg` is required — no extra Python libraries. Run
`python add_watermark.py --help` for the full list of options.
