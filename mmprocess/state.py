"""
Job state persistence.

Tracks processing state for each file, enabling resume capability.

Supports loading from:
1. state.json (new format)
2. {filename}.cfg (old mmprocess INI format) - source of truth
"""

import configparser
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ProcessingSteps:
    """Tracks which processing steps are enabled/completed."""
    probe: bool = False
    crop: bool = False
    scale: bool = False
    encode: bool = False
    mux: bool = False
    move: bool = False


@dataclass
class InputInfo:
    """Input file information."""
    path: str = ""
    size: int = 0
    format: str = ""
    duration: float = 0
    video_codec: str = ""
    video_width: int = 0
    video_height: int = 0
    video_fps: float = 0
    audio_codec: str = ""
    audio_channels: int = 0
    audio_bitrate: int = 0


@dataclass
class OutputInfo:
    """Output file information."""
    path: str = ""
    container: str = ""
    video_codec: str = ""
    video_width: int = 0
    video_height: int = 0
    video_bitrate: int = 0
    video_crf: int | None = None
    audio_codec: str = ""
    audio_channels: int = 0
    audio_bitrate: int = 0
    crop: list[int] = field(default_factory=list)  # [w, h, x, y]
    current_pass: int = 0  # Current/last completed pass (0=not started, 1=pass1 done, 2=pass2 done)
    total_passes: int = 2  # Total passes needed


@dataclass
class JobState:
    """Complete job state for persistence."""
    version: str = "2.0.0"
    profile_name: str = ""
    created: str = ""
    updated: str = ""
    steps_enabled: ProcessingSteps = field(default_factory=ProcessingSteps)
    steps_done: ProcessingSteps = field(default_factory=ProcessingSteps)
    input: InputInfo = field(default_factory=InputInfo)
    output: OutputInfo = field(default_factory=OutputInfo)
    error: str = ""

    def mark_done(self, step: str) -> None:
        """Mark a processing step as completed."""
        if hasattr(self.steps_done, step):
            setattr(self.steps_done, step, True)
        self.updated = datetime.now().isoformat()

    def is_done(self, step: str) -> bool:
        """Check if a processing step is completed."""
        return getattr(self.steps_done, step, False)

    def is_enabled(self, step: str) -> bool:
        """Check if a processing step is enabled."""
        return getattr(self.steps_enabled, step, False)


def state_path(job_dir: Path) -> Path:
    """Get the state file path for a job directory."""
    return job_dir / "state.json"


def load_state(job_dir: Path) -> JobState | None:
    """
    Load job state from file.

    Tries in order:
    1. state.json (new format)
    2. {filename}.cfg (old mmprocess format) - creates state.json from it

    Args:
        job_dir: Job directory containing state files

    Returns:
        JobState if file exists, None otherwise
    """
    path = state_path(job_dir)

    # Try state.json first
    if not path.exists():
        # Fall back to .cfg file
        cfg_path = find_cfg_file(job_dir)
        if cfg_path:
            state = load_state_from_cfg(cfg_path)
            if state:
                # Save as state.json for future use
                save_state(job_dir, state)
                return state
        return None

    with open(path, "r") as f:
        data = json.load(f)

    # Parse nested dataclasses
    state = JobState(
        version=data.get("version", "2.0.0"),
        profile_name=data.get("profile_name", ""),
        created=data.get("created", ""),
        updated=data.get("updated", ""),
        error=data.get("error", ""),
    )

    # Parse steps_enabled
    if "steps_enabled" in data:
        for key, value in data["steps_enabled"].items():
            if hasattr(state.steps_enabled, key):
                setattr(state.steps_enabled, key, value)

    # Parse steps_done
    if "steps_done" in data:
        for key, value in data["steps_done"].items():
            if hasattr(state.steps_done, key):
                setattr(state.steps_done, key, value)

    # Parse input
    if "input" in data:
        for key, value in data["input"].items():
            if hasattr(state.input, key):
                setattr(state.input, key, value)

    # Parse output
    if "output" in data:
        for key, value in data["output"].items():
            if hasattr(state.output, key):
                setattr(state.output, key, value)

    return state


