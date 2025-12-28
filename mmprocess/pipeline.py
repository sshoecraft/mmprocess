"""
Processing pipeline orchestration.

Handles batch and single-file processing modes.
"""

import fcntl
import os
import shutil
import struct
from pathlib import Path

from mmprocess.calculate import calculate_from_profile
from mmprocess.config import Config, Profile, load_profile, profile_exists, select_tier, apply_tier
from mmprocess.encode import create_encode_job, run_encode
from mmprocess.log import logger
from mmprocess.mux import mux
from mmprocess.probe import probe, detect_crop, MediaInfo
from mmprocess.state import JobState, create_state, load_state, save_state, find_cfg_file
from mmprocess.utils import fixfname


# Supported video extensions
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg"}


def is_video_file(path: Path) -> bool:
    """Check if path is a video file based on extension."""
    return path.suffix.lower() in VIDEO_EXTENSIONS


def get_lock_path(job_dir: Path) -> Path:
    """Get lock file path for a job directory."""
    # Use {dirname}.lock alongside the directory (like old mmprocess)
    return job_dir.parent / f"{job_dir.name}.lock"


def acquire_lock(job_dir: Path) -> int | None:
    """
    Acquire an exclusive lock on a job directory.

    Uses POSIX fcntl() locking which works over NFS (unlike BSD flock).

    Args:
        job_dir: Directory to lock

    Returns:
        File descriptor if lock acquired, None if already locked
    """
    lock_path = get_lock_path(job_dir)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        # Use POSIX fcntl locking (works over NFS, unlike flock)
        lock_data = struct.pack('hhllhh', fcntl.F_WRLCK, 0, 0, 0, 0, 0)
        fcntl.fcntl(fd, fcntl.F_SETLK, lock_data)
        return fd
    except (OSError, IOError):
        return None


def release_lock(fd: int, job_dir: Path) -> None:
    """Release a lock on a job directory."""
    try:
        # Unlock using POSIX fcntl
        lock_data = struct.pack('hhllhh', fcntl.F_UNLCK, 0, 0, 0, 0, 0)
        fcntl.fcntl(fd, fcntl.F_SETLK, lock_data)
        os.close(fd)
        lock_path = get_lock_path(job_dir)
        if lock_path.exists():
            lock_path.unlink()
    except (OSError, IOError):
        pass


def determine_profile_name(file_path: Path, config: Config) -> str:
    """
    Determine profile name from file location.

    If file is in a subdirectory of in/, use that subdirectory name.
    Otherwise use the default profile.

    Args:
        file_path: Path to the input file
        config: Application configuration

    Returns:
        Profile name to use
    """
    # Check if file is in a subdirectory of in/
    try:
        relative = file_path.parent.relative_to(config.dirs.input)
        if relative != Path("."):
            # File is in a subdirectory - use that as profile name
            return str(relative.parts[0])
    except ValueError:
        pass

    return config.defaults.profile


