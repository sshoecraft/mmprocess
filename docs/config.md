# Configuration Reference

mmprocess uses TOML for configuration files.

## Main Configuration File

Location: `~/.config/mmprocess/config.toml`

### Example Configuration

```toml
[dirs]
base = "/data/media/convert"
in = "in"
out = "out"
work = "work"
done = "done"
error = "error"
temp = "temp"
profiles = "profiles"

[tools]
ffmpeg = "ffmpeg"
ffprobe = "ffprobe"
mp4box = "MP4Box"
mkvmerge = "mkvmerge"

[defaults]
profile = "default"
container = "mkv"
video_codec = "libx264"
audio_codec = "aac"
```

## Configuration Sections

### [dirs]

Directory configuration. Paths can be absolute or relative to `base`.

| Key | Description | Default |
|-----|-------------|---------|
| `base` | Base directory for all paths | `/data/media/convert` |
| `in` | Input directory (incoming files) | `in` |
| `out` | Output directory (encoded files) | `out` |
| `work` | Work directory (files being processed) | `work` |
| `done` | Done directory (source files after processing) | `done` |
| `error` | Error directory (failed processing) | `error` |
| `temp` | Temporary files | `temp` |
| `profiles` | Profile directory | `profiles` |

### [tools]

External tool paths. If not absolute, will search PATH.

| Key | Description | Default |
|-----|-------------|---------|
| `ffmpeg` | FFmpeg executable | `ffmpeg` |
| `ffprobe` | FFprobe executable | `ffprobe` |
| `mp4box` | MP4Box executable (for MP4 muxing) | `MP4Box` |
| `mkvmerge` | mkvmerge executable (for MKV muxing) | `mkvmerge` |

### [defaults]

Default encoding settings.

| Key | Description | Default |
|-----|-------------|---------|
| `profile` | Default profile name | `default` |
| `container` | Default output container | `mkv` |
| `video_codec` | Default video codec | `libx264` |
| `audio_codec` | Default audio codec | `aac` |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XDG_CONFIG_HOME` | Override config directory (default: `~/.config`) |

## Config File Search Order

1. Path specified with `--config` option
2. `$XDG_CONFIG_HOME/mmprocess/config.toml`
3. `~/.config/mmprocess/config.toml`
