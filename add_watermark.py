#!/usr/bin/env python3
"""Overlay a logo watermark in a corner of a video for its entire duration.

Usage:
    python add_watermark.py INPUT.mp4 logo.png
    python add_watermark.py INPUT.mp4 logo.png -o OUTPUT.mp4 --scale 0.1 --margin -0.015

Uses only ffmpeg - no extra Python libraries needed. The watermark is sized
relative to the video's width (via ffmpeg's scale2ref filter) so it scales
correctly regardless of the video's resolution.
"""

import argparse
import os
import shutil
import subprocess

VALID_IMAGE_EXTS = (".jpg", ".jpeg", ".png")

# {margin} is substituted with an expression for the margin in pixels.
# A positive margin pads the watermark inward from the edge; a negative
# margin lets it hang off the edge slightly.
POSITIONS = {
    "bottom-right": ("W-w-({margin})", "H-h-({margin})"),
    "bottom-left": ("({margin})", "H-h-({margin})"),
    "top-right": ("W-w-({margin})", "({margin})"),
    "top-left": ("({margin})", "({margin})"),
}


def add_watermark(
    video_path: str,
    logo_path: str,
    output_path: str,
    scale: float,
    margin: float,
    position: str,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH. Install it and try again.")

    x_template, y_template = POSITIONS[position]
    # In the overlay filter (below), W/H are the main video's dimensions.
    margin_expr = f"W*{margin}"
    x_expr = x_template.format(margin=margin_expr)
    y_expr = y_template.format(margin=margin_expr)

    # In scale2ref (below), iw/ih refer to the *reference* stream (the video,
    # listed second) and mdar refers to the stream being scaled (the logo).
    filter_complex = (
        f"[1:v][0:v]scale2ref=w='iw*{scale}':h='ow/mdar'[wm][base];"
        f"[base][wm]overlay=x='{x_expr}':y='{y_expr}'[outv]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", logo_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:a", "copy",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        output_path,
    ]

    print("Overlaying watermark with ffmpeg...")
    subprocess.run(cmd, check=True)
    print(f"Wrote watermarked video -> '{output_path}'")


def default_output_path(video_path: str) -> str:
    base, ext = os.path.splitext(video_path)
    return f"{base}_watermarked{ext or '.mp4'}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", help="Path to the input video file (e.g. .mp4)")
    parser.add_argument("logo", help="Path to the watermark image (.jpg, .jpeg, .png; PNG with transparency recommended)")
    parser.add_argument("-o", "--output", help="Path for the output video (default: INPUT_watermarked.mp4)")
    parser.add_argument("--scale", type=float, default=0.10, help="Watermark width as a fraction of the video's width (default: 0.10, i.e. 10%%)")
    parser.add_argument("--margin", type=float, default=-0.015, help="Margin from the corner, as a fraction of the video's width (default: -0.015, a small overlap off the edge; use a positive value to pad inward)")
    parser.add_argument("--position", choices=sorted(POSITIONS), default="bottom-right", help="Corner to place the watermark in (default: bottom-right)")

    args = parser.parse_args()

    if not os.path.isfile(args.video):
        raise SystemExit(f"Input video not found: {args.video}")
    if not os.path.isfile(args.logo):
        raise SystemExit(f"Logo image not found: {args.logo}")
    if os.path.splitext(args.logo)[1].lower() not in VALID_IMAGE_EXTS:
        raise SystemExit("Logo must be a .jpg, .jpeg, or .png file")
    if not 0 < args.scale < 1:
        raise SystemExit("--scale must be between 0 and 1")

    output_path = args.output or default_output_path(args.video)
    add_watermark(args.video, args.logo, output_path, args.scale, args.margin, args.position)


if __name__ == "__main__":
    main()
