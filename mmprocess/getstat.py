#!/usr/bin/env python3
"""
FFmpeg encoding status monitor.

Displays progress of active FFmpeg encoding jobs in the work directory.
"""

import argparse
import json
import re
from pathlib import Path

WORK_DIR = Path("/data/media/convert/work")


def parse_ffmpeg_time(time_str: str) -> float:
    """Parse FFmpeg time string (HH:MM:SS.ms) to seconds."""
    match = re.match(r"(\d+):(\d+):(\d+\.?\d*)", time_str)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_ffmpeg_progress(log_path: Path) -> dict | None:
    """
    Parse the last progress line from an FFmpeg log.

    Returns dict with: frame, fps, time, speed, or None if not found.
    """
    if not log_path.exists():
        return None

    # Read chunks from end of file, skipping null bytes (sparse/preallocated files)
    # FFmpeg progress lines are written with carriage returns, so they may not
    # be at the very end of the file
    with open(log_path, "rb") as f:
        f.seek(0, 2)  # End of file
        size = f.tell()

        # Try progressively larger chunks until we find content
        for chunk_size in [8192, 32768, 131072, size]:
            f.seek(max(0, size - chunk_size))
            raw = f.read()

            # Strip null bytes from end (sparse file padding)
            raw = raw.rstrip(b'\x00')
            if len(raw) > 100:  # Need enough content to have a progress line
                break

        content = raw.decode("utf-8", errors="ignore")

    # Try FFmpeg encode format first
    # Format: frame=12345 fps=130 q=25.0 size=N/A time=00:14:51.22 bitrate=N/A speed=5.4x
    ffmpeg_pattern = r"frame=\s*(\d+)\s+fps=\s*([\d.]+)\s+.*time=(\d+:\d+:[\d.]+).*speed=\s*([\d.]+)x"

    last_match = None
    for match in re.finditer(ffmpeg_pattern, content):
        last_match = match

    if last_match:
        return {
            "frame": int(last_match.group(1)),
            "fps": float(last_match.group(2)),
            "time": parse_ffmpeg_time(last_match.group(3)),
            "speed": float(last_match.group(4)),
        }

    # Try FFmpeg copy format (no frame/fps when stream copying)
    # Format: size=  515840kB time=00:28:06.93 bitrate=2505.0kbits/s speed=13.9x
    copy_pattern = r"size=\s*\d+kB\s+time=(\d+:\d+:[\d.]+)\s+bitrate=[\d.]+kbits/s\s+speed=\s*([\d.]+)x"

    last_match = None
    for match in re.finditer(copy_pattern, content):
        last_match = match

    if last_match:
        return {
            "frame": 0,
            "fps": 0,
            "time": parse_ffmpeg_time(last_match.group(1)),
            "speed": float(last_match.group(2)),
        }

    # Try mencoder format (old system)
    # Format: Pos:3669.9s  87992f (95%)  8.79fps Trem:   7min 1528mb  A-V:0.065 [2951:383]
    mencoder_pattern = r"Pos:\s*([\d.]+)s\s+(\d+)f\s+\((\d+)%\)\s+([\d.]+)fps"

    last_match = None
    for match in re.finditer(mencoder_pattern, content):
        last_match = match

    if last_match:
        pos_seconds = float(last_match.group(1))
        fps = float(last_match.group(4))
        # Estimate speed from fps (assuming 24fps source)
        speed = fps / 24.0 if fps > 0 else 1.0

        return {
            "frame": int(last_match.group(2)),
            "fps": fps,
            "time": pos_seconds,
            "speed": speed,
        }

    return None


def load_state(job_dir: Path) -> dict | None:
    """Load state.json from job directory."""
    state_path = job_dir / "state.json"
    if not state_path.exists():
        return None

    with open(state_path) as f:
        return json.load(f)


