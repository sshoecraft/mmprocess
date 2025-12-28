"""
FFmpeg filter chain construction.
"""

from dataclasses import dataclass, field


@dataclass
class FilterChain:
    """Represents an FFmpeg filter chain."""
    filters: list[str] = field(default_factory=list)

    def add(self, filter_str: str) -> None:
        """Add a filter to the chain."""
        if filter_str:
            self.filters.append(filter_str)

    def build(self) -> str:
        """Build the complete filter string for -vf."""
        return ",".join(self.filters) if self.filters else ""

    def __bool__(self) -> bool:
        """Return True if chain has filters."""
        return len(self.filters) > 0


def crop_filter(width: int, height: int, x: int, y: int) -> str:
    """
    Build crop filter string.

    Args:
        width: Crop width
        height: Crop height
        x: X offset
        y: Y offset

    Returns:
        FFmpeg crop filter string
    """
    return f"crop={width}:{height}:{x}:{y}"


def scale_filter(width: int, height: int, algorithm: str = "") -> str:
    """
    Build scale filter string.

    Args:
        width: Target width
        height: Target height
        algorithm: Scaling algorithm (lanczos, bicubic, etc.)

    Returns:
        FFmpeg scale filter string
    """
    if algorithm:
        return f"scale={width}:{height}:flags={algorithm}"
    return f"scale={width}:{height}"


def deinterlace_filter(method: str = "yadif") -> str:
    """
    Build deinterlace filter string.

    Args:
        method: Deinterlace method (yadif, w3fdif, etc.)

    Returns:
        FFmpeg deinterlace filter string
    """
    return method


def denoise_filter(method: str = "hqdn3d") -> str:
    """
    Build denoise filter string.

    Args:
        method: Denoise method (hqdn3d, nlmeans, etc.)

    Returns:
        FFmpeg denoise filter string
    """
    return method


def subtitle_filter(input_path: str, stream_index: int | None = None) -> str:
    """
    Build subtitle burn-in filter string.

    Uses FFmpeg's subtitles filter for text-based subtitles.
    The input path needs special escaping for the filter syntax.

    Args:
        input_path: Path to input file containing subtitles
        stream_index: Subtitle stream index (None for external .srt files)

    Returns:
        FFmpeg subtitle filter string
    """
    # Escape special characters in path for FFmpeg filter syntax
    # Colons, backslashes, and single quotes need escaping
    escaped_path = input_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    if stream_index is not None:
        return f"subtitles='{escaped_path}':si={stream_index}"
    else:
        return f"subtitles='{escaped_path}'"


def build_video_filters(
    crop: tuple[int, int, int, int] | None = None,
    scale: tuple[int, int] | None = None,
    deinterlace: bool = False,
    denoise: bool = False,
    deinterlace_method: str = "yadif",
    denoise_method: str = "hqdn3d",
    scale_algorithm: str = "lanczos",
    subtitle_path: str | None = None,
    subtitle_stream_index: int | None = None,
) -> FilterChain:
    """
    Build a complete video filter chain.

    Filter order follows best practices:
    1. Crop (reduces pixels to process)
    2. Deinterlace (after crop, before scale)
    3. Scale (after deinterlace)
    4. Denoise (after scale)
    5. Subtitles (last, after final resolution is set)

    Args:
        crop: Crop parameters (w, h, x, y)
        scale: Scale parameters (w, h)
        deinterlace: Whether to deinterlace
        denoise: Whether to denoise
        deinterlace_method: Deinterlace filter to use
        denoise_method: Denoise filter to use
        scale_algorithm: Scaling algorithm
        subtitle_path: Path to file containing subtitles to burn in
        subtitle_stream_index: Subtitle stream index to burn in

    Returns:
        FilterChain with all filters in correct order
    """
    chain = FilterChain()

    # 1. Crop first
    if crop:
        w, h, x, y = crop
        chain.add(crop_filter(w, h, x, y))

    # 2. Deinterlace after crop, before scale
    if deinterlace:
        chain.add(deinterlace_filter(deinterlace_method))

    # 3. Scale after deinterlace
    if scale:
        w, h = scale
        chain.add(scale_filter(w, h, scale_algorithm))

    # 4. Denoise after scale
    if denoise:
        chain.add(denoise_filter(denoise_method))

    # 5. Subtitles last (after final resolution is set)
    if subtitle_path:
        chain.add(subtitle_filter(subtitle_path, subtitle_stream_index))

    return chain


def build_audio_filters(
    channels: int | None = None,
    sample_rate: int | None = None,
) -> FilterChain:
    """
    Build audio filter chain.

    Args:
        channels: Target channel count (for downmixing)
        sample_rate: Target sample rate

    Returns:
        FilterChain with audio filters
    """
    chain = FilterChain()

    # Channel conversion
    if channels:
        if channels == 2:
            chain.add("pan=stereo|FL=FC+0.30*FL+0.30*BL|FR=FC+0.30*FR+0.30*BR")
        elif channels == 1:
            chain.add("pan=mono|c0=0.5*c0+0.5*c1")

    # Sample rate conversion
    if sample_rate:
        chain.add(f"aresample={sample_rate}")

    return chain
