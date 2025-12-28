"""
Container muxing operations.
"""

import subprocess
from pathlib import Path

from mmprocess.log import logger, get_job_logger


def remux_to_mkv(
    input_path: Path,
    output_path: Path,
    job_dir: Path,
    mkvmerge_path: str = "mkvmerge",
    dry_run: bool = False,
) -> bool:
    """
    Remux to MKV container using mkvmerge.

    Args:
        input_path: Source file path
        output_path: Output file path
        job_dir: Directory for job logs
        mkvmerge_path: Path to mkvmerge executable
        dry_run: If True, only log commands

    Returns:
        True if successful
    """
    cmd = [
        mkvmerge_path,
        "-o", str(output_path),
        str(input_path)
    ]

    logger.info(f"Muxing to MKV: {output_path.name}")
    logger.debug(f"Command: {' '.join(cmd)}")

    if dry_run:
        logger.info("[DRY RUN] Would execute: " + " ".join(cmd))
        return True

    job_logger = get_job_logger(job_dir, "mux")
    job_logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    job_logger.info(result.stdout)
    if result.stderr:
        job_logger.info(result.stderr)

    if result.returncode != 0:
        logger.error(f"Muxing failed: {result.stderr[-500:]}")
        return False

    return True


def remux_to_mp4(
    input_path: Path,
    output_path: Path,
    job_dir: Path,
    mp4box_path: str = "MP4Box",
    fps: float | None = None,
    dry_run: bool = False,
) -> bool:
    """
    Remux to MP4 container using MP4Box.

    Args:
        input_path: Source file path
        output_path: Output file path
        job_dir: Directory for job logs
        mp4box_path: Path to MP4Box executable
        fps: Frame rate (required for some inputs)
        dry_run: If True, only log commands

    Returns:
        True if successful
    """
    cmd = [mp4box_path]

    # Add input with optional fps
    if fps:
        cmd.extend(["-fps", str(fps)])
    cmd.extend(["-add", str(input_path)])

    # Add output
    cmd.extend(["-new", str(output_path)])

    logger.info(f"Muxing to MP4: {output_path.name}")
    logger.debug(f"Command: {' '.join(cmd)}")

    if dry_run:
        logger.info("[DRY RUN] Would execute: " + " ".join(cmd))
        return True

    job_logger = get_job_logger(job_dir, "mux")
    job_logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    job_logger.info(result.stdout)
    if result.stderr:
        job_logger.info(result.stderr)

    if result.returncode != 0:
        logger.error(f"Muxing failed: {result.stderr[-500:]}")
        return False

    return True


def remux_ffmpeg(
    input_path: Path,
    output_path: Path,
    job_dir: Path,
    ffmpeg_path: str = "ffmpeg",
    container: str = "mkv",
    dry_run: bool = False,
) -> bool:
    """
    Remux using FFmpeg (stream copy).

    Args:
        input_path: Source file path
        output_path: Output file path
        job_dir: Directory for job logs
        ffmpeg_path: Path to ffmpeg executable
        container: Output container format
        dry_run: If True, only log commands

    Returns:
        True if successful
    """
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(input_path),
        "-c", "copy",  # Copy all streams
        str(output_path)
    ]

    logger.info(f"Remuxing to {container.upper()}: {output_path.name}")
    logger.debug(f"Command: {' '.join(cmd)}")

    if dry_run:
        logger.info("[DRY RUN] Would execute: " + " ".join(cmd))
        return True

    job_logger = get_job_logger(job_dir, "mux")
    job_logger.info(f"Command: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    job_logger.info(result.stdout)
    if result.stderr:
        job_logger.info(result.stderr)

    if result.returncode != 0:
        logger.error(f"Remuxing failed: {result.stderr[-500:]}")
        return False

    return True


def mux(
    input_path: Path,
    output_path: Path,
    job_dir: Path,
    container: str,
    ffmpeg_path: str = "ffmpeg",
    mkvmerge_path: str = "mkvmerge",
    mp4box_path: str = "MP4Box",
    fps: float | None = None,
    dry_run: bool = False,
) -> bool:
    """
    Mux input to specified container format.

    Selects appropriate tool based on container:
    - MKV: Uses mkvmerge if available, otherwise ffmpeg
    - MP4: Uses MP4Box if available, otherwise ffmpeg
    - Other: Uses ffmpeg

    Args:
        input_path: Source file path
        output_path: Output file path
        job_dir: Directory for job logs
        container: Target container format (mkv, mp4)
        ffmpeg_path: Path to ffmpeg
        mkvmerge_path: Path to mkvmerge
        mp4box_path: Path to MP4Box
        fps: Frame rate (for MP4Box)
        dry_run: If True, only log commands

    Returns:
        True if successful
    """
    container = container.lower()

    if container == "mkv":
        # Try mkvmerge first
        try:
            result = subprocess.run(
                [mkvmerge_path, "--version"],
                capture_output=True
            )
            if result.returncode == 0:
                return remux_to_mkv(
                    input_path, output_path, job_dir,
                    mkvmerge_path=mkvmerge_path, dry_run=dry_run
                )
        except FileNotFoundError:
            pass

        # Fall back to ffmpeg
        return remux_ffmpeg(
            input_path, output_path, job_dir,
            ffmpeg_path=ffmpeg_path, container=container, dry_run=dry_run
        )

    elif container == "mp4":
        # Try MP4Box first
        try:
            result = subprocess.run(
                [mp4box_path, "-version"],
                capture_output=True
            )
            if result.returncode == 0:
                return remux_to_mp4(
                    input_path, output_path, job_dir,
                    mp4box_path=mp4box_path, fps=fps, dry_run=dry_run
                )
        except FileNotFoundError:
            pass

        # Fall back to ffmpeg
        return remux_ffmpeg(
            input_path, output_path, job_dir,
            ffmpeg_path=ffmpeg_path, container=container, dry_run=dry_run
        )

    else:
        # Use ffmpeg for other containers
        return remux_ffmpeg(
            input_path, output_path, job_dir,
            ffmpeg_path=ffmpeg_path, container=container, dry_run=dry_run
        )