def find_active_pass(job_dir: Path, state: dict | None = None) -> tuple[int, int, Path] | None:
    """
    Find the currently active pass and its log file.

    Uses state file for pass info when available, falls back to log file detection.

    Returns (current_pass, total_passes, log_path) or None.
    """
    # Get pass info from state if available
    output = state.get("output", {}) if state else {}
    current_pass = output.get("current_pass", 0)
    total_passes = output.get("total_passes", 2)

    # If state has current_pass, use it to find the log file
    if current_pass > 0:
        log_path = job_dir / f"pass{current_pass}.log"
        if log_path.exists():
            return (current_pass, total_passes, log_path)

    # Fallback: detect from log files (for legacy jobs without pass tracking)
    pass2_log = job_dir / "pass2.log"
    if pass2_log.exists():
        return (2, 2, pass2_log)

    pass1_log = job_dir / "pass1.log"
    if pass1_log.exists():
        return (1, 2, pass1_log)

    encode_log = job_dir / "encode.log"
    if encode_log.exists():
        return (1, 1, encode_log)

    return None


def format_time(seconds: float) -> str:
    """Format seconds as human-readable time remaining."""
    if seconds <= 0:
        return ""

    days = int(seconds // 86400)
    seconds -= days * 86400
    hours = int(seconds // 3600)
    seconds -= hours * 3600
    mins = int(seconds // 60)

    parts = []
    if days:
        parts.append(f"{days} Day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} Hour{'s' if hours != 1 else ''}")
    parts.append(f"{mins} Min{'s' if mins != 1 else ''}")

    return "[" + ", ".join(parts) + "]"


def get_job_status(job_dir: Path) -> dict | None:
    """
    Get the status of an encoding job.

    Returns dict with job info or None if not active.
    """
    # Check for lock file (indicates active job)
    lock_file = job_dir.parent / f"{job_dir.name}.lock"
    if not lock_file.exists():
        return None

    state = load_state(job_dir)
    if not state:
        return None

    duration = state.get("input", {}).get("duration", 0)
    if duration <= 0:
        return None

    active_pass = find_active_pass(job_dir, state)
    if not active_pass:
        return None

    pass_num, total_passes, log_path = active_pass
    progress = parse_ffmpeg_progress(log_path)
    if not progress:
        return None

    current_time = progress["time"]
    percent = (current_time / duration) * 100 if duration > 0 else 0

    # Calculate time remaining
    if progress["speed"] > 0:
        remaining_video_time = duration - current_time
        remaining_real_time = remaining_video_time / progress["speed"]

        # If pass 1 of 2, add time for pass 2
        if pass_num == 1 and total_passes == 2:
            remaining_real_time = remaining_real_time + (duration / progress["speed"])
    else:
        remaining_real_time = 0

    return {
        "name": job_dir.name,
        "pass": pass_num,
        "total_passes": total_passes,
        "percent": percent,
        "fps": progress["fps"],
        "speed": progress["speed"],
        "remaining": remaining_real_time,
        "current_time": current_time,
        "duration": duration,
    }


def display_status(jobs: list[dict]) -> None:
    """Display job status in a formatted table."""
    if not jobs:
        print("No active encoding jobs.")
        return

    for job in jobs:
        name = job["name"]
        if len(name) > 40:
            name = name[:37] + "..."

        pass_str = f"pass {job['pass']}/{job['total_passes']}" if job['pass'] > 0 else "encode"
        status = f"{pass_str} {job['percent']:.1f}%"

        time_remaining = format_time(job["remaining"])
        speed_info = f"{job['fps']:.0f}fps {job['speed']:.1f}x"

        print(f"{name:<42} {status:<20} {time_remaining:<30} {speed_info}")


def main():
    parser = argparse.ArgumentParser(description="FFmpeg encoding status monitor")
    parser.add_argument("-w", "--workdir", type=str, default=str(WORK_DIR), help="Work directory")
    args = parser.parse_args()

    work_dir = Path(args.workdir)

    jobs = []

    # Scan work directory for job subdirectories
    if work_dir.exists():
        for entry in sorted(work_dir.iterdir()):
            if entry.is_dir():
                status = get_job_status(entry)
                if status:
                    jobs.append(status)

    display_status(jobs)


if __name__ == "__main__":
    main()
