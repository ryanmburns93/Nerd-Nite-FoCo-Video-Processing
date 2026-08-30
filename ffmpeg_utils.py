"""Shared helpers for running ffmpeg with a live progress indicator."""

import json
import subprocess
import sys


def ffprobe_json(path: str, *args: str) -> dict:
    cmd = ["ffprobe", "-v", "error", "-of", "json", *args, path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_duration(path: str) -> float:
    data = ffprobe_json(path, "-show_entries", "format=duration")
    return float(data["format"]["duration"])


def print_progress_bar(label: str, fraction: float) -> None:
    fraction = max(0.0, min(1.0, fraction))
    bar_width = 30
    filled = int(bar_width * fraction)
    bar = "#" * filled + "-" * (bar_width - filled)
    sys.stdout.write(f"\r{label} [{bar}] {fraction * 100:5.1f}%")
    sys.stdout.flush()


def run_ffmpeg(cmd: list, total_duration: float, label: str = "Processing") -> None:
    """Run an ffmpeg command while printing a live progress bar.

    cmd must be a full ffmpeg command list starting with "ffmpeg" and ending
    with the output path, as built by the caller (e.g. including -y and any
    -filter_complex/-map options). total_duration is the expected duration
    in seconds of the output, used to turn ffmpeg's own -progress output
    into a percentage.
    """
    progress_cmd = [cmd[0], "-progress", "pipe:1", "-nostats", "-loglevel", "error"] + cmd[1:]

    process = subprocess.Popen(
        progress_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    out_time_seconds = 0.0
    for line in process.stdout:
        key, _, value = line.strip().partition("=")
        if key == "out_time_us" and value not in ("", "N/A"):
            out_time_seconds = int(value) / 1_000_000
        if total_duration > 0:
            print_progress_bar(label, out_time_seconds / total_duration)

    stderr_output = process.stderr.read()
    returncode = process.wait()
    print_progress_bar(label, 1.0)
    sys.stdout.write("\n")

    if returncode != 0:
        sys.stderr.write(stderr_output)
        raise subprocess.CalledProcessError(returncode, progress_cmd)
