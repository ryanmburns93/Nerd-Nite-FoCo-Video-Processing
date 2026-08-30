#!/usr/bin/env python3
"""Transcribe a video, burn in subtitles, and produce a finished video.

Optionally prepends a title image intro and, by default, overlays the
Nerd Nite FoCo logo watermark. This is the main entry point of the repo;
add_title_image.py and add_watermark.py remain available standalone for
using either feature on its own.

Usage:
    python process_video.py INPUT.mp4
    python process_video.py INPUT.mp4 --title-screen title_image.png
    python process_video.py INPUT.mp4 --no-watermark
    python process_video.py INPUT.mp4 -o OUTPUT.mp4 --model-size medium
    python process_video.py INPUT.mp4 --srt-only
    python process_video.py INPUT.mp4 --burn-only --srt existing.srt

Runs on CPU by default (no GPU required), matching the workflow originally
prototyped in Google Colab with GPU-enabled faster-whisper.
"""

import argparse
import datetime
import os
import re
import shutil
import tempfile

from add_title_image import add_title_image
from add_watermark import add_watermark, POSITIONS as WATERMARK_POSITIONS
from ffmpeg_utils import get_duration, print_progress_bar, run_ffmpeg

VALID_IMAGE_EXTS = (".jpg", ".jpeg", ".png")

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WATERMARK_IMAGE = os.path.join(REPO_DIR, "assets", "NNFoCoLogo_winter.png")

# Calibrated settings matching the original manual-editing style.
MAX_CHARS_PER_LINE = 40  # Allows natural 36-42 character line widths
MAX_LINES = 2  # Standard 2-line maximum
MAX_CHARS_PER_BLOCK = MAX_CHARS_PER_LINE * MAX_LINES  # ~80 characters max
MAX_BLOCK_DURATION = 6.5  # Allows natural 4.5s-6.5s presentation windows
MAX_PAUSE_SECONDS = 0.95  # Don't split on minor hesitations (< 0.95s)
MIN_CHUNK_CHARS_FOR_PUNCT_SPLIT = 35  # Only split on sentence ends if block has meaningful length


def format_timestamp(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def wrap_words_into_lines(words: list, max_line_len: int) -> str:
    """Formats words into 1 or 2 balanced lines without breaking individual words."""
    lines = []
    current_line = []
    current_len = 0

    for word in words:
        word_len = len(word)
        if current_line and (current_len + 1 + word_len) > max_line_len:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_len = word_len
        else:
            current_line.append(word)
            current_len += (1 if len(current_line) > 1 else 0) + word_len

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)


