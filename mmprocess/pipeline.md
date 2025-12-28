# pipeline.py - Processing Orchestration

## Overview

Orchestrates the video transcoding pipeline for both single-file and batch processing modes.

## Processing Flow

```
1. Probe (ffprobe)
   ↓
2. Tier Selection (if configured)  ← Added v2.4.0
   ↓
3. Crop Detection (optional)
   ↓
4. Calculate (scale, bitrate)
   ↓
5. Encode (ffmpeg)
   ↓
6. Mux (mkvmerge/MP4Box/ffmpeg)
   ↓
7. Move to output
```

## Key Functions

### Entry Points

- `run_single(config, file_path, profile_name)` - Process a single file
- `run_batch(config)` - Batch mode: process files from input directory

### Core Processing

- `process_file(input_path, job_dir, config, profile, state)` - Main processing pipeline

### File Discovery

- `_find_work_jobs(config)` - Find resumable jobs in work/
- `_find_input_files(config)` - Find new files in input/

## Tier Selection (v2.4.0)

After probing the input file, if the profile has resolution tiers configured:

1. Calculate input pixels (width × height)
2. Find matching tier via `select_tier()`
3. Apply tier overrides via `apply_tier()`

This allows automatic codec/limit switching based on source resolution.

## Concurrency

- Uses POSIX fcntl() locking for NFS compatibility
- Multiple instances can run safely (skip locked files)
- One job per invocation (allows parallel instances to grab different jobs)

## History

- v2.0.0: Initial Python rewrite
- v2.4.0: Added resolution tier selection after probe step
