# Profile Reference

Profiles define encoding settings for different use cases.

## Profile Location

Profiles are stored in the profiles directory (default: `{base}/profiles/`).
Profiles can be either `.toml` (new format) or `.cfg` (legacy INI format).

## Legacy .cfg Format

The original mmprocess used INI-style `.cfg` files. These are still supported:

```ini
[video]
codec=copy
opts=

[audio]
bitrate=384

[steps]
crop=no
scale=no

[smart]
enabled=yes
```

## Example Profile

```toml
# profiles/cgi.toml - For CGI/animated content

[video]
codec = "libx264"
crf = 18
max_width = 1280
max_height = 720
opts = ""

[audio]
codec = "aac"
bitrate = 192
channels = 2

[processing]
crop = false
scale = true
denoise = false
deinterlace = false

[limits]
max_size_mb = 2048
max_bitrate = 4000

[smart]
enabled = false
```

## Profile Sections

### [video]

Video encoding settings.

| Key | Description | Default |
|-----|-------------|---------|
| `codec` | Video codec (libx264, libx265, etc.) | `libx264` |
| `crf` | Constant Rate Factor (quality mode) | None |
| `bitrate` | Video bitrate in kbps (alternative to CRF) | None |
| `max_width` | Maximum output width | `1920` |
| `max_height` | Maximum output height | `1080` |
| `opts` | Extra codec options | `""` |

Note: If `crf` is set, bitrate mode is disabled (quality-based encoding).

### [audio]

Audio encoding settings.

| Key | Description | Default |
|-----|-------------|---------|
| `codec` | Audio codec (aac, ac3, copy) | `aac` |
| `bitrate` | Audio bitrate in kbps | `384` |
| `channels` | Output channel count | `6` |
| `sample_rate` | Sample rate (optional) | None |

### [processing]

Processing steps to enable.

| Key | Description | Default |
|-----|-------------|---------|
| `crop` | Enable automatic crop detection | `true` |
| `scale` | Enable resolution scaling | `true` |
| `denoise` | Enable denoise filter | `false` |
| `deinterlace` | Enable deinterlace filter | `false` |
| `subtitles` | Burn in forced/external subtitles | `true` |

### [limits]

Output constraints.

| Key | Description | Default |
|-----|-------------|---------|
| `max_size_mb` | Maximum output file size in MB | None |
| `max_bitrate` | Maximum video bitrate in kbps | None |
| `max_width` | Maximum output width | None |
| `max_height` | Maximum output height | None |
| `min_bitrate` | Minimum video bitrate in kbps | None |

### [smart]

Smart sizing configuration.

| Key | Description | Default |
|-----|-------------|---------|
| `enabled` | Enable smart sizing | `false` |
| `size` | Adjust file size | `true` |
| `scale` | Adjust resolution | `true` |

### [tier.NAME] (Legacy .cfg) / [[tiers]] (TOML)

Resolution-based encoding overrides. Allows different codecs and size limits based on input resolution. Useful for using HEVC for 4K sources while keeping H.264 for 1080p compatibility.

Tiers are matched by finding the smallest tier where `input_pixels <= max_pixels`.

| Key | Description | Default |
|-----|-------------|---------|
| `name` | Tier name (for logging) | `""` |
| `max_pixels` | Maximum input pixels (width × height) | Required |
| `codec` | Video codec override | None |
| `max_size_mb` | Max output size override in MB | None |
| `max_width` | Max output width override | None |
| `max_height` | Max output height override | None |

#### Legacy .cfg Format

```ini
[tier.sd]
max_pixels=921600
codec=libx264
max_size_mb=2048

[tier.hd]
max_pixels=2073600
codec=libx264
max_size_mb=4096

[tier.uhd]
max_pixels=8294400
codec=libx265
max_size_mb=6144
```

#### TOML Format

```toml
[[tiers]]
name = "sd"
max_pixels = 921600
codec = "libx264"
max_size_mb = 2048

[[tiers]]
name = "hd"
max_pixels = 2073600
codec = "libx264"
max_size_mb = 4096

[[tiers]]
name = "uhd"
max_pixels = 8294400
codec = "libx265"
max_size_mb = 6144
```

#### Common Resolution Pixel Values

| Resolution | Pixels | Notes |
|------------|--------|-------|
| 720p | 921,600 | 1280×720 |
| 1080p | 2,073,600 | 1920×1080 |
| 1440p | 3,686,400 | 2560×1440 |
| 4K | 8,294,400 | 3840×2160 |

## Common Profile Examples

### copy_video.toml - Quick remux (copy streams)

```toml
[video]
codec = "copy"

[audio]
codec = "copy"

[processing]
crop = false
scale = false
```

### web720.toml - Web-optimized 720p

```toml
[video]
codec = "libx264"
crf = 23
max_width = 1280
max_height = 720

[audio]
codec = "aac"
bitrate = 128
channels = 2

[processing]
crop = true
scale = true

[limits]
max_bitrate = 2500
```

### max4g.toml - Maximum 4GB output

```toml
[video]
codec = "libx264"
max_width = 1920
max_height = 1080

[audio]
codec = "aac"
bitrate = 384
channels = 6

[processing]
crop = false
scale = false

[limits]
max_size_mb = 4096
max_bitrate = 8192
```

## Subdirectory-as-Profile

When processing in batch mode, files in subdirectories of `in/` automatically use the matching profile:

```
in/
├── movie.mkv           # Uses 'default' profile
├── copy_video/
│   └── show.mkv        # Uses 'copy_video' profile
├── web720/
│   └── clip.mkv        # Uses 'web720' profile
└── cgi/
    └── animation.mkv   # Uses 'cgi' profile
```

This enables completely hands-free processing based on file placement.