def process_file(
    input_path: Path,
    job_dir: Path,
    config: Config,
    profile: Profile,
    state: JobState,
    dry_run: bool = False,
) -> bool:
    """
    Process a single file through the encoding pipeline.

    Args:
        input_path: Path to input file
        job_dir: Directory for job files
        config: Application configuration
        profile: Encoding profile
        state: Job state
        dry_run: If True, only log actions

    Returns:
        True if successful
    """
    # Step 1: Probe input file
    if state.is_enabled("probe") and not state.is_done("probe"):
        logger.info(f"Probing: {input_path.name}")
        try:
            info = probe(input_path, config.tools.ffprobe)

            # Update state with input info
            state.input.format = info.format
            state.input.duration = info.duration

            if info.primary_video:
                video = info.primary_video
                state.input.video_codec = video.codec
                state.input.video_width = video.width
                state.input.video_height = video.height
                state.input.video_fps = video.fps

            if info.primary_audio:
                audio = info.primary_audio
                state.input.audio_codec = audio.codec
                state.input.audio_channels = audio.channels
                state.input.audio_bitrate = audio.bitrate or 0

            state.mark_done("probe")
            save_state(job_dir, state)

        except Exception as e:
            logger.error(f"Probe failed: {e}")
            state.error = str(e)
            save_state(job_dir, state)
            return False
    else:
        # Load info from state
        info = probe(input_path, config.tools.ffprobe)

    # Apply resolution tier overrides (if configured)
    if info.primary_video and profile.tiers:
        input_pixels = info.primary_video.width * info.primary_video.height
        tier = select_tier(profile, input_pixels)
        if tier:
            logger.info(f"Resolution tier: {tier.name} ({input_pixels:,} pixels)")
            apply_tier(profile, tier)

    # Step 2: Crop detection
    crop = None
    if state.is_enabled("crop") and not state.is_done("crop"):
        logger.info(f"Detecting crop: {input_path.name}")
        try:
            crop = detect_crop(
                input_path,
                ffmpeg_path=config.tools.ffmpeg,
                duration=info.duration
            )
            if crop:
                state.output.crop = list(crop)
                logger.info(f"Crop detected: {crop[0]}x{crop[1]}+{crop[2]}+{crop[3]}")
            else:
                logger.info("No crop needed")
            state.mark_done("crop")
            save_state(job_dir, state)
        except Exception as e:
            logger.error(f"Crop detection failed: {e}")
            state.error = str(e)
            save_state(job_dir, state)
            return False
    elif state.output.crop:
        crop = tuple(state.output.crop)

    # Step 3: Calculate scale and bitrate
    try:
        scale, bitrate = calculate_from_profile(info, profile, crop)
        state.output.video_width = scale.width
        state.output.video_height = scale.height
        state.output.video_bitrate = bitrate.video_bitrate
        state.output.video_crf = profile.video.crf
        state.output.audio_bitrate = bitrate.audio_bitrate
        state.output.audio_channels = profile.audio.channels
        state.output.video_codec = profile.video.codec
        state.output.audio_codec = profile.audio.codec
        state.output.container = profile.container or config.defaults.container
        save_state(job_dir, state)
    except Exception as e:
        logger.error(f"Calculation failed: {e}")
        state.error = str(e)
        save_state(job_dir, state)
        return False

    # Determine output container (profile overrides config default)
    container = profile.container or config.defaults.container
    output_ext = f".{container}"

    # Step 4: Encode
    if state.is_enabled("encode") and not state.is_done("encode"):
        # Use temp file during encoding to avoid overwriting input
        # Old system used .avi intermediate; we use .tmp suffix
        temp_output_path = job_dir / f"temp_output{output_ext}"

        # Check for external subtitle file (.srt with same base name)
        external_srt = job_dir / (input_path.stem + ".srt")
        if not external_srt.exists():
            external_srt = None

        try:
            job = create_encode_job(
                input_path=input_path,
                output_path=temp_output_path,
                info=info,
                profile=profile,
                scale=scale,
                bitrate=bitrate,
                crop=crop,
                audio_language=config.defaults.audio_language,
                external_subtitle=external_srt,
            )

            success = run_encode(
                job=job,
                job_dir=job_dir,
                state=state,
                ffmpeg_path=config.tools.ffmpeg,
                dry_run=dry_run,
            )

            if not success:
                state.error = "Encoding failed"
                save_state(job_dir, state)
                return False

            state.mark_done("encode")
            save_state(job_dir, state)

        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            state.error = str(e)
            save_state(job_dir, state)
            return False

    # Step 5: Finalize output - rename temp to final name
    temp_output_path = job_dir / f"temp_output{output_ext}"
    final_output_path = job_dir / (input_path.stem + output_ext)

    if state.is_enabled("mux") and not state.is_done("mux"):
        if temp_output_path.exists():
            if not dry_run:
                # NEVER delete anything - if final path exists, preserve it
                if final_output_path.exists():
                    # Preserve existing file (could be input or previous output)
                    preserved_path = job_dir / (final_output_path.name + ".source")
                    if not preserved_path.exists():
                        final_output_path.rename(preserved_path)
                        logger.info(f"Preserved existing file as: {preserved_path.name}")
                    # If .source already exists, final must be from a previous partial run
                temp_output_path.rename(final_output_path)
            logger.info(f"Output: {final_output_path.name}")

        state.output.path = str(final_output_path)
        state.mark_done("mux")
        save_state(job_dir, state)

    # Step 6: Move to output directory
    if state.is_enabled("move") and not state.is_done("move"):
        if final_output_path.exists():
            dest_path = config.dirs.out / final_output_path.name

            logger.info(f"Moving to output: {dest_path}")

            if not dry_run:
                # Ensure output directory exists
                config.dirs.out.mkdir(parents=True, exist_ok=True)

                # If file exists in output, rename it rather than delete
                if dest_path.exists():
                    backup_path = dest_path.with_suffix(dest_path.suffix + ".old")
                    dest_path.rename(backup_path)
                    logger.info(f"Existing output renamed to: {backup_path.name}")

                shutil.move(str(final_output_path), str(dest_path))

            state.output.path = str(dest_path)
            state.mark_done("move")
            save_state(job_dir, state)

    logger.info(f"Processing complete: {input_path.name}")
    return True


