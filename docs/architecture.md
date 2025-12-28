# Architecture

mmprocess is a Python-based video transcoding pipeline.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              cli.py                                      │
│                    Entry point, argument parsing                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            pipeline.py                                   │
│                    Processing orchestration                              │
│                                                                          │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│   │ run_single() │    │ run_batch()  │    │process_file()│             │
│   └──────────────┘    └──────────────┘    └──────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│    probe.py     │      │  calculate.py   │      │   encode.py     │
│ Media analysis  │      │ Scale/bitrate   │      │ FFmpeg encoding │
└─────────────────┘      └─────────────────┘      └─────────────────┘
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   filters.py    │      │    state.py     │      │     mux.py      │
│ Filter chains   │      │ Job persistence │      │ Container mux   │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

## Modules

### cli.py

Command-line interface using argparse.

- Parses arguments
- Dispatches to pipeline.run_single() or pipeline.run_batch()

### config.py

Configuration management.

- Loads main config from TOML (XDG compliant location)
- Loads profiles from profiles directory
- Dataclasses for typed configuration

### pipeline.py

Processing orchestration.

- **run_single()**: Process a single file
- **run_batch()**: Scan input directory and process queue
- **process_file()**: Execute processing steps for one file
- File locking for concurrent access
- Directory management (in → work → done/error)

### probe.py

Media analysis using ffprobe.

- Extract video stream info (codec, resolution, fps)
- Extract audio stream info (codec, channels, bitrate)
- Crop detection using ffmpeg cropdetect filter

### calculate.py

Video processing calculations.

- Scale calculation respecting constraints
- Bitrate calculation from size limits
- Bits-per-pixel quality estimation

### filters.py

FFmpeg filter chain construction.

- Video filters: crop, scale, deinterlace, denoise
- Audio filters: channel conversion, resampling
- Correct filter ordering

### encode.py

FFmpeg encoding execution.

- Command building for single/multi-pass
- CRF (quality) and bitrate modes
- Pass log management
- Pass tracking in state for resume capability

### mux.py

Container muxing operations.

- MKV muxing via mkvmerge
- MP4 muxing via MP4Box
- Fallback to ffmpeg remux

### state.py

Job state persistence.

- JSON-based state files
- Tracks completed steps for resume
- Input/output metadata

### log.py

Logging configuration.

- Console and file logging
- Per-job log files

### utils.py

Utility functions.

- `fixfname()`: Normalize filenames for Unix/Windows compatibility
  - Replace non-alphanumeric chars with underscore
  - Lowercase everything
  - Replace dots in name (not extension) with underscore
  - Remove leading/trailing underscores
  - Collapse multiple underscores to single

## Data Flow

### Batch Mode

```
1. Scan in/ directory
   ├── Loose files → default profile
   └── Subdirectories → profile name from directory

2. For each file:
   ├── Normalize filename (fixfname)
   ├── Create job directory in work/
   ├── Acquire lock
   ├── Move file to work/{filename}/ (with normalized name)
   ├── Move external .srt if present (also normalized)
   ├── Create state file
   └── Process file

3. Processing steps:
   ├── probe: Analyze input file
   ├── crop: Detect black borders (optional)
   ├── calculate: Determine scale/bitrate
   ├── encode: Run FFmpeg
   ├── mux: Create final container (if needed)
   └── move: Copy to out/

4. Completion:
   ├── Success: Move work/{filename}/ → done/{filename}/
   └── Failure: Move work/{filename}/ → error/{filename}/
```

### Single-File Mode

```
1. Accept file path and optional --profile
2. Create temporary job directory in work/
3. Process file (same steps as batch)
4. Move result to done/ or error/
5. Output file in out/
```

## State Management

Job state is persisted in `state.json` within each job directory:

```json
{
  "version": "2.0.0",
  "profile_name": "cgi",
  "created": "2024-01-15T10:30:00",
  "updated": "2024-01-15T10:35:00",
  "steps_enabled": {
    "probe": true,
    "crop": false,
    "encode": true,
    "mux": true,
    "move": true
  },
  "steps_done": {
    "probe": true,
    "crop": false,
    "encode": true,
    "mux": false,
    "move": false
  },
  "input": {
    "path": "/data/media/convert/work/movie.mkv/movie.mkv",
    "video_codec": "h264",
    "video_width": 1920,
    "video_height": 1080
  },
  "output": {
    "video_codec": "libx264",
    "video_width": 1280,
    "video_height": 720,
    "current_pass": 2,
    "total_passes": 2
  }
}
```

This enables:
- Resume after interruption (including mid-pass for multi-pass encodes)
- Debugging failed jobs
- Tracking which profile was used
- Status monitoring via `getstat`

## External Tools

| Tool | Purpose |
|------|---------|
| ffmpeg | Encoding, muxing, crop detection |
| ffprobe | Media analysis |
| mkvmerge | MKV container creation |
| MP4Box | MP4 container creation |

FFmpeg is the primary tool. mkvmerge and MP4Box are optional (ffmpeg fallback available).

## Concurrency

- File locking via fcntl prevents concurrent processing of same file
- Multiple instances can run safely (will skip locked files)
- No global lock - different files process in parallel
- Use `mmrun` to manage multiple instances (see docs/tools.md)

## SMART Sizing Algorithm

Calculates target bitrate based on resolution, implementing the formula from the original C code:

```
target_bpp = ref_bpp - ((pixels - ref_pixels) * factor / 1000)
```

Default values:
- ref_bpp = 0.225 (reference BPP at 720x480)
- ref_pixels = 345600 (720x480)
- factor = 0.000061

Example results:
- 720x480 (345,600 pixels) → 0.225 BPP
- 1920x800 (1,536,000 pixels) → 0.152 BPP
- 1920x1080 (2,073,600 pixels) → 0.120 BPP

Higher resolution = lower BPP needed = smaller files.

## Audio Handling

- Selects best audio track by preferred language
- Prefers 5.1 over stereo when multiple tracks exist
- Single output track matching source channels (5.1 or stereo)
- Forces correct 5.1 channel layout (L R C LFE Ls Rs) for QuickTime compatibility

## Subtitle Handling

- External .srt files: If a `.srt` file with the same base name exists alongside the input, it is moved to the job directory and burned in (takes priority over embedded)
- Embedded forced tracks: Detects forced subtitle tracks during probe and burns them in
- Uses FFmpeg subtitles filter with correct stream indexing (subtitle-relative, not global)
- Subtitles applied after final resolution is set

## Compatibility Fixes

- Forces 8-bit output (`-pix_fmt yuv420p`) for QuickTime compatibility
- Uses `-f null -` for pass 1 output (cross-platform)
- Correct channel layout metadata for AAC audio
