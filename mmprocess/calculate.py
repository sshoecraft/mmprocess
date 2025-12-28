"""
Calculations for video processing: scaling, bitrate, etc.

Implements the SMART sizing algorithm from the original mmprocess C code.
The key formula is:
    target_bpp = ref_bpp - ((pixels - ref_pixels) * factor)

This scales the target bits-per-pixel based on resolution:
- Higher resolution = lower BPP needed = smaller files
- Default: ref_bpp=0.225, ref_pixels=345600 (720x480), factor=0.000061
"""

from dataclasses import dataclass

from mmprocess.config import Profile
from mmprocess.probe import MediaInfo


@dataclass
class ScaleResult:
    """Result of scale calculation."""
    width: int
    height: int
    scaled: bool  # True if different from input


@dataclass
class BitrateResult:
    """Result of bitrate calculation."""
    video_bitrate: int  # kbps
    audio_bitrate: int  # kbps
    total_bitrate: int  # kbps
    bpp: float  # bits per pixel (for logging/debugging)


def round_to_multiple(value: int, multiple: int = 2) -> int:
    """Round value to nearest multiple (for video dimensions)."""
    return ((value + multiple // 2) // multiple) * multiple


def calculate_smart_bpp(
    pixels: int,
    ref_bpp: float = 0.225,
    ref_pixels: int = 345600,
    factor: float = 0.000061,
    min_bpp: float | None = None,
    max_bpp: float | None = None,
) -> float:
    """
    Calculate target BPP using the SMART sizing formula from old mmprocess.

    Higher resolution videos need lower BPP to achieve similar quality,
    because there's more spatial redundancy to exploit.

    Formula (from smart.c):
        diff = pixels - ref_pixels
        df = diff * factor
        d = df / 1000
        target_bpp = ref_bpp - d

    Example for 1920x800 (1,536,000 pixels):
        diff = 1536000 - 345600 = 1190400
        df = 1190400 * 0.000061 = 72.6
        d = 72.6 / 1000 = 0.0726
        target_bpp = 0.225 - 0.0726 = 0.152

    Args:
        pixels: Output resolution in pixels (width * height)
        ref_bpp: Reference BPP at ref_pixels resolution (default 0.225)
        ref_pixels: Reference resolution in pixels (default 345600 = 720x480)
        factor: BPP reduction factor (default 0.000061)
        min_bpp: Minimum allowed BPP (floor)
        max_bpp: Maximum allowed BPP (ceiling)

    Returns:
        Target bits per pixel
    """
    # Calculate target BPP based on resolution difference from reference
    # Formula from old smart.c: cq = ref_b - ((diff * factor) / 1000)
    diff = pixels - ref_pixels
    df = diff * factor
    d = df / 1000.0
    target_bpp = ref_bpp - d

    # Apply constraints
    if min_bpp is not None and target_bpp < min_bpp:
        target_bpp = min_bpp
    if max_bpp is not None and target_bpp > max_bpp:
        target_bpp = max_bpp

    # Sanity check - BPP should never be negative or extremely low
    if target_bpp < 0.05:
        target_bpp = 0.05

    return target_bpp


def calculate_scale(
    input_width: int,
    input_height: int,
    max_width: int | None = None,
    max_height: int | None = None,
    crop_width: int | None = None,
    crop_height: int | None = None,
) -> ScaleResult:
    """
    Calculate output dimensions respecting constraints.

    Args:
        input_width: Original video width
        input_height: Original video height
        max_width: Maximum allowed width
        max_height: Maximum allowed height
        crop_width: Width after cropping (if any)
        crop_height: Height after cropping (if any)

    Returns:
        ScaleResult with calculated dimensions
    """
    # Start with cropped dimensions if provided, otherwise input
    width = crop_width if crop_width else input_width
    height = crop_height if crop_height else input_height

    # Calculate aspect ratio
    aspect = width / height if height > 0 else 1.0

    # Apply max width constraint
    if max_width and width > max_width:
        width = max_width
        height = round_to_multiple(int(width / aspect))

    # Apply max height constraint
    if max_height and height > max_height:
        height = max_height
        width = round_to_multiple(int(height * aspect))

    # Ensure dimensions are even (required for most codecs)
    width = round_to_multiple(width, 2)
    height = round_to_multiple(height, 2)

    # Determine if scaling is needed
    original_width = crop_width if crop_width else input_width
    original_height = crop_height if crop_height else input_height
    scaled = (width != original_width) or (height != original_height)

    return ScaleResult(width=width, height=height, scaled=scaled)


def calculate_bitrate(
    width: int,
    height: int,
    fps: float,
    duration: float,
    max_size_mb: int | None = None,
    max_bitrate: int | None = None,
    min_bitrate: int | None = None,
    audio_bitrate: int = 384,
    crf: int | None = None,
    mbps: float | None = None,
    max_bpp: float | None = None,
    min_bpp: float | None = None,
    # SMART sizing parameters
    input_size: int | None = None,
    can_grow: bool = False,
    ref_bpp: float = 0.225,
    ref_pixels: int = 345600,
    factor: float = 0.000061,
    inflate: bool = True,
    deflate: bool = True,
    smart_enabled: bool = False,
) -> BitrateResult:
    """
    Calculate video bitrate based on constraints.

    Implements the SMART sizing algorithm from the original mmprocess:
    1. Calculate initial target from MBPS * duration
    2. Calculate target BPP based on resolution (higher res = lower BPP)
    3. Adjust size up (inflate) or down (deflate) to meet target BPP
    4. Ensure output never exceeds input size (unless can_grow=True)
    5. Apply max_size_mb, max_bitrate, min_bitrate constraints

    Args:
        width: Output video width
        height: Output video height
        fps: Frames per second
        duration: Video duration in seconds
        max_size_mb: Maximum output file size in MB
        max_bitrate: Maximum video bitrate in kbps
        min_bitrate: Minimum video bitrate in kbps
        audio_bitrate: Audio bitrate in kbps
        crf: If set, indicates CRF mode (no specific bitrate)
        mbps: Target MB per second of content (smart sizing)
        max_bpp: Maximum bits per pixel (hard limit)
        min_bpp: Minimum bits per pixel (hard limit)
        input_size: Input file size in bytes (for can_grow check)
        can_grow: Allow output to be larger than input (default False)
        ref_bpp: Reference BPP for SMART sizing (default 0.225)
        ref_pixels: Reference pixels for SMART sizing (default 345600)
        factor: BPP scaling factor for SMART sizing (default 0.000061)
        inflate: Allow increasing size to meet target BPP
        deflate: Allow decreasing size to meet target BPP
        smart_enabled: Whether SMART sizing is enabled

    Returns:
        BitrateResult with calculated bitrates and BPP
    """
    pixels = width * height
    pixels_per_second = pixels * fps

    # If CRF mode and no smart sizing, return 0 for video bitrate
    if crf is not None and not smart_enabled:
        return BitrateResult(
            video_bitrate=0,
            audio_bitrate=audio_bitrate,
            total_bitrate=0,
            bpp=0.0
        )

    # Calculate audio size for the full duration
    audio_size_bytes = (audio_bitrate * 1000 * duration) / 8

    # Step 1: Calculate initial target size from MBPS
    if mbps and duration > 0:
        target_size_bytes = duration * mbps * 1024 * 1024
    else:
        # Fallback: use a reasonable default BPP
        default_bpp = 0.15
        video_size_bytes = (pixels_per_second * default_bpp * duration) / 8
        target_size_bytes = video_size_bytes + audio_size_bytes

    # Step 2: Apply max_size_mb constraint
    if max_size_mb and duration > 0:
        max_size_bytes = max_size_mb * 1024 * 1024
        if target_size_bytes > max_size_bytes:
            target_size_bytes = max_size_bytes

    # Step 3: Apply input size constraint (can't grow larger than input)
    if input_size and not can_grow:
        if target_size_bytes > input_size:
            target_size_bytes = input_size

    # Calculate initial video size and bitrate
    video_size_bytes = target_size_bytes - audio_size_bytes
    if video_size_bytes < 0:
        video_size_bytes = target_size_bytes * 0.9  # 90% for video if audio too big

    video_bitrate = int((video_size_bytes * 8) / duration / 1000) if duration > 0 else 0

    # Calculate initial BPP
    initial_bpp = (video_bitrate * 1000) / pixels_per_second if pixels_per_second > 0 else 0

    # Step 4: Apply SMART BPP scaling if enabled
    if smart_enabled and pixels_per_second > 0:
        # Calculate target BPP based on resolution
        target_bpp = calculate_smart_bpp(
            pixels=pixels,
            ref_bpp=ref_bpp,
            ref_pixels=ref_pixels,
            factor=factor,
            min_bpp=min_bpp,
            max_bpp=max_bpp,
        )

        # Adjust size based on BPP comparison
        if initial_bpp < target_bpp and inflate:
            # Current BPP is below target - increase size (if allowed)
            new_video_bitrate = int(pixels_per_second * target_bpp / 1000)
            new_video_size = (new_video_bitrate * 1000 * duration) / 8
            new_total_size = new_video_size + audio_size_bytes

            # Check constraints before inflating
            can_inflate = True
            if max_size_mb:
                max_size_bytes = max_size_mb * 1024 * 1024
                if new_total_size > max_size_bytes:
                    can_inflate = False
            if input_size and not can_grow:
                if new_total_size > input_size:
                    can_inflate = False

            if can_inflate:
                video_bitrate = new_video_bitrate

        elif initial_bpp > target_bpp and deflate:
            # Current BPP is above target - decrease size
            video_bitrate = int(pixels_per_second * target_bpp / 1000)

    # Step 5: Apply hard BPP constraints (these override SMART adjustments)
    if pixels_per_second > 0:
        current_bpp = (video_bitrate * 1000) / pixels_per_second

        if max_bpp and current_bpp > max_bpp:
            video_bitrate = int(pixels_per_second * max_bpp / 1000)

        if min_bpp and current_bpp < min_bpp:
            video_bitrate = int(pixels_per_second * min_bpp / 1000)

    # Step 6: Re-check max size constraint after BPP adjustments
    if max_size_mb and duration > 0:
        video_size_bytes = (video_bitrate * 1000 * duration) / 8
        total_size_bytes = video_size_bytes + audio_size_bytes
        max_size_bytes = max_size_mb * 1024 * 1024

        if total_size_bytes > max_size_bytes:
            video_size_bytes = max_size_bytes - audio_size_bytes
            video_bitrate = int((video_size_bytes * 8) / duration / 1000)

    # Step 7: Re-check input size constraint after all adjustments
    if input_size and not can_grow and duration > 0:
        video_size_bytes = (video_bitrate * 1000 * duration) / 8
        total_size_bytes = video_size_bytes + audio_size_bytes

        if total_size_bytes > input_size:
            video_size_bytes = input_size - audio_size_bytes
            if video_size_bytes < 0:
                video_size_bytes = input_size * 0.9
            video_bitrate = int((video_size_bytes * 8) / duration / 1000)

    # Step 8: Apply max/min bitrate constraints
    if max_bitrate and video_bitrate > max_bitrate:
        video_bitrate = max_bitrate

    if min_bitrate and video_bitrate < min_bitrate:
        video_bitrate = min_bitrate

    # Calculate final BPP
    final_bpp = (video_bitrate * 1000) / pixels_per_second if pixels_per_second > 0 else 0

    total_bitrate = video_bitrate + audio_bitrate

    return BitrateResult(
        video_bitrate=video_bitrate,
        audio_bitrate=audio_bitrate,
        total_bitrate=total_bitrate,
        bpp=round(final_bpp, 3)
    )


def calculate_output_size(
    video_bitrate: int,
    audio_bitrate: int,
    duration: float
) -> int:
    """
    Estimate output file size in bytes.

    Args:
        video_bitrate: Video bitrate in kbps
        audio_bitrate: Audio bitrate in kbps
        duration: Duration in seconds

    Returns:
        Estimated file size in bytes
    """
    total_kbps = video_bitrate + audio_bitrate
    total_bits = total_kbps * 1000 * duration
    return int(total_bits / 8)


def calculate_from_profile(
    info: MediaInfo,
    profile: Profile,
    crop: tuple[int, int, int, int] | None = None,
) -> tuple[ScaleResult, BitrateResult]:
    """
    Calculate scale and bitrate based on profile settings.

    Args:
        info: Media information from probe
        profile: Encoding profile
        crop: Crop dimensions (w, h, x, y) if any

    Returns:
        Tuple of (ScaleResult, BitrateResult)
    """
    video = info.primary_video
    if not video:
        raise ValueError("No video stream found")

    # Calculate cropped dimensions
    crop_width = crop[0] if crop else None
    crop_height = crop[1] if crop else None

    # Calculate scale
    scale = calculate_scale(
        input_width=video.width,
        input_height=video.height,
        max_width=profile.limits.max_width or profile.video.max_width,
        max_height=profile.limits.max_height or profile.video.max_height,
        crop_width=crop_width,
        crop_height=crop_height,
    )

    # Calculate bitrate with SMART sizing
    bitrate = calculate_bitrate(
        width=scale.width,
        height=scale.height,
        fps=video.fps,
        duration=video.duration,
        max_size_mb=profile.limits.max_size_mb,
        max_bitrate=profile.limits.max_bitrate,
        min_bitrate=profile.limits.min_bitrate,
        audio_bitrate=profile.audio.bitrate,
        crf=profile.video.crf,
        mbps=profile.smart.mbps if profile.smart.enabled else None,
        max_bpp=profile.smart.max_bpp,
        min_bpp=profile.smart.min_bpp,
        # SMART sizing parameters
        input_size=info.size,
        can_grow=profile.smart.can_grow,
        ref_bpp=profile.smart.ref_bpp,
        ref_pixels=profile.smart.ref_pixels,
        factor=profile.smart.factor,
        inflate=profile.smart.inflate,
        deflate=profile.smart.deflate,
        smart_enabled=profile.smart.enabled,
    )

    return scale, bitrate