def generate_srt(
    video_path: str,
    output_srt: str,
    model_size: str = "medium",
    device: str = "cpu",
    compute_type: str = "int8",
) -> None:
    from faster_whisper import WhisperModel

    print(f"Loading model '{model_size}' (device={device}, compute_type={compute_type})...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print("Transcribing (this can take a while on CPU)...")
    segments, info = model.transcribe(
        video_path, beam_size=5, word_timestamps=True, vad_filter=True
    )

    srt_blocks = []
    current_chunk = []

    for segment in segments:
        if info.duration > 0:
            print_progress_bar("Transcribing", segment.end / info.duration)

        if not segment.words:
            continue

        for word in segment.words:
            word_text = word.word.strip()
            if not word_text:
                continue

            if not current_chunk:
                current_chunk.append(word)
                continue

            prev_word = current_chunk[-1]
            chunk_text = " ".join(w.word.strip() for w in current_chunk)
            tentative_len = len(chunk_text) + 1 + len(word_text)
            duration = word.end - current_chunk[0].start
            pause = word.start - prev_word.end

            has_terminal_punct = prev_word.word.strip().endswith((".", "?", "!"))
            punct_split_ready = (
                has_terminal_punct and len(chunk_text) >= MIN_CHUNK_CHARS_FOR_PUNCT_SPLIT
            )

            capacity_reached = (
                tentative_len > MAX_CHARS_PER_BLOCK or duration >= MAX_BLOCK_DURATION
            )

            silence_split = pause >= MAX_PAUSE_SECONDS

            if punct_split_ready or capacity_reached or silence_split:
                start_time = current_chunk[0].start
                end_time = prev_word.end
                formatted_text = wrap_words_into_lines(
                    [w.word.strip() for w in current_chunk], MAX_CHARS_PER_LINE
                )
                srt_blocks.append((start_time, end_time, formatted_text))
                current_chunk = [word]
            else:
                current_chunk.append(word)

    if current_chunk:
        start_time = current_chunk[0].start
        end_time = current_chunk[-1].end
        formatted_text = wrap_words_into_lines(
            [w.word.strip() for w in current_chunk], MAX_CHARS_PER_LINE
        )
        srt_blocks.append((start_time, end_time, formatted_text))

    if info.duration > 0:
        print_progress_bar("Transcribing", 1.0)
        print()

    with open(output_srt, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(srt_blocks, start=1):
            f.write(
                f"{idx}\n{format_timestamp(start)} --> {format_timestamp(end)}\n{text}\n\n"
            )

    print(f"Generated {len(srt_blocks)} subtitle blocks -> '{output_srt}'")


def escape_subtitles_path(path: str) -> str:
    """Escape a path for safe use inside an ffmpeg subtitles= filter argument."""
    abs_path = os.path.abspath(path)
    return abs_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH. Install it (e.g. 'apt install ffmpeg' or 'brew install ffmpeg') and try again.")

    escaped_srt = escape_subtitles_path(srt_path)
    vf = f"subtitles='{escaped_srt}'"
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", vf, "-c:a", "copy", output_path]

    run_ffmpeg(cmd, total_duration=get_duration(video_path), label="Burning in subtitles")
    print(f"Wrote subtitled video -> '{output_path}'")


SRT_TIMESTAMP_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def shift_srt(input_srt: str, output_srt: str, offset_seconds: float) -> None:
    """Rewrite an .srt file with every timestamp shifted forward by offset_seconds."""

    def shift_match(match: re.Match) -> str:
        hours, minutes, secs, millis = (int(g) for g in match.groups())
        total_seconds = hours * 3600 + minutes * 60 + secs + millis / 1000
        return format_timestamp(total_seconds + offset_seconds)

    with open(input_srt, encoding="utf-8") as f:
        content = f.read()
    with open(output_srt, "w", encoding="utf-8") as f:
        f.write(SRT_TIMESTAMP_RE.sub(shift_match, content))


def default_srt_path(video_path: str) -> str:
    base, _ext = os.path.splitext(video_path)
    return f"{base}.srt"


def default_output_path(video_path: str) -> str:
    base, ext = os.path.splitext(video_path)
    return f"{base}_processed{ext or '.mp4'}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", help="Path to the input video file (e.g. .mp4)")
    parser.add_argument("-o", "--output", help="Path for the finished output video (default: INPUT_processed.mp4)")
    parser.add_argument("--srt", help="Path to read/write the .srt file (default: alongside the input video)")
    parser.add_argument("--model-size", default="medium", help="faster-whisper model size (default: medium; try 'small' for speed or 'large-v3' for accuracy)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Device to run transcription on (default: cpu)")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper compute type (default: int8, fastest on CPU)")
    parser.add_argument("--srt-only", action="store_true", help="Only generate the .srt file; skip burning, title screen, and watermark")
    parser.add_argument("--burn-only", action="store_true", help="Skip transcription and use an existing .srt (requires --srt or a .srt already alongside the video)")
    parser.add_argument("--force-transcribe", action="store_true", help="Re-transcribe even if the .srt file already exists")

    parser.add_argument("--title-screen", metavar="IMAGE", help="Prepend a still image (.jpg, .jpeg, .png) as a title card before the video")
    parser.add_argument("--title-hold", type=float, default=5.0, help="Seconds to hold the title screen before the fade begins (default: 5)")
    parser.add_argument("--title-fade", type=float, default=1.5, help="Seconds the crossfade from the title screen into the video takes (default: 1.5)")

    parser.add_argument("--no-watermark", action="store_true", help="Skip overlaying the logo watermark (it's applied by default)")
    parser.add_argument("--watermark-image", default=DEFAULT_WATERMARK_IMAGE, help="Path to the watermark image (default: the Nerd Nite FoCo logo in assets/)")
    parser.add_argument("--watermark-scale", type=float, default=0.08, help="Watermark width as a fraction of the video's width (default: 0.08, i.e. 8%%)")
    parser.add_argument("--watermark-margin", type=float, default=0.02, help="Watermark padding from the corner, as a fraction of the video's width (default: 0.02; use a negative value to let it hang off the edge instead)")
    parser.add_argument("--watermark-position", choices=sorted(WATERMARK_POSITIONS), default="bottom-right", help="Corner to place the watermark in (default: bottom-right)")

    args = parser.parse_args()

    if not os.path.isfile(args.video):
        raise SystemExit(f"Input video not found: {args.video}")
    if args.burn_only and args.srt_only:
        raise SystemExit("--srt-only and --burn-only are mutually exclusive")

    srt_path = args.srt or default_srt_path(args.video)

    if args.burn_only:
        if not os.path.isfile(srt_path):
            raise SystemExit(f".srt file not found for --burn-only: {srt_path}")
    else:
        if os.path.isfile(srt_path) and not args.force_transcribe:
            print(f"Found existing .srt at '{srt_path}', skipping transcription (use --force-transcribe to redo).")
        else:
            generate_srt(
                args.video,
                srt_path,
                model_size=args.model_size,
                device=args.device,
                compute_type=args.compute_type,
            )

    if args.srt_only:
        return

    if args.title_screen:
        if not os.path.isfile(args.title_screen):
            raise SystemExit(f"Title screen image not found: {args.title_screen}")
        if os.path.splitext(args.title_screen)[1].lower() not in VALID_IMAGE_EXTS:
            raise SystemExit("Title screen image must be a .jpg, .jpeg, or .png file")

    apply_watermark = not args.no_watermark
    if apply_watermark:
        if not os.path.isfile(args.watermark_image):
            raise SystemExit(
                f"Watermark image not found: {args.watermark_image}\n"
                "Pass --no-watermark to skip it, or --watermark-image to point at a different file."
            )
        if os.path.splitext(args.watermark_image)[1].lower() not in VALID_IMAGE_EXTS:
            raise SystemExit("Watermark image must be a .jpg, .jpeg, or .png file")

    output_path = args.output or default_output_path(args.video)

    with tempfile.TemporaryDirectory(prefix="process_video_") as tmp_dir:
        current_video = args.video
        current_srt = srt_path

        if args.title_screen:
            titled_video = os.path.join(tmp_dir, "with_title.mp4")
            add_title_image(current_video, args.title_screen, titled_video, args.title_hold, args.title_fade)
            shifted_srt = os.path.join(tmp_dir, "shifted.srt")
            shift_srt(current_srt, shifted_srt, args.title_hold)
            current_video = titled_video
            current_srt = shifted_srt

        subtitled_video = os.path.join(tmp_dir, "subtitled.mp4") if apply_watermark else output_path
        burn_subtitles(current_video, current_srt, subtitled_video)
        current_video = subtitled_video

        if apply_watermark:
            add_watermark(
                current_video,
                args.watermark_image,
                output_path,
                args.watermark_scale,
                args.watermark_margin,
                args.watermark_position,
            )

    print(f"Done -> '{output_path}'")


if __name__ == "__main__":
    main()
