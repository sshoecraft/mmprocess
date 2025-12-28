"""
Configuration management for mmprocess.

Handles loading of main config and profiles from TOML files.
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DirsConfig:
    """Directory configuration."""
    base: Path | None = None  # Must be configured
    input: Path = Path("in")
    out: Path = Path("out")
    work: Path = Path("work")
    done: Path = Path("done")
    error: Path = Path("error")
    temp: Path = Path("temp")
    profiles: Path = Path("profiles")

    def resolve(self) -> None:
        """Resolve relative paths against base directory."""
        if self.base is None:
            raise ValueError("Configuration error: dirs.base must be set in config file")
        for name in ["input", "out", "work", "done", "error", "temp", "profiles"]:
            path = getattr(self, name)
            if not path.is_absolute():
                setattr(self, name, self.base / path)


@dataclass
class ToolsConfig:
    """External tools configuration."""
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    mp4box: str = "MP4Box"
    mkvmerge: str = "mkvmerge"


@dataclass
class DefaultsConfig:
    """Default encoding settings."""
    profile: str = "default"
    container: str = "mp4"  # Default to mp4 (same as old mmprocess)
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    audio_language: str = "eng"  # Preferred audio language (ISO 639)


@dataclass
class Config:
    """Main application configuration."""
    dirs: DirsConfig = field(default_factory=DirsConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)


@dataclass
class VideoProfile:
    """Video encoding settings from profile."""
    codec: str = "libx264"
    crf: int | None = None
    bitrate: int | None = None
    max_width: int = 1920
    max_height: int = 1080
    opts: str = ""


@dataclass
class AudioProfile:
    """Audio encoding settings from profile."""
    codec: str = "aac"
    bitrate: int = 384
    channels: int = 6
    sample_rate: int | None = None


@dataclass
class ProcessingProfile:
    """Processing steps configuration."""
    crop: bool = True
    scale: bool = True
    denoise: bool = False
    deinterlace: bool = False


@dataclass
class LimitsProfile:
    """Output constraints."""
    max_size_mb: int | None = None
    max_bitrate: int | None = None
    max_width: int | None = None
    max_height: int | None = None
    min_bitrate: int | None = None


@dataclass
class SmartProfile:
    """Smart sizing configuration."""
    enabled: bool = False
    size: bool = True
    scale: bool = True
    mbps: float = 1.0  # Target MB per second of content
    max_bpp: float | None = None  # Max bits per pixel
    min_bpp: float | None = None  # Min bits per pixel
    # SMART BPP scaling parameters (from old mmprocess)
    # Formula: target_bpp = ref_bpp - ((pixels - ref_pixels) * factor)
    ref_bpp: float = 0.225  # Reference BPP at ref_pixels resolution
    ref_pixels: int = 345600  # Reference resolution (720x480)
    factor: float = 0.000061  # BPP reduction factor per pixel above ref
    can_grow: bool = False  # Allow output to be larger than input
    inflate: bool = True  # Allow size increase to meet target BPP
    deflate: bool = True  # Allow size decrease to meet target BPP


@dataclass
class Profile:
    """Complete encoding profile."""
    name: str = "default"
    container: str | None = None  # None = use config default
    video: VideoProfile = field(default_factory=VideoProfile)
    audio: AudioProfile = field(default_factory=AudioProfile)
    processing: ProcessingProfile = field(default_factory=ProcessingProfile)
    limits: LimitsProfile = field(default_factory=LimitsProfile)
    smart: SmartProfile = field(default_factory=SmartProfile)


def get_config_path() -> Path:
    """Get the default config file path (XDG compliant)."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_dir = Path(xdg_config)
    else:
        config_dir = Path.home() / ".config"
    return config_dir / "mmprocess" / "config.toml"


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from TOML file."""
    if config_path is None:
        config_path = get_config_path()

    config = Config()

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Create it with at minimum:\n\n"
            f"[dirs]\n"
            f'base = "/path/to/your/convert/directory"\n'
        )

    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Load dirs section
        if "dirs" in data:
            dirs_data = data["dirs"]
            if "base" in dirs_data:
                config.dirs.base = Path(dirs_data["base"])
            if "in" in dirs_data:
                config.dirs.input = Path(dirs_data["in"])
            if "out" in dirs_data:
                config.dirs.out = Path(dirs_data["out"])
            if "work" in dirs_data:
                config.dirs.work = Path(dirs_data["work"])
            if "done" in dirs_data:
                config.dirs.done = Path(dirs_data["done"])
            if "error" in dirs_data:
                config.dirs.error = Path(dirs_data["error"])
            if "temp" in dirs_data:
                config.dirs.temp = Path(dirs_data["temp"])
            if "profiles" in dirs_data:
                config.dirs.profiles = Path(dirs_data["profiles"])

        # Load tools section
        if "tools" in data:
            tools_data = data["tools"]
            if "ffmpeg" in tools_data:
                config.tools.ffmpeg = tools_data["ffmpeg"]
            if "ffprobe" in tools_data:
                config.tools.ffprobe = tools_data["ffprobe"]
            if "mp4box" in tools_data:
                config.tools.mp4box = tools_data["mp4box"]
            if "mkvmerge" in tools_data:
                config.tools.mkvmerge = tools_data["mkvmerge"]

        # Load defaults section
        if "defaults" in data:
            defaults_data = data["defaults"]
            if "profile" in defaults_data:
                config.defaults.profile = defaults_data["profile"]
            if "container" in defaults_data:
                config.defaults.container = defaults_data["container"]
            if "video_codec" in defaults_data:
                config.defaults.video_codec = defaults_data["video_codec"]
            if "audio_codec" in defaults_data:
                config.defaults.audio_codec = defaults_data["audio_codec"]
            if "audio_language" in defaults_data:
                config.defaults.audio_language = defaults_data["audio_language"]

    # Resolve relative paths
    config.dirs.resolve()

    return config


def _parse_bool(value: str) -> bool:
    """Parse boolean from INI file (yes/no/true/false/1/0)."""
    return value.lower() in ("yes", "true", "1", "on")


def _load_profile_cfg(profile_path: Path, profile: Profile) -> None:
    """Load profile from INI/CFG format (old mmprocess format)."""
    import configparser

    cfg = configparser.ConfigParser()
    cfg.read(profile_path)

    # [steps] section
    if cfg.has_section("steps"):
        if cfg.has_option("steps", "smart"):
            profile.smart.enabled = _parse_bool(cfg.get("steps", "smart"))
        if cfg.has_option("steps", "crop"):
            profile.processing.crop = _parse_bool(cfg.get("steps", "crop"))
        if cfg.has_option("steps", "scale"):
            profile.processing.scale = _parse_bool(cfg.get("steps", "scale"))

    # [limits] section
    if cfg.has_section("limits"):
        if cfg.has_option("limits", "mbps"):
            profile.smart.mbps = cfg.getfloat("limits", "mbps")
        if cfg.has_option("limits", "maxbpp"):
            profile.smart.max_bpp = cfg.getfloat("limits", "maxbpp")
        if cfg.has_option("limits", "minbpp"):
            profile.smart.min_bpp = cfg.getfloat("limits", "minbpp")
        if cfg.has_option("limits", "maxs"):
            profile.limits.max_size_mb = cfg.getint("limits", "maxs")
        if cfg.has_option("limits", "maxb"):
            profile.limits.max_bitrate = cfg.getint("limits", "maxb")
        if cfg.has_option("limits", "maxw"):
            profile.limits.max_width = cfg.getint("limits", "maxw")
        if cfg.has_option("limits", "maxh"):
            profile.limits.max_height = cfg.getint("limits", "maxh")

    # [video] section
    if cfg.has_section("video"):
        if cfg.has_option("video", "codec"):
            profile.video.codec = cfg.get("video", "codec")
        if cfg.has_option("video", "opts"):
            profile.video.opts = cfg.get("video", "opts")

    # [audio] section
    if cfg.has_section("audio"):
        if cfg.has_option("audio", "bitrate"):
            profile.audio.bitrate = cfg.getint("audio", "bitrate")
        if cfg.has_option("audio", "channels"):
            profile.audio.channels = cfg.getint("audio", "channels")

    # [smart] section
    if cfg.has_section("smart"):
        if cfg.has_option("smart", "size"):
            profile.smart.size = _parse_bool(cfg.get("smart", "size"))
        if cfg.has_option("smart", "scale"):
            profile.smart.scale = _parse_bool(cfg.get("smart", "scale"))
        if cfg.has_option("smart", "ref_b"):
            profile.smart.ref_bpp = cfg.getfloat("smart", "ref_b")
        if cfg.has_option("smart", "ref_p"):
            profile.smart.ref_pixels = cfg.getint("smart", "ref_p")
        if cfg.has_option("smart", "factor"):
            profile.smart.factor = cfg.getfloat("smart", "factor")
        if cfg.has_option("smart", "inflate"):
            profile.smart.inflate = _parse_bool(cfg.get("smart", "inflate"))
        if cfg.has_option("smart", "deflate"):
            profile.smart.deflate = _parse_bool(cfg.get("smart", "deflate"))

    # [settings] section - for CANGROW
    if cfg.has_section("settings"):
        if cfg.has_option("settings", "cangrow"):
            profile.smart.can_grow = _parse_bool(cfg.get("settings", "cangrow"))


def profile_exists(config: Config, name: str) -> bool:
    """Check if a profile exists (either .cfg or .toml)."""
    cfg_path = config.dirs.profiles / f"{name}.cfg"
    toml_path = config.dirs.profiles / f"{name}.toml"
    return cfg_path.exists() or toml_path.exists()


def load_profile(config: Config, name: str) -> Profile:
    """Load a profile from the profiles directory."""
    profile = Profile(name=name)

    # Try .cfg first (old INI format), then .toml
    cfg_path = config.dirs.profiles / f"{name}.cfg"
    toml_path = config.dirs.profiles / f"{name}.toml"

    if cfg_path.exists():
        _load_profile_cfg(cfg_path, profile)
        return profile

    if not toml_path.exists():
        return profile

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

        # Load top-level settings
        if "container" in data:
            profile.container = data["container"]

        # Load video section
        if "video" in data:
            video_data = data["video"]
            if "codec" in video_data:
                profile.video.codec = video_data["codec"]
            if "crf" in video_data:
                profile.video.crf = video_data["crf"]
            if "bitrate" in video_data:
                profile.video.bitrate = video_data["bitrate"]
            if "max_width" in video_data:
                profile.video.max_width = video_data["max_width"]
            if "max_height" in video_data:
                profile.video.max_height = video_data["max_height"]
            if "opts" in video_data:
                profile.video.opts = video_data["opts"]

        # Load audio section
        if "audio" in data:
            audio_data = data["audio"]
            if "codec" in audio_data:
                profile.audio.codec = audio_data["codec"]
            if "bitrate" in audio_data:
                profile.audio.bitrate = audio_data["bitrate"]
            if "channels" in audio_data:
                profile.audio.channels = audio_data["channels"]
            if "sample_rate" in audio_data:
                profile.audio.sample_rate = audio_data["sample_rate"]

        # Load processing section
        if "processing" in data:
            proc_data = data["processing"]
            if "crop" in proc_data:
                profile.processing.crop = proc_data["crop"]
            if "scale" in proc_data:
                profile.processing.scale = proc_data["scale"]
            if "denoise" in proc_data:
                profile.processing.denoise = proc_data["denoise"]
            if "deinterlace" in proc_data:
                profile.processing.deinterlace = proc_data["deinterlace"]

        # Load limits section
        if "limits" in data:
            limits_data = data["limits"]
            if "max_size_mb" in limits_data:
                profile.limits.max_size_mb = limits_data["max_size_mb"]
            if "max_bitrate" in limits_data:
                profile.limits.max_bitrate = limits_data["max_bitrate"]
            if "max_width" in limits_data:
                profile.limits.max_width = limits_data["max_width"]
            if "max_height" in limits_data:
                profile.limits.max_height = limits_data["max_height"]
            if "min_bitrate" in limits_data:
                profile.limits.min_bitrate = limits_data["min_bitrate"]

        # Load smart section
        if "smart" in data:
            smart_data = data["smart"]
            if "enabled" in smart_data:
                profile.smart.enabled = smart_data["enabled"]
            if "size" in smart_data:
                profile.smart.size = smart_data["size"]
            if "scale" in smart_data:
                profile.smart.scale = smart_data["scale"]
            if "mbps" in smart_data:
                profile.smart.mbps = smart_data["mbps"]
            if "max_bpp" in smart_data:
                profile.smart.max_bpp = smart_data["max_bpp"]
            if "min_bpp" in smart_data:
                profile.smart.min_bpp = smart_data["min_bpp"]
            if "ref_bpp" in smart_data:
                profile.smart.ref_bpp = smart_data["ref_bpp"]
            if "ref_pixels" in smart_data:
                profile.smart.ref_pixels = smart_data["ref_pixels"]
            if "factor" in smart_data:
                profile.smart.factor = smart_data["factor"]
            if "can_grow" in smart_data:
                profile.smart.can_grow = smart_data["can_grow"]
            if "inflate" in smart_data:
                profile.smart.inflate = smart_data["inflate"]
            if "deflate" in smart_data:
                profile.smart.deflate = smart_data["deflate"]

    return profile