def save_state(job_dir: Path, state: JobState) -> None:
    """
    Save job state to file.

    Args:
        job_dir: Job directory for state.json
        state: JobState to save
    """
    state.updated = datetime.now().isoformat()

    path = state_path(job_dir)

    # Convert to dict
    data = {
        "version": state.version,
        "profile_name": state.profile_name,
        "created": state.created,
        "updated": state.updated,
        "error": state.error,
        "steps_enabled": asdict(state.steps_enabled),
        "steps_done": asdict(state.steps_done),
        "input": asdict(state.input),
        "output": asdict(state.output),
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _parse_bool(value: str) -> bool:
    """Parse boolean from INI file (yes/no/true/false/1/0)."""
    return value.lower() in ("yes", "true", "1", "on")


def load_state_from_cfg(cfg_path: Path) -> JobState | None:
    """
    Load job state from old mmprocess .cfg file.

    The .cfg file is the source of truth for the old system.
    This parses the [DONE], [STEPS], [INPUT], [OUTPUT], [SETTINGS] sections.

    Args:
        cfg_path: Path to the .cfg file

    Returns:
        JobState if file exists and is valid, None otherwise
    """
    if not cfg_path.exists():
        return None

    # ConfigParser is case-insensitive by default for options,
    # but we need to handle section names too
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)

    # Helper to check sections case-insensitively
    def has_section(name: str) -> bool:
        return name.upper() in [s.upper() for s in cfg.sections()]

    def get_section(name: str) -> str | None:
        for s in cfg.sections():
            if s.upper() == name.upper():
                return s
        return None

    now = datetime.now().isoformat()
    state = JobState(created=now, updated=now)

    # Default all steps to enabled (old system assumed all steps unless disabled)
    state.steps_enabled.probe = True
    state.steps_enabled.crop = True
    state.steps_enabled.scale = True
    state.steps_enabled.encode = True
    state.steps_enabled.mux = True
    state.steps_enabled.move = True

    # Get profile name and pass info from [SETTINGS]
    sect = get_section("SETTINGS")
    if sect:
        if cfg.has_option(sect, "profile_name"):
            state.profile_name = cfg.get(sect, "profile_name")
        elif cfg.has_option(sect, "profile_loaded"):
            state.profile_name = cfg.get(sect, "profile_loaded")
        if cfg.has_option(sect, "pass"):
            state.output.current_pass = cfg.getint(sect, "pass")
        if cfg.has_option(sect, "passes"):
            state.output.total_passes = cfg.getint(sect, "passes")

    # Parse [STEPS] - what's enabled
    sect = get_section("STEPS")
    if sect:
        if cfg.has_option(sect, "info"):
            state.steps_enabled.probe = _parse_bool(cfg.get(sect, "info"))
        if cfg.has_option(sect, "crop"):
            state.steps_enabled.crop = _parse_bool(cfg.get(sect, "crop"))
        if cfg.has_option(sect, "scale"):
            state.steps_enabled.scale = _parse_bool(cfg.get(sect, "scale"))
        if cfg.has_option(sect, "encode"):
            state.steps_enabled.encode = _parse_bool(cfg.get(sect, "encode"))
        if cfg.has_option(sect, "mux"):
            state.steps_enabled.mux = _parse_bool(cfg.get(sect, "mux"))
        if cfg.has_option(sect, "move"):
            state.steps_enabled.move = _parse_bool(cfg.get(sect, "move"))

    # Parse [DONE] - what's completed
    sect = get_section("DONE")
    if sect:
        if cfg.has_option(sect, "info"):
            state.steps_done.probe = _parse_bool(cfg.get(sect, "info"))
        if cfg.has_option(sect, "crop"):
            state.steps_done.crop = _parse_bool(cfg.get(sect, "crop"))
        if cfg.has_option(sect, "scale"):
            state.steps_done.scale = _parse_bool(cfg.get(sect, "scale"))
        if cfg.has_option(sect, "encode"):
            state.steps_done.encode = _parse_bool(cfg.get(sect, "encode"))
        if cfg.has_option(sect, "mux"):
            state.steps_done.mux = _parse_bool(cfg.get(sect, "mux"))
        if cfg.has_option(sect, "move"):
            state.steps_done.move = _parse_bool(cfg.get(sect, "move"))

    # Parse [INPUT]
    sect = get_section("INPUT")
    if sect:
        if cfg.has_option(sect, "name"):
            state.input.path = cfg.get(sect, "name")
        if cfg.has_option(sect, "size"):
            state.input.size = cfg.getint(sect, "size")
        if cfg.has_option(sect, "length"):
            state.input.duration = cfg.getfloat(sect, "length")
        if cfg.has_option(sect, "vcodec"):
            state.input.video_codec = cfg.get(sect, "vcodec")
        if cfg.has_option(sect, "width"):
            state.input.video_width = cfg.getint(sect, "width")
        if cfg.has_option(sect, "height"):
            state.input.video_height = cfg.getint(sect, "height")
        if cfg.has_option(sect, "fps"):
            state.input.video_fps = cfg.getfloat(sect, "fps")
        if cfg.has_option(sect, "acodec"):
            state.input.audio_codec = cfg.get(sect, "acodec")
        if cfg.has_option(sect, "ac"):
            state.input.audio_channels = cfg.getint(sect, "ac")
        if cfg.has_option(sect, "abr"):
            state.input.audio_bitrate = cfg.getint(sect, "abr")

    # Parse [OUTPUT]
    sect = get_section("OUTPUT")
    if sect:
        if cfg.has_option(sect, "type"):
            state.output.container = cfg.get(sect, "type")
        if cfg.has_option(sect, "width"):
            state.output.video_width = cfg.getint(sect, "width")
        if cfg.has_option(sect, "height"):
            state.output.video_height = cfg.getint(sect, "height")
        if cfg.has_option(sect, "crop"):
            crop_str = cfg.get(sect, "crop")
            if crop_str:
                # Format: w:h:x:y
                parts = crop_str.split(":")
                if len(parts) == 4:
                    state.output.crop = [int(p) for p in parts]

    # Parse [VIDEO]
    sect = get_section("VIDEO")
    if sect:
        if cfg.has_option(sect, "codec"):
            state.output.video_codec = cfg.get(sect, "codec")
        if cfg.has_option(sect, "bitrate"):
            state.output.video_bitrate = cfg.getint(sect, "bitrate")

    # Parse [AUDIO]
    sect = get_section("AUDIO")
    if sect:
        if cfg.has_option(sect, "codec"):
            state.output.audio_codec = cfg.get(sect, "codec")
        if cfg.has_option(sect, "bitrate"):
            state.output.audio_bitrate = cfg.getint(sect, "bitrate")
        if cfg.has_option(sect, "channels"):
            state.output.audio_channels = cfg.getint(sect, "channels")

    return state


