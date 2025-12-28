# mmprocess - Multimedia Processing System

**Version:** 1.101.211
**Author:** Stephen P. Shoecraft
**Origin:** ~2005 (file dates lost during system migration; copyright shows 2009-2023)
**Language:** C

A sophisticated batch video transcoding and processing system with intelligent quality/size optimization, multi-pass encoding, and extensive codec support.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Directory Structure](#directory-structure)
5. [Core Modules](#core-modules)
6. [Data Structures](#data-structures)
7. [Processing Pipeline](#processing-pipeline)
8. [Configuration](#configuration)
9. [External Dependencies](#external-dependencies)
10. [Build System](#build-system)
11. [Command-Line Usage](#command-line-usage)
12. [Workflow](#workflow)

---

## Overview

**mmprocess** is a production-grade multimedia transcoding framework designed for automated batch processing and optimization of video files. It intelligently analyzes source media, determines optimal output parameters through compression testing, and produces standardized output using multi-pass encoding strategies.

### Key Capabilities

- **Batch Processing**: Monitors input directories and processes files automatically
- **Multi-Pass Encoding**: Up to 3+ passes for optimal quality/size balance
- **Intelligent Bitrate Calculation**: Compression testing to hit target file sizes
- **Format Detection**: Automatic NTSC/PAL/Film and progressive/interlaced detection
- **Smart Sizing**: Auto-calculate bitrate and resolution from target constraints
- **Multiple Codecs**: x264, xvid, MPEG-2, and lavc (libavcodec) support
- **Multiple Containers**: AVI, MP4, MKV output formats
- **Audio Processing**: Multi-channel encoding, normalization, codec conversion
- **Subtitle Handling**: Extraction and embedding support
- **DVD Ripping**: Direct DVD title processing with chapter support

---

## Features

### Video Processing
- Automatic crop detection (black border removal)
- Resolution scaling with aspect ratio preservation
- Deinterlacing filter support
- Denoising with effectiveness testing
- Frame rate conversion
- Multi-pass encoding with quality metrics (PSNR, SSIM, QP)

### Audio Processing
- Multi-channel audio encoding (AAC, MP3, AC3)
- Audio normalization
- Sample rate conversion
- External audio track support

### Quality Control
- Smart mode: Auto-size based on target file size and quality
- Rate testing: Sample encoding to determine optimal bitrate
- Quality metrics: PSNR, SSIM, QP-based encoding modes
- Configurable bitrate/quality limits

### Workflow Management
- File locking to prevent concurrent processing
- State checkpointing for resume capability
- Error handling with separate error directory
- Configurable processing steps (skip any stage)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           main.c                                     │
│              Entry point, CLI parsing, workflow dispatch             │
└─────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│    scan.c       │      │    work.c       │      │   process.c     │
│ Input directory │ ──▶  │  Work queue     │ ──▶  │ Main processing │
│   monitoring    │      │  management     │      │    pipeline     │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                                           │
                    ┌──────────────────────────────────────┤
                    │                                      │
         ┌──────────┴──────────┐              ┌────────────┴────────────┐
         │  Analysis Layer     │              │   Encoding Layer        │
         ├─────────────────────┤              ├─────────────────────────┤
         │ info.c    - metadata│              │ encode.c  - orchestrate │
         │ format.c  - format  │              │ cmd.c     - build cmds  │
         │ crop.c    - borders │              │ x264.c    - x264 opts   │
         │ scale.c   - sizing  │              │ audio.c   - audio enc   │
         │ smart.c   - auto    │              │ extract.c - streams     │
         │ rate.c    - bitrate │              │ mux.c     - containers  │
         │ dntest.c  - denoise │              │ normalize.c - audio lvl │
         └─────────────────────┘              └─────────────────────────┘
                    │                                      │
                    └──────────────────┬───────────────────┘
                                       ▼
                          ┌─────────────────────────┐
                          │    Support Layer        │
                          ├─────────────────────────┤
                          │ config.c   - config mgmt│
                          │ settings.c - file state │
                          │ tools.c    - tool paths │
                          │ utils.c    - utilities  │
                          └─────────────────────────┘
```

---

## Directory Structure

```
mmprocess/
├── Source Files (31 .c files)
│   ├── main.c          # Entry point, CLI, workflow dispatch
│   ├── process.c       # Main processing pipeline
│   ├── scan.c          # Input directory monitoring
│   ├── work.c          # Work queue management
│   ├── config.c        # Configuration management
│   ├── settings.c      # Per-file settings serialization
│   ├── info.c          # Media metadata extraction
│   ├── format.c        # Format detection (NTSC/PAL)
│   ├── crop.c          # Crop detection
│   ├── scale.c         # Resolution scaling
│   ├── smart.c         # Smart sizing algorithm
│   ├── rate.c          # Bitrate calculation
│   ├── dntest.c        # Denoise testing
│   ├── encode.c        # Encoding orchestration
│   ├── cmd.c           # Command-line building
│   ├── x264.c          # x264 codec options
│   ├── audio.c         # Audio encoding
│   ├── extract.c       # Stream extraction
│   ├── mux.c           # Container muxing
│   ├── normalize.c     # Audio normalization
│   ├── tools.c         # Tool discovery
│   ├── utils.c         # Utility functions
│   ├── mode.c          # Quality metric modes
│   ├── sample.c        # Sample generation
│   ├── fix.c           # Filename fixes
│   ├── cq.c            # Constant quality
│   └── ...             # Additional modules
│
├── Header Files
│   ├── mmprocess.h     # Main header (247 lines)
│   ├── avfile.h        # File structure definitions (185 lines)
│   ├── config.h        # Configuration structure (54 lines)
│   └── version.h       # Version string
│
├── Build Files
│   ├── Makefile        # Build configuration
│   ├── mkall           # Multi-platform build script
│   └── incv            # Version increment script
│
├── Configuration
│   ├── mmprocess.cfg   # Main configuration file
│   └── cfg/            # Per-file configuration directory
│       └── *.cfg       # Video project configurations
│
├── Documentation
│   ├── changelog       # Version history (150+ entries)
│   ├── audio.txt       # Audio encoding notes
│   ├── filters.txt     # Filter order documentation
│   ├── ideas.txt       # Design concepts
│   └── *.txt           # Various notes
│
└── mmprocess           # Compiled binary (616 KB)
```

---

## Core Modules

### Entry & Workflow

| Module | Lines | Purpose |
|--------|-------|---------|
| `main.c` | 177 | Entry point, CLI parsing, workflow dispatch |
| `scan.c` | 224 | Monitor input directory, move files to work |
| `work.c` | 97 | Work queue processing loop |
| `process.c` | 493 | Central processing pipeline orchestration |

### Analysis

| Module | Lines | Purpose |
|--------|-------|---------|
| `info.c` | 511 | Extract media metadata (FFmpeg/mkvinfo) |
| `format.c` | 301 | Detect NTSC/PAL/Film format |
| `crop.c` | 201 | Auto-detect black borders for cropping |
| `scale.c` | 206 | Calculate output resolution |
| `smart.c` | 260 | Smart sizing algorithm |
| `rate.c` | 551 | Bitrate determination via compression testing |
| `dntest.c` | 193 | Denoise filter effectiveness testing |

### Encoding

| Module | Lines | Purpose |
|--------|-------|---------|
| `encode.c` | 231 | Multi-pass encoding execution |
| `cmd.c` | 443 | Build mencoder/mplayer commands |
| `x264.c` | 462 | x264 codec-specific options |
| `audio.c` | 146 | Audio encoding pipeline |
| `normalize.c` | 64 | Audio level normalization |

### Post-Processing

| Module | Lines | Purpose |
|--------|-------|---------|
| `extract.c` | 285 | Extract video/audio streams |
| `mux.c` | 139 | Multiplex into MP4/MKV containers |
| `sample.c` | 137 | Generate sample files |

### Configuration & Support

| Module | Lines | Purpose |
|--------|-------|---------|
| `config.c` | 366 | Configuration file management |
| `settings.c` | 592 | Per-file settings serialization |
| `tools.c` | 123 | External tool discovery |
| `utils.c` | 310 | Utility functions |
| `mode.c` | 251 | PSNR/SSIM/QP quality modes |

---

## Data Structures

### Primary Structure: `avfile_t` (avfile.h)

The main data structure representing a file being processed:

```c
typedef struct {
    CFG_INFO *cfg;              // Configuration file handle
    steps_t steps;              // Actions to perform
    steps_t done;               // Actions completed

    struct {                    // INPUT metadata
        char name[NAME_SIZE];
        int width, height;
        fp_t fps;
        int length, start, end;
        char vcodec[CODEC_SIZE], acodec[CODEC_SIZE];
        int ahz, ac, abr;       // Audio: sample rate, channels, bitrate
        int sid, vid, aid;      // Stream IDs
        fp_t par, dar;          // Pixel/Display aspect ratio
    } input;

    struct {                    // OUTPUT parameters
        char name[NAME_SIZE];
        int width, height;
        irec_t crop;            // Crop region {w,h,x,y}
        isize_t scale;          // Scale dimensions
        char vfilters[VFILTERS_SIZE];
        char vcodec[CODEC_SIZE], acodec[CODEC_SIZE];
        int vbr, abr;           // Bitrates (kbps)
        long long dest_size;    // Target file size
        fp_t bpf, bpp;          // Bits per frame/pixel
    } output;

    struct {                    // X264 specific
        char opts[VOPTS_SIZE];
        int slow_first, turbo;
        int vbr, pct;
    } x264;

    struct {                    // Processing settings
        int pass, passes;
        int psnr, ssim, qp;     // Quality metrics
        int keep_files;
    } settings;

    struct {                    // Constraints
        int maxp, maxw, maxh, maxb, maxs;
        fp_t maxbpp, minbpp;
    } limits;

    sampdef_t crop, rate, sample;  // Sample definitions
    list tools;                    // External tool list
} avfile_t;
```

### Global Configuration: `struct _config` (config.h)

```c
struct _config {
    struct {
        int ready, fix, single, locking;
    } flags;

    // Directories
    char in_dir[PATH_SIZE];     // Input files
    char work_dir[PATH_SIZE];   // Processing
    char out_dir[PATH_SIZE];    // Output
    char done_dir[PATH_SIZE];   // Completed
    char error_dir[PATH_SIZE];  // Errors
    char temp_dir[PATH_SIZE];   // Temporary

    // Tools
    list tools;                 // External tool list

    // Settings
    char profile_path[PATH_SIZE];
    int niceval;                // Process priority
    char deinter[32];           // Default deinterlacer
    char denoiser[32];          // Default denoiser
    char profile_name[NAME_SIZE];
};
```

### Supporting Types

```c
typedef double fp_t;            // Floating point type

typedef struct {
    int w, h;                   // Width, Height
} isize_t;

typedef struct {
    int w, h, x, y;             // Rectangle
} irec_t;

typedef struct {
    int pct, len;               // Sample: percent of file, length
} sampdef_t;

typedef struct {
    int info, format, crop;     // Processing step flags
    int smart, scale, dntest;
    int rate, encode, extract;
    int wav, norm, audio;
    int mux, move, sample;
} steps_t;

enum VTYPES {
    VTYPE_UNK,                  // Unknown
    VTYPE_PRO,                  // Progressive
    VTYPE_FILM,                 // Film
    VTYPE_INT,                  // Interlaced
    VTYPE_MIX                   // Mixed
};
```

---

## Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PROCESS(filename)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. LOAD_SETTINGS                                                            │
│    └─▶ Load profile → Load per-file .cfg → Initialize avfile_t             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. ANALYSIS PHASE                                                           │
│    ├─▶ GET_INFO()    - Probe source: codec, dimensions, duration, audio    │
│    ├─▶ GET_FORMAT()  - Detect NTSC/PAL/Film                                 │
│    ├─▶ GET_CROP()    - Detect black borders                                 │
│    ├─▶ GET_SMART()   - Auto-select scale+bitrate (if enabled)              │
│    ├─▶ GET_SCALE()   - Calculate output resolution                         │
│    ├─▶ DNTEST()      - Test denoiser effectiveness                         │
│    └─▶ GET_RATE()    - Determine bitrate via compression test              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. ENCODING PHASE                                                           │
│    ├─▶ X264OPTIONS() - Generate x264 params (if auto opts)                 │
│    └─▶ DO_ENCODE()   - Multi-pass encoding                                 │
│        ├─▶ Pass 1: Rate control initialization                             │
│        ├─▶ Pass 2: Quality refinement                                      │
│        └─▶ Pass 3+: Quality comparison (PSNR/SSIM mode)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. POST-PROCESSING PHASE                                                    │
│    ├─▶ NORMALIZE()      - Audio level normalization (if enabled)           │
│    ├─▶ EXTRACT_WAV()    - Extract PCM audio                                │
│    ├─▶ ENCODE_AUDIO()   - Encode audio (faac/nero/mp3)                     │
│    ├─▶ EXTRACT_VIDEO()  - Extract video stream (.264/xvid)                 │
│    ├─▶ EXTRACT_AUDIO()  - Extract audio stream                             │
│    └─▶ MUX()            - Create final container (MP4/MKV)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. COMPLETION                                                               │
│    ├─▶ MOVE()           - Copy to output directory                         │
│    └─▶ SAVE_SETTINGS()  - Checkpoint state to .cfg                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### State Checkpointing

After each major step, progress is saved to the per-file `.cfg` file:

```ini
[DONE]
info=1
format=1
crop=1
scale=1
rate=1
encode=0        # Not yet complete
...
```

This enables **graceful resume** if processing is interrupted.

---

## Configuration

### Main Configuration (`mmprocess.cfg`)

```ini
[mmprocess]
in_dir=/path/to/input
work_dir=/path/to/work
out_dir=/path/to/output
done_dir=/path/to/done
error_dir=/path/to/errors

profile_path=/path/to/profiles
niceval=19

deinter=yadif
denoiser=hqdn3d
```

### Per-File Configuration (`.cfg`)

Each video file gets a configuration with sections:

| Section | Purpose |
|---------|---------|
| `[SETTINGS]` | Encoding settings, filter choices, mode flags |
| `[STEPS]` | Boolean flags for steps to perform |
| `[DONE]` | Boolean flags for completed steps |
| `[INPUT]` | Source file metadata |
| `[OUTPUT]` | Target format and codec settings |
| `[VIDEO]` | Video codec and bitrate |
| `[AUDIO]` | Audio codec and bitrate |
| `[LIMITS]` | Size, bitrate, quality constraints |
| `[SMART]` | Smart sizing parameters |
| `[CROP]` | Crop detection parameters |
| `[RATE]` | Bitrate test parameters |
| `[X264]` | x264 encoder options |

### Configuration Example

```ini
[SETTINGS]
pass=0
passes=2
deinter=yadif
denoiser=hqdn3d

[STEPS]
info=1
format=1
crop=1
scale=1
rate=1
encode=1
mux=1
move=1

[OUTPUT]
vcodec=x264
acodec=faac
format=mp4
vbr=1500
abr=128

[LIMITS]
maxw=1920
maxh=1080
maxs=4000
maxbpp=0.15
minbpp=0.05
```

---

## External Dependencies

### Required Tools

| Tool | Purpose | Used By |
|------|---------|---------|
| **mencoder** | Video encoding | `encode.c`, `cmd.c` |
| **mplayer** | Media analysis/extraction | `info.c`, `extract.c` |
| **ffmpeg** | Format conversion | `mux.c` (alternative) |
| **normalize** | Audio normalization | `normalize.c` |
| **MP4Box** | MP4 container creation | `mux.c` |
| **mkvinfo** | MKV metadata extraction | `info.c` |
| **mkvmerge** | MKV container creation | `mux.c` |
| **mkvextract** | MKV stream extraction | `extract.c` |

### Optional Tools

| Tool | Purpose |
|------|---------|
| **faac** | AAC audio encoding |
| **neroAacEnc** | High-quality AAC encoding |
| **lame** | MP3 audio encoding |
| **lsdvd** | DVD title detection |
| **dvdxchap** | DVD chapter extraction |

### Library Dependency

- **libos**: Custom OS abstraction library for cross-platform support, configuration management, list handling

---

## Build System

### Makefile Targets

```bash
make                    # Build for current platform
make clean              # Clean build artifacts
make install            # Install to /convert/tools/$(OS)/
```

### Multi-Platform Build

```bash
./mkall                 # Build for all platforms
```

Builds for:
- `linux32` - 32-bit Linux
- `linux64` - 64-bit Linux
- `win32` - 32-bit Windows
- `win64` - 64-bit Windows

### Build Flags

| Flag | Purpose |
|------|---------|
| `DEBUG=yes` | Enable debug symbols |
| `LIBOS=yes` | Link with libos library |
| `-DNO_LOCKING` | Disable file locking |
| `-DFFMPEG_MP4` | Use FFmpeg for MP4 muxing |
| `-DMKV_DEMUXER` | Enable MKV demuxer |
| `-DOLD_MPLAYER` | Compatibility with older mplayer |

---

## Command-Line Usage

```
mmprocess [options] [filename]

Options:
  -0          Do everything except encode
  -1          Only process 1st pass
  -2          Only process up to 2nd pass
  -3          Only process up to 3rd pass
  -c <file>   Specify config file
  -f <path>   Specify full path to process single file
  -g          Generate default config file
  -m          Multi-instance mode
  -k <file>   Specify lockfile path
  -o          Create sample only
  -p <name>   Use default profile
  -r          Reset file config (re-run all tests)
  -s <pos>    Set start position (seconds)
  -t          Test config file
  -u <pos>    Set end position (seconds)
  -V          Display version
  -w <name>   Specify work item name
  -x          Don't move output when done
  -z          Zardo zap mode
```

### Examples

```bash
# Process all files in input directory
mmprocess

# Process single file
mmprocess -f /path/to/video.mkv

# Process with specific profile
mmprocess -p high_quality -f video.mkv

# Only run first pass
mmprocess -1 -f video.mkv

# Reset and reprocess
mmprocess -r -f video.mkv
```

---

## Workflow

### Batch Processing Flow

```
1. scan_indir()
   └─▶ Find new files in in_dir
   └─▶ Lock and move to work_dir

2. do_work()
   └─▶ Loop through work_dir
   └─▶ For each file: do_work_item()

3. do_work_item()
   ├─▶ Lock file
   ├─▶ process() - main encoding
   ├─▶ On success: move to done_dir
   ├─▶ On error: move to error_dir
   └─▶ Unlock file

4. Repeat until no new files
```

### Directory Flow

```
in_dir/         ──▶  work_dir/      ──▶  done_dir/
(source files)       (processing)        (completed)
                          │
                          ▼
                     error_dir/
                     (failed)
                          │
                          ▼
                     out_dir/
                     (final output)
```

### Graceful Shutdown

- Create file `work_dir/mmprocess.stop` to signal shutdown
- Current file completes before exit
- State saved for resume

---

## Code Statistics

| Category | Count | Lines |
|----------|-------|-------|
| C Source Files | 31 | 7,148 |
| Header Files | 4 | 487 |
| **Total C Code** | **35** | **7,635** |
| Config Files | 10 | ~500 |
| Documentation | 13 | ~800 |

---

## Version History

The project originated around **2005** (original file timestamps were lost during a system migration). The changelog contains 150+ entries with recorded dates from 2009-2023, documenting:
- Feature additions
- Bug fixes
- Codec support updates
- Performance optimizations

This represents nearly **20 years** of development and refinement.

---

## Notes for Refactoring

### Current Architecture Observations

1. **Single-threaded processing** - Work queue processed sequentially
2. **Heavy external tool dependency** - mencoder/mplayer for core encoding
3. **State stored in files** - `.cfg` files for checkpointing
4. **Platform-specific code paths** - Conditional compilation for Windows/Linux
5. **Global state** - `config` pointer and various global flags
6. **Procedural design** - Functions organized by task, minimal OOP

### Potential Refactoring Considerations

- Modern FFmpeg API could replace mencoder/mplayer dependency
- Parallel processing for multi-file batches
- Database-backed state management vs file-based
- Plugin architecture for codec handlers
- Configuration validation layer
- Unit testing infrastructure

---

## Production Environment

### Directory Layout (`/data/media/convert/`)

```
/data/media/convert/
├── in/                    # Incoming files
│   ├── file.mkv           # Loose files use default profile
│   ├── cgi/               # Subdirectory = profile name
│   │   └── movie.mkv      # Uses 'cgi' profile
│   ├── copy_video/        # Quick remux profile
│   ├── copy_video_ac3/
│   └── ...
├── work/                  # Files being processed
│   ├── movie.mkv/         # Per-file subdirectory
│   │   ├── movie.mkv      # Source file
│   │   ├── movie.mkv.cfg  # State file
│   │   ├── movie.mkv.lock # Lock file
│   │   └── *.log          # Processing logs
│   └── ...
├── done/                  # Completed files
│   └── movie.mkv/         # Per-file subdirectory preserved
│       ├── movie.mkv      # Original source
│       ├── movie.mkv.cfg  # Full processing state
│       ├── pass1.log
│       ├── pass2.log
│       └── ...
├── out/                   # Output files (final encoded)
├── error/                 # Failed processing
├── profiles/              # Profile .cfg files
│   ├── default.cfg
│   ├── cgi.cfg
│   ├── copy_video.cfg
│   └── ...
├── temp/                  # Temporary files
└── tools/                 # External tool binaries
    └── linux64/bin/
```

### Subdirectory-as-Profile Workflow

The key operational feature: **dropping a file into a subdirectory of `in/` automatically selects the profile**.

```
in/copy_video/movie.mkv  →  Uses 'copy_video' profile (quick remux)
in/cgi/movie.mkv         →  Uses 'cgi' profile (720p, 2ch audio)
in/movie.mkv             →  Uses 'default' profile
```

This enables **completely hands-free operation**:
1. Drop file into appropriate `in/` subdirectory (via Samba/NFS)
2. Cron runs `mmprocess` periodically
3. Files are processed automatically
4. Output appears in `out/`, source moves to `done/`

### Multi-Stage Processing

Files can be re-queued for additional processing:

1. **Stage 1**: Drop into `in/copy_video/` → quick remux (copy streams)
2. **Stage 2**: Move from `done/` to `in/cgi/` → full encode with subtitles baked in
3. **Stage 3**: Move to `in/web720/` → create web-optimized version

Each stage creates a new output; source files in `done/` preserve all processing history.

### Profile Format

Profiles are INI files in `/data/media/convert/profiles/`:

```ini
[steps]
crop=no
scale=no

[limits]
maxs=4096
maxp=2073600
maxw=1920
maxh=1080
maxb=6144

[video]
opts=autouhq

[audio]
bitrate=384
channels=6
```

### State File Contents

Per-file `.cfg` in `done/{filename}/` contains complete processing record:

- `PROFILE_NAME` - which profile was used
- `[INPUT]` - source metadata (resolution, codec, duration, etc.)
- `[OUTPUT]` - output settings used
- `[DONE]` - which processing steps completed
- `[VIDEO]`, `[AUDIO]` - codec settings and bitrates
- `[LIMITS]` - constraints applied
- `[SMART]` - smart sizing parameters used

This enables debugging and reproducibility.

---

*Documentation generated for pre-refactoring analysis. Legacy C code preserved in `old/` directory.*
