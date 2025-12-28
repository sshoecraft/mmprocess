"""
Media file analysis using ffprobe.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mmprocess.log import logger


@dataclass
class VideoStream:
    """Video stream information."""
    index: int
    codec: str
    width: int
    height: int
    fps: float
    duration: float
    bitrate: int | None = None
    pixel_format: str = ""
    display_aspect_ratio: str = ""


@dataclass
class AudioStream:
    """Audio stream information."""
    index: int
    codec: str
    channels: int
    sample_rate: int
    bitrate: int | None = None
    language: str = ""


@dataclass
class SubtitleStream:
    """Subtitle stream information."""
    index: int
    codec: str
    language: str = ""
    forced: bool = False


@dataclass
class MediaInfo:
    """Complete media file information."""
    path: Path
    format: str
    duration: float
    size: int
    bitrate: int
    video: list[VideoStream]
    audio: list[AudioStream]
    subtitles: list[SubtitleStream]

    @property
    def primary_video(self) -> VideoStream | None:
        """Get the primary (first) video stream."""
        return self.video[0] if self.video else None

    @property
    def primary_audio(self) -> AudioStream | None:
        """Get the primary (first) audio stream."""
        return self.audio[0] if self.audio else None

    def get_forced_subtitle(self) -> SubtitleStream | None:
        """Get the forced subtitle track if one exists."""
        for sub in self.subtitles:
            if sub.forced:
                return sub
        return None

    def get_audio_by_language(self, preferred_lang: str) -> AudioStream | None:
        """
        Get best audio stream by preferred language.

        Prefers 5.1 (6 channels) over stereo when multiple tracks exist.
        Falls back to track with most channels if preferred language not found.

        Args:
            preferred_lang: ISO 639 language code (e.g., 'eng', 'ita', 'hin')

        Returns:
            Best matching audio stream, or None
        """
        if not self.audio:
            return None

        # Find all tracks matching preferred language
        lang_matches = [
            s for s in self.audio
            if s.language.lower() == preferred_lang.lower()
        ]

        if lang_matches:
            # Return the one with most channels (prefer 5.1 over stereo)
            return max(lang_matches, key=lambda s: s.channels)

        # No language match - return track with most channels
        return max(self.audio, key=lambda s: s.channels)


def parse_fps(fps_str: str) -> float:
    """Parse frame rate string (e.g., '24000/1001' or '25')."""
    if "/" in fps_str:
        num, den = fps_str.split("/")
        return float(num) / float(den)
    return float(fps_str)


def probe(file_path: Path, ffprobe_path: str = "ffprobe") -> MediaInfo:
    """
    Probe a media file using ffprobe.

    Args:
        file_path: Path to the media file
        ffprobe_path: Path to ffprobe executable

    Returns:
        MediaInfo object with parsed media information

    Raises:
        subprocess.CalledProcessError: If ffprobe fails
        json.JSONDecodeError: If output cannot be parsed
    """
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]

    logger.debug(f"Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)

    # Parse format information
    fmt = data.get("format", {})
    format_name = fmt.get("format_name", "").split(",")[0]
    duration = float(fmt.get("duration", 0))
    size = int(fmt.get("size", 0))
    bitrate = int(fmt.get("bit_rate", 0))

    # Parse streams
    video_streams: list[VideoStream] = []
    audio_streams: list[AudioStream] = []
    subtitle_streams: list[SubtitleStream] = []

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        index = stream.get("index", 0)

        if codec_type == "video":
            # Parse frame rate
            fps_str = stream.get("r_frame_rate", "0/1")
            fps = parse_fps(fps_str)

            # Get stream duration or fall back to format duration
            stream_duration = float(stream.get("duration", duration))

            video_streams.append(VideoStream(
                index=index,
                codec=stream.get("codec_name", "unknown"),
                width=stream.get("width", 0),
                height=stream.get("height", 0),
                fps=fps,
                duration=stream_duration,
                bitrate=int(stream["bit_rate"]) if "bit_rate" in stream else None,
                pixel_format=stream.get("pix_fmt", ""),
                display_aspect_ratio=stream.get("display_aspect_ratio", ""),
            ))

        elif codec_type == "audio":
            # Get language from tags
            tags = stream.get("tags", {})
            language = tags.get("language", "")

            audio_streams.append(AudioStream(
                index=index,
                codec=stream.get("codec_name", "unknown"),
                channels=stream.get("channels", 0),
                sample_rate=int(stream.get("sample_rate", 0)),
                bitrate=int(stream["bit_rate"]) if "bit_rate" in stream else None,
                language=language,
            ))

        elif codec_type == "subtitle":
            tags = stream.get("tags", {})
            disposition = stream.get("disposition", {})

            subtitle_streams.append(SubtitleStream(
                index=len(subtitle_streams),  # Subtitle-relative index for FFmpeg si= filter
                codec=stream.get("codec_name", "unknown"),
                language=tags.get("language", ""),
                forced=disposition.get("forced", 0) == 1,
            ))

    return MediaInfo(
        path=file_path,
        format=format_name,
        duration=duration,
        size=size,
        bitrate=bitrate,
        video=video_streams,
        audio=audio_streams,
        subtitles=subtitle_streams,
    )


def detect_crop(
    file_path: Path,
    ffmpeg_path: str = "ffmpeg",
    duration: float = 0,
    samples: int = 10,
    sample_duration: float = 2.0
) -> tuple[int, int, int, int] | None:
    """
    Detect black borders using ffmpeg cropdetect filter.

    Args:
        file_path: Path to the media file
        ffmpeg_path: Path to ffmpeg executable
        duration: Total duration of the file (for sample positioning)
        samples: Number of samples to analyze
        sample_duration: Duration of each sample in seconds

    Returns:
        Tuple of (width, height, x, y) for crop, or None if no crop needed
    """
    if duration <= 0:
        # Need to probe first to get duration
        info = probe(file_path)
        duration = info.duration

    # Calculate sample positions (skip first and last 10%)
    start_pct = 0.1
    end_pct = 0.9
    usable_duration = duration * (end_pct - start_pct)
    interval = usable_duration / samples if samples > 1 else usable_duration

    crops: list[tuple[int, int, int, int]] = []

    for i in range(samples):
        start_time = duration * start_pct + (i * interval)

        cmd = [
            ffmpeg_path,
            "-ss", str(start_time),
            "-i", str(file_path),
            "-t", str(sample_duration),
            "-vf", "cropdetect=24:16:0",
            "-f", "null",
            "-"
        ]

        logger.debug(f"Crop detection sample {i+1}/{samples} at {start_time:.1f}s")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        # Parse cropdetect output from stderr
        for line in result.stderr.split("\n"):
            if "crop=" in line:
                # Extract crop=W:H:X:Y
                crop_part = line.split("crop=")[1].split()[0]
                parts = crop_part.split(":")
                if len(parts) == 4:
                    w, h, x, y = map(int, parts)
                    crops.append((w, h, x, y))

    if not crops:
        return None

    # Find the most common crop (mode)
    from collections import Counter
    crop_counter = Counter(crops)
    most_common = crop_counter.most_common(1)[0][0]

    return most_common
