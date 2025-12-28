# config.py - Configuration Management

## Overview

Handles loading of main configuration and encoding profiles from TOML and legacy INI (.cfg) files.

## Key Data Structures

### Configuration Hierarchy

```
Config
├── DirsConfig          # Directory paths
├── ToolsConfig         # External tool paths (ffmpeg, ffprobe, etc.)
└── DefaultsConfig      # Default encoding settings

Profile
├── VideoProfile        # Video codec settings
├── AudioProfile        # Audio codec settings
├── ProcessingProfile   # Processing steps (crop, scale, etc.)
├── LimitsProfile       # Output constraints
├── SmartProfile        # Smart sizing algorithm parameters
└── ResolutionTier[]    # Resolution-based overrides
```

### ResolutionTier (Added v2.4.0)

Allows different codecs and size limits based on input resolution. Useful for:
- Using HEVC (libx265) for 4K sources
- Using H.264 (libx264) for 1080p and below for compatibility
- Different file size limits per resolution tier

Tiers are matched by finding the smallest tier where `input_pixels <= max_pixels`.

## Key Functions

- `load_config(path)` - Load main config from TOML
- `load_profile(config, name)` - Load profile (.cfg or .toml)
- `select_tier(profile, pixels)` - Find matching tier for input resolution
- `apply_tier(profile, tier)` - Apply tier overrides to profile

## File Formats

### Main Config (TOML)

Location: `~/.config/mmprocess/config.toml`

### Profiles

- Legacy: `{base}/profiles/{name}.cfg` (INI format)
- Modern: `{base}/profiles/{name}.toml`

## History

- v2.0.0: Initial Python rewrite with TOML support
- v2.4.0: Added ResolutionTier support for codec/limit switching based on input resolution
