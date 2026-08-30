#!/usr/bin/env python3
"""Prepend a still image to a video: hold it, then crossfade into the video.

Usage:
    python add_title_image.py INPUT.mp4 title_image.png
    python add_title_image.py INPUT.mp4 title_image.jpg -o output.mp4 --hold 5 --fade 1.5

Uses only ffmpeg/ffprobe (already required by process_video.py) - no extra
Python libraries needed.
"""

import argparse
import os
import shutil

from ffmpeg_utils import ffprobe_json, run_ffmpeg

VALID_IMAGE_EXTS = (".jpg", ".jpeg", ".png")


def get_video_info(video_path: str):
    stream_data = ffprobe_json(
        video_path,
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
    )
    stream = stream_data["streams"][0]
    width = int(stream["width"])
    height = int(stream["height"])
    fps = stream["r_frame_rate"]  # e.g. "30/1" or "30000/1001"

    format_data = ffprobe_json(video_path, "-show_entries", "format=duration")
    duration = float(format_data["format"]["duration"])

    audio_data = ffprobe_json(video_path, "-select_streams", "a", "-show_entries", "stream=index")
    has_audio = bool(audio_data.get("streams"))

    return width, height, fps, duration, has_audio


def build_filter_complex(width: int, height: int, fps: str, hold: float, fade: float, has_audio: bool) -> str:
    filters = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[img]",
        f"[1:v]fps={fps},format=yuv420p[vid]",
        f"[img][vid]xfade=transition=fade:duration={fade}:offset={hold}[outv]",
    ]
    if has_audio:
        delay_ms = round(hold * 1000)
        filters.append(f"[1:a]adelay={delay_ms}:all=1[outa]")
    return ";".join(filters)


def add_title_image(video_path: str, image_path: str, output_path: str, hold: float, fade: float) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise SystemExit("ffmpeg/ffprobe not found on PATH. Install ffmpeg and try again.")

    width, height, fps, duration, has_audio = get_video_info(video_path)

    if fade <= 0:
        raise SystemExit("--fade must be greater than 0")
    if fade > duration:
        raise SystemExit(f"--fade ({fade}s) can't be longer than the video itself ({duration:.2f}s)")

    image_clip_duration = hold + fade
    filter_complex = build_filter_complex(width, height, fps, hold, fade, has_audio)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(image_clip_duration), "-i", image_path,
        "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
    ]
    if has_audio:
        cmd += ["-map", "[outa]", "-c:a", "aac"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", output_path]

    run_ffmpeg(cmd, total_duration=hold + duration, label="Rendering title image intro")
    print(f"Wrote video with title image intro -> '{output_path}'")


def default_output_path(video_path: str) -> str:
    base, ext = os.path.splitext(video_path)
    return f"{base}_with_title{ext or '.mp4'}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", help="Path to the input video file (e.g. .mp4)")
    parser.add_argument("image", help="Path to the still image to prepend (.jpg, .jpeg, .png)")
    parser.add_argument("-o", "--output", help="Path for the output video (default: INPUT_with_title.mp4)")
    parser.add_argument("--hold", type=float, default=5.0, help="Seconds to hold the still image before the fade begins (default: 5)")
    parser.add_argument("--fade", type=float, default=1.5, help="Seconds the crossfade into the video takes (default: 1.5)")

    args = parser.parse_args()

    if not os.path.isfile(args.video):
        raise SystemExit(f"Input video not found: {args.video}")
    if not os.path.isfile(args.image):
        raise SystemExit(f"Image not found: {args.image}")
    if os.path.splitext(args.image)[1].lower() not in VALID_IMAGE_EXTS:
        raise SystemExit("Image must be a .jpg, .jpeg, or .png file")

    output_path = args.output or default_output_path(args.video)
    add_title_image(args.video, args.image, output_path, args.hold, args.fade)


if __name__ == "__main__":
    main()