def find_cfg_file(job_dir: Path) -> Path | None:
    """Find the .cfg file in a job directory."""
    # The cfg file is named {source_filename}.cfg
    source_name = job_dir.name  # Directory name is the source filename
    cfg_path = job_dir / f"{source_name}.cfg"
    if cfg_path.exists():
        return cfg_path
    return None


def create_state(
    profile_name: str,
    input_path: Path,
    probe_enabled: bool = True,
    crop_enabled: bool = False,
    scale_enabled: bool = True,
    encode_enabled: bool = True,
    mux_enabled: bool = True,
    move_enabled: bool = True,
) -> JobState:
    """
    Create a new job state.

    Args:
        profile_name: Name of the encoding profile
        input_path: Path to input file
        probe_enabled: Enable probing step
        crop_enabled: Enable crop detection
        scale_enabled: Enable scaling
        encode_enabled: Enable encoding
        mux_enabled: Enable muxing
        move_enabled: Enable moving to output

    Returns:
        New JobState instance
    """
    now = datetime.now().isoformat()

    state = JobState(
        profile_name=profile_name,
        created=now,
        updated=now,
    )

    state.input.path = str(input_path)
    if input_path.exists():
        state.input.size = input_path.stat().st_size

    state.steps_enabled.probe = probe_enabled
    state.steps_enabled.crop = crop_enabled
    state.steps_enabled.scale = scale_enabled
    state.steps_enabled.encode = encode_enabled
    state.steps_enabled.mux = mux_enabled
    state.steps_enabled.move = move_enabled

    return state
