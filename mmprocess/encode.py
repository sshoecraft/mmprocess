"""
FFmpeg encoding execution.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from mmprocess.calculate import BitrateResult, ScaleResult
from mmprocess.config import Profile
from mmprocess.filters import FilterChain, build_video_filters
from mmprocess.log import logger, get_job_logger
from mmprocess.probe import MediaInfo
from mmprocess.state import JobState, save_state


@dataclass
class AudioTrack:
    """Represents an output audio track configuration."""
    channels: int  # 2 for stereo, 6 for 5.1
    bitrate: int  # kbps
    title: str = ""  # Track title metadata


@dataclass
class EncodeJob:
    """Represents an encoding job configuration."""
    input_path: Path
    output_path: Path
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: int | None = None  # kbps, None for CRF mode
    crf: int | None = None  # Constant rate factor (quality mode)
    video_filters: FilterChain | None = None
    passes: int = 2
    container: str = "mp4"
    extra_video_opts: list[str] | None = None
    audio_stream_index: int | None = None  # Specific audio stream to use
    title: str | None = None  # Output title metadata
    audio_tracks: list[AudioTrack] | None = None  # Output audio tracks


def build_ffmpeg_command(
    job: EncodeJob,
    pass_num: int = 0,
    pass_log_prefix: str = "ffmpeg2pass",
    ffmpeg_path: str = "ffmpeg",
) -> list[str]:
    """
    Build FFmpeg command for encoding.

    Args:
        job: Encoding job configuration
        pass_num: Pass number (0 for single-pass, 1 or 2 for multi-pass)
        pass_log_prefix: Prefix for pass log files
        ffmpeg_path: Path to ffmpeg executable

    Returns:
        List of command arguments
    """
    cmd = [ffmpeg_path, "-y"]  # -y to overwrite output

    # Input
    cmd.extend(["-i", str(job.input_path)])

    # Force constant frame rate to avoid pass 1/2 frame count mismatch
    cmd.extend(["-vsync", "cfr"])

    # Stream mapping
    cmd.extend(["-map", "0:v:0"])  # First video stream

    # Audio mapping - skip on first pass of multi-pass
    if pass_num != 1 and job.audio_tracks:
        # Map audio stream once per output track
        audio_src = f"0:{job.audio_stream_index}" if job.audio_stream_index is not None else "0:a:0"
        for _ in job.audio_tracks:
            cmd.extend(["-map", audio_src])

    # Video codec
    if job.video_codec == "copy":
        cmd.extend(["-c:v", "copy"])
    else:
        cmd.extend(["-c:v", job.video_codec])

        # Force 8-bit output for compatibility (QuickTime doesn't support 10-bit H.264)
        cmd.extend(["-pix_fmt", "yuv420p"])

        # Use hvc1 tag for HEVC (required for QuickTime/Apple compatibility)
        if job.video_codec == "libx265":
            cmd.extend(["-tag:v", "hvc1"])

        # Video filters
        if job.video_filters:
            vf = job.video_filters.build()
            if vf:
                cmd.extend(["-vf", vf])

        # Rate control
        if job.crf is not None:
            # CRF mode (quality-based)
            cmd.extend(["-crf", str(job.crf)])
        elif job.video_bitrate:
            # Bitrate mode
            cmd.extend(["-b:v", f"{job.video_bitrate}k"])

        # Multi-pass
        if pass_num > 0:
            cmd.extend(["-pass", str(pass_num)])
            cmd.extend(["-passlogfile", pass_log_prefix])

            # First pass optimizations
            if pass_num == 1:
                cmd.extend(["-f", "null"])  # Null output

        # Extra video options
        if job.extra_video_opts:
            cmd.extend(job.extra_video_opts)

    # Audio encoding (skip on first pass of multi-pass)
    # We use a single audio track matching the source (5.1 or stereo)
    if pass_num != 1 and job.audio_tracks:
        track = job.audio_tracks[0]  # Single track
        cmd.extend(["-c:a", job.audio_codec])
        cmd.extend(["-ac", str(track.channels)])
        cmd.extend(["-b:a", f"{track.bitrate}k"])

        # Force correct channel layout for QuickTime compatibility
        # QuickTime requires standard 5.1 layout (L R C LFE Ls Rs)
        if track.channels == 6:
            cmd.extend(["-af", "channelmap=channel_layout=5.1"])

        if track.title:
            cmd.extend(["-metadata:s:a:0", f"title={track.title}"])

        # Add movflags for MP4 streaming compatibility (Roku)
        if job.container == "mp4":
            cmd.extend(["-movflags", "+faststart"])

    # Metadata - set title to output filename without extension
    if job.title and pass_num != 1:
        cmd.extend(["-metadata", f"title={job.title}"])

    # Output
    if pass_num == 1:
        # First pass writes to null output (using - for cross-platform compatibility)
        cmd.append("-")
    else:
        cmd.append(str(job.output_path))

    return cmd


def _run_ffmpeg(
    cmd: list[str],
    log_path: Path,
) -> tuple[bool, str]:
    """
    Run FFmpeg and capture output to log file.

    Args:
        cmd: FFmpeg command
        log_path: Path to write log file

    Returns:
        Tuple of (success, last_error_lines)
    """
    with open(log_path, "w") as log_file:
        log_file.write(f"Command: {' '.join(cmd)}\n\n")

        result = subprocess.run(
            cmd,
            stdout=log_file,
            stderr=log_file,
            text=True,
        )

    # Read last lines for error reporting
    with open(log_path, "r") as f:
        lines = f.readlines()
        last_lines = lines[-20:] if len(lines) > 20 else lines

    return result.returncode == 0, "".join(last_lines)


def run_encode(
    job: EncodeJob,
    job_dir: Path,
    state: JobState | None = None,
    ffmpeg_path: str = "ffmpeg",
    dry_run: bool = False,
) -> bool:
    """
    Run the encoding job.

    Args:
        job: Encoding job configuration
        job_dir: Directory for job files (logs, pass files)
        state: Job state for pass tracking (optional)
        ffmpeg_path: Path to ffmpeg executable
        dry_run: If True, only log commands without executing

    Returns:
        True if successful, False otherwise
    """
    pass_log_prefix = str(job_dir / "ffmpeg2pass")

    if job.passes == 1 or job.crf is not None:
        # Single pass encoding (or CRF mode)
        if state:
            state.output.total_passes = 1
            state.output.current_pass = 1
            save_state(job_dir, state)

        cmd = build_ffmpeg_command(job, pass_num=0, ffmpeg_path=ffmpeg_path)
        logger.info(f"Encoding (single pass): {job.input_path.name}")
        logger.debug(f"Command: {' '.join(cmd)}")

        if dry_run:
            logger.info("[DRY RUN] Would execute: " + " ".join(cmd))
            return True

        log_path = job_dir / "pass1.log"
        success, last_lines = _run_ffmpeg(cmd, log_path)

        if not success:
            logger.error(f"Encoding failed: {last_lines[-500:]}")
            return False

        return True

    else:
        # Multi-pass encoding
        if state:
            state.output.total_passes = job.passes
            save_state(job_dir, state)

        # Determine starting pass (resume from where we left off)
        start_pass = 1
        if state and state.output.current_pass > 0:
            # current_pass tracks the pass we're ON, so resume from there
            start_pass = state.output.current_pass

        for pass_num in range(start_pass, job.passes + 1):
            # Update state before starting this pass
            if state:
                state.output.current_pass = pass_num
                save_state(job_dir, state)

            cmd = build_ffmpeg_command(
                job,
                pass_num=pass_num,
                pass_log_prefix=pass_log_prefix,
                ffmpeg_path=ffmpeg_path
            )

            logger.info(f"Encoding pass {pass_num}/{job.passes}: {job.input_path.name}")
            logger.debug(f"Command: {' '.join(cmd)}")

            if dry_run:
                logger.info(f"[DRY RUN] Would execute pass {pass_num}: " + " ".join(cmd))
                continue

            log_path = job_dir / f"pass{pass_num}.log"
            success, last_lines = _run_ffmpeg(cmd, log_path)

            if not success:
                logger.error(f"Pass {pass_num} failed: {last_lines[-500:]}")
                return False

        return True


def create_encode_job(
    input_path: Path,
    output_path: Path,
    info: MediaInfo,
    profile: Profile,
    scale: ScaleResult,
    bitrate: BitrateResult,
    crop: tuple[int, int, int, int] | None = None,
    audio_language: str = "eng",
    external_subtitle: Path | None = None,
) -> EncodeJob:
    """
    Create an encoding job from profile and calculated parameters.

    Args:
        input_path: Source file path
        output_path: Output file path
        info: Media information
        profile: Encoding profile
        scale: Calculated scale parameters
        bitrate: Calculated bitrate parameters
        crop: Crop parameters (w, h, x, y)
        audio_language: Preferred audio language (ISO 639 code)
        external_subtitle: Path to external .srt file (overrides embedded)

    Returns:
        Configured EncodeJob
    """
    # Determine subtitle source: external .srt takes priority over embedded
    subtitle_path = None
    subtitle_stream_index = None

    if profile.processing.subtitles:
        if external_subtitle and external_subtitle.exists():
            subtitle_path = str(external_subtitle)
            subtitle_stream_index = None  # External .srt doesn't need stream index
            logger.info(f"Using external subtitle: {external_subtitle.name}")
        else:
            # Check for embedded forced subtitle track
            forced_sub = info.get_forced_subtitle()
            if forced_sub:
                subtitle_path = str(input_path)
                subtitle_stream_index = forced_sub.index
                logger.info(f"Found forced subtitle track {forced_sub.index} ({forced_sub.codec})")
    else:
        logger.info("Subtitle burn-in disabled by profile")

    # Build video filters (including subtitle burn-in if subs found)
    video_filters = build_video_filters(
        crop=crop,
        scale=(scale.width, scale.height) if scale.scaled else None,
        deinterlace=profile.processing.deinterlace,
        denoise=profile.processing.denoise,
        subtitle_path=subtitle_path,
        subtitle_stream_index=subtitle_stream_index,
    )

    # Select audio stream by language preference
    selected_audio = info.get_audio_by_language(audio_language)
    audio_stream_index = selected_audio.index if selected_audio else None

    if selected_audio:
        logger.debug(f"Selected audio stream {selected_audio.index}: "
                     f"{selected_audio.language or 'unknown'}, "
                     f"{selected_audio.channels}ch")

    # Build single audio track matching source channels
    audio_tracks = []
    if selected_audio:
        source_channels = selected_audio.channels

        if source_channels >= 6:
            # Source has 5.1 - output 5.1
            audio_tracks = [
                AudioTrack(channels=6, bitrate=profile.audio.bitrate, title=""),
            ]
            logger.debug(f"Creating 5.1 audio track at {profile.audio.bitrate}k")
        else:
            # Source is stereo or mono - output stereo
            # Use 128k for stereo (sufficient for AAC)
            audio_tracks = [
                AudioTrack(channels=2, bitrate=128, title=""),
            ]
            logger.debug("Creating stereo audio track at 128k")

    # Determine passes
    # Stream copy = 1 pass (no encoding)
    # CRF mode = 1 pass (quality-based)
    # Bitrate mode = 2 pass (for better quality)
    if profile.video.codec == "copy":
        passes = 1
    elif profile.video.crf is not None:
        passes = 1
    elif bitrate.video_bitrate > 0:
        passes = 2
    else:
        passes = 1

    # Title is input filename without extension (not temp output path)
    title = input_path.stem

    return EncodeJob(
        input_path=input_path,
        output_path=output_path,
        video_codec=profile.video.codec,
        audio_codec=profile.audio.codec,
        video_bitrate=bitrate.video_bitrate if bitrate.video_bitrate > 0 else None,
        crf=profile.video.crf,
        video_filters=video_filters,
        passes=passes,
        audio_stream_index=audio_stream_index,
        title=title,
        audio_tracks=audio_tracks,
    )