def run_single(
    config: Config,
    file_path: Path,
    profile_name: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Process a single file.

    Args:
        config: Application configuration
        file_path: Path to file to process
        profile_name: Profile to use (or default)
        dry_run: If True, only log actions

    Returns:
        Exit code (0 for success)
    """
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return 1

    # Determine profile
    if not profile_name:
        profile_name = config.defaults.profile

    logger.info(f"Processing: {file_path.name} with profile '{profile_name}'")

    # Load profile
    profile = load_profile(config, profile_name)

    # Create temporary job directory in work/
    job_dir = config.dirs.work / file_path.name
    job_dir.mkdir(parents=True, exist_ok=True)

    # Create state
    state = create_state(
        profile_name=profile_name,
        input_path=file_path,
        crop_enabled=profile.processing.crop,
    )
    save_state(job_dir, state)

    # Process
    try:
        success = process_file(
            input_path=file_path,
            job_dir=job_dir,
            config=config,
            profile=profile,
            state=state,
            dry_run=dry_run,
        )

        if success:
            # Move job dir to done/
            done_dir = config.dirs.done / file_path.name
            if done_dir.exists():
                logger.error(f"Cannot move to done - already exists: {done_dir}")
                return 1
            shutil.move(str(job_dir), str(done_dir))
            return 0
        else:
            # Move job dir to error/
            error_dir = config.dirs.error / file_path.name
            if error_dir.exists():
                logger.error(f"Cannot move to error - already exists: {error_dir}")
                return 1
            shutil.move(str(job_dir), str(error_dir))
            return 1

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        return 1


def _find_work_jobs(config: Config) -> list[Path]:
    """Find existing job directories in work/ that can be resumed."""
    jobs = []
    if config.dirs.work.exists():
        for job_dir in config.dirs.work.iterdir():
            if job_dir.is_dir() and not job_dir.name.startswith("."):
                # Directory name IS the source filename
                # Look for exact match, not any video file (avoids old system .avi intermediates)
                source_file = job_dir / job_dir.name
                if source_file.is_file():
                    jobs.append(job_dir)
    return jobs


def _find_input_files(config: Config) -> list[Path]:
    """Find video files in input directory."""
    files = []

    if not config.dirs.input.exists():
        return files

    # Check loose files in input directory
    for path in config.dirs.input.iterdir():
        if path.is_file() and is_video_file(path):
            files.append(path)

    # Check subdirectories (profile queues)
    # Only include files from subdirectories that have a matching profile
    for subdir in config.dirs.input.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("."):
            # Check if a profile exists for this subdirectory
            if not profile_exists(config, subdir.name):
                logger.debug(f"Skipping subdir (no profile): {subdir.name}")
                continue
            for path in subdir.iterdir():
                if path.is_file() and is_video_file(path):
                    files.append(path)

    return files


def _process_work_job(
    job_dir: Path,
    config: Config,
    dry_run: bool,
) -> bool | None:
    """
    Try to process an existing job in work/.

    Returns:
        True if successful, False if failed, None if couldn't lock
    """
    # Try to acquire lock
    lock_fd = acquire_lock(job_dir)
    if lock_fd is None:
        logger.debug(f"Skipping (locked): {job_dir.name}")
        return None

    try:
        # Directory name IS the source filename
        work_file = job_dir / job_dir.name
        if not work_file.is_file():
            logger.warning(f"Source file not found: {work_file}")
            return False

        # Load state to get profile name (tries state.json, then .cfg)
        state = load_state(job_dir)
        if state is None:
            # No state file - create a new one with default profile
            logger.info(f"Creating new state for: {job_dir.name}")
            profile_name = config.defaults.profile
            profile = load_profile(config, profile_name)
            state = create_state(
                profile_name=profile_name,
                input_path=work_file,
                crop_enabled=profile.processing.crop,
            )
            save_state(job_dir, state)
        else:
            profile_name = state.profile_name or config.defaults.profile
        logger.info(f"Resuming: {work_file.name} with profile '{profile_name}'")

        # Load profile
        profile = load_profile(config, profile_name)

        # Process
        success = process_file(
            input_path=work_file,
            job_dir=job_dir,
            config=config,
            profile=profile,
            state=state,
            dry_run=dry_run,
        )

        if success:
            # Move job dir to done/
            if not dry_run:
                done_dir = config.dirs.done / job_dir.name
                if done_dir.exists():
                    logger.error(f"Cannot move to done - already exists: {done_dir}")
                    return False
                shutil.move(str(job_dir), str(done_dir))
            return True
        else:
            # Move job dir to error/
            if not dry_run:
                error_dir = config.dirs.error / job_dir.name
                if error_dir.exists():
                    logger.error(f"Cannot move to error - already exists: {error_dir}")
                    return False
                shutil.move(str(job_dir), str(error_dir))
            return False

    finally:
        release_lock(lock_fd, job_dir)


def _process_input_file(
    file_path: Path,
    config: Config,
    dry_run: bool,
) -> bool | None:
    """
    Process a file from input directory.

    Returns:
        True if successful, False if failed, None if couldn't lock
    """
    # Determine profile from directory
    profile_name = determine_profile_name(file_path, config)

    # Normalize filename
    fixed_name = fixfname(file_path.name)

    # Create job directory in work/ (using normalized name)
    job_dir = config.dirs.work / fixed_name
    job_dir.mkdir(parents=True, exist_ok=True)

    # Try to acquire lock
    lock_fd = acquire_lock(job_dir)
    if lock_fd is None:
        logger.debug(f"Skipping (locked): {fixed_name}")
        return None

    try:
        if fixed_name != file_path.name:
            logger.info(f"Renamed: {file_path.name} -> {fixed_name}")
        logger.info(f"Processing: {fixed_name} with profile '{profile_name}'")

        # Move file to job directory (with normalized name)
        work_file = job_dir / fixed_name
        if not dry_run:
            shutil.move(str(file_path), str(work_file))

            # Check for external .srt file with same base name
            srt_file = file_path.with_suffix(".srt")
            if srt_file.exists():
                # Normalize .srt filename to match video
                fixed_srt = fixfname(srt_file.name)
                work_srt = job_dir / fixed_srt
                shutil.move(str(srt_file), str(work_srt))
                logger.info(f"Found external subtitle: {srt_file.name}")
        else:
            work_file = file_path

        # Load profile
        profile = load_profile(config, profile_name)

        # Create state
        state = create_state(
            profile_name=profile_name,
            input_path=work_file,
            crop_enabled=profile.processing.crop,
        )
        save_state(job_dir, state)

        # Process
        success = process_file(
            input_path=work_file,
            job_dir=job_dir,
            config=config,
            profile=profile,
            state=state,
            dry_run=dry_run,
        )

        if success:
            # Move job dir to done/
            if not dry_run:
                done_dir = config.dirs.done / fixed_name
                if done_dir.exists():
                    logger.error(f"Cannot move to done - already exists: {done_dir}")
                    return False
                shutil.move(str(job_dir), str(done_dir))
            return True
        else:
            # Move job dir to error/
            if not dry_run:
                error_dir = config.dirs.error / fixed_name
                if error_dir.exists():
                    logger.error(f"Cannot move to error - already exists: {error_dir}")
                    return False
                shutil.move(str(job_dir), str(error_dir))
            return False

    finally:
        release_lock(lock_fd, job_dir)


def run_batch(config: Config, dry_run: bool = False) -> int:
    """
    Run batch processing mode.

    Priority order:
    1. First try to resume existing jobs in work/
    2. If no work jobs available, take files from in/

    Args:
        config: Application configuration
        dry_run: If True, only log actions

    Returns:
        Exit code (0 for success, 1 if any errors)
    """
    # Ensure directories exist
    for dir_path in [config.dirs.input, config.dirs.work, config.dirs.done,
                     config.dirs.out, config.dirs.error]:
        dir_path.mkdir(parents=True, exist_ok=True)

    errors = 0
    processed = 0

    # Phase 1: Try to resume existing work jobs first
    work_jobs = _find_work_jobs(config)
    if work_jobs:
        logger.info(f"Found {len(work_jobs)} job(s) in work/")

        for job_dir in work_jobs:
            result = _process_work_job(job_dir, config, dry_run)
            if result is True:
                processed += 1
                # After processing one, exit (one job per invocation)
                # This allows multiple instances to grab different jobs
                break
            elif result is False:
                errors += 1
                break
            # result is None means locked, try next

    # Phase 2: If we didn't process anything from work, check input
    if processed == 0 and errors == 0:
        input_files = _find_input_files(config)

        if input_files:
            logger.info(f"Found {len(input_files)} file(s) in input/")

            for file_path in input_files:
                result = _process_input_file(file_path, config, dry_run)
                if result is True:
                    processed += 1
                    break
                elif result is False:
                    errors += 1
                    break
                # result is None means locked, try next

    if processed == 0 and errors == 0:
        logger.info("No files to process")

    if errors > 0:
        logger.warning(f"Completed with {errors} error(s)")
        return 1

    if processed > 0:
        logger.info("Batch processing complete")

    return 0
