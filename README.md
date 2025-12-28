# mmprocess

Batch video transcoding system with intelligent quality/size optimization.

## Features

- **Batch Processing**: Drop files into directories, processing happens automatically
- **Profile-Based Encoding**: Define encoding presets as TOML profiles
- **Subdirectory-as-Profile**: File placement determines encoding settings
- **Multi-Pass Encoding**: Quality-optimized two-pass encoding
- **Smart Sizing**: Automatic bitrate calculation from size constraints
- **Crop Detection**: Automatic black border detection
- **Resume Support**: State persistence for interrupted jobs
- **FFmpeg-Based**: Modern encoding using FFmpeg

## Requirements

- Python 3.11+
- FFmpeg with ffprobe
- Optional: mkvmerge (MKV muxing), MP4Box (MP4 muxing)

## Installation

```bash
cd /home/steve/src/mmprocess
pip install -e .
```

## Usage

### Single File

```bash
# Process with default profile
mmprocess /path/to/video.mkv

# Process with specific profile
mmprocess -p web720 /path/to/video.mkv
```

### Batch Mode

```bash
# Process all files in configured input directory
mmprocess
```

### Options

```
mmprocess [OPTIONS] [FILE]

Options:
  -p, --profile NAME    Profile to use
  -c, --config PATH     Config file path
  -o, --output PATH     Override output directory
  -n, --dry-run         Show actions without executing
  -v, --verbose         Increase verbosity (repeat for more)
  -V, --version         Show version
```

## Configuration

Main config: `~/.config/mmprocess/config.toml`

```toml
[dirs]
base = "/data/media/convert"
in = "in"
out = "out"
work = "work"
done = "done"
error = "error"
profiles = "profiles"

[tools]
ffmpeg = "ffmpeg"
ffprobe = "ffprobe"

[defaults]
profile = "default"
container = "mkv"
```

## Profiles

Profiles define encoding settings. Place in `{base}/profiles/`:

```toml
# profiles/web720.toml
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
```

## Workflow

### Drop-and-Forget Processing

1. Place files in `in/` subdirectory matching desired profile:
   ```
   in/copy_video/movie.mkv    # Uses copy_video profile
   in/web720/clip.mkv         # Uses web720 profile
   ```

2. Run `mmprocess` (or set up cron)

3. Output appears in `out/`, source moves to `done/`

### Multi-Stage Processing

1. Quick remux: Drop in `in/copy_video/`
2. Re-queue from `done/` to `in/web720/` for web version
3. Re-queue to `in/cgi/` for animated content optimization

## Directory Layout

```
/data/media/convert/
├── in/                 # Incoming files
│   ├── copy_video/     # Profile subdirectories
│   ├── web720/
│   └── cgi/
├── work/               # Files being processed
├── done/               # Completed (source + logs)
├── out/                # Output files
├── error/              # Failed jobs
└── profiles/           # Profile definitions
```

## Documentation

- [Configuration Reference](docs/config.md)
- [Profile Reference](docs/profiles.md)
- [Architecture](docs/architecture.md)
- [Legacy C Version](oldarch.md)

## License

MIT
