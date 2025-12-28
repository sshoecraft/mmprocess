# Command-Line Tools

## mmprocess

Main video transcoding command.

```bash
mmprocess              # Batch mode - process all files in input directories
mmprocess -v           # Verbose output
mmprocess file.mkv     # Single file mode
mmprocess --profile cgi file.mkv  # Specify profile
```

## mmrun

Slot-based process manager for running multiple mmprocess instances.

### Purpose

Ensures a target number of mmprocess instances are running. Designed for cron-based invocation.

### Usage

```bash
mmrun                  # Start instances if needed (up to configured count)
mmrun --status         # Show slot status without starting anything
mmrun --status -v      # Verbose status with details
mmrun -n 5             # Override instance count
mmrun --init           # Create default config file
```

### Configuration

Config file: `~/.config/mmrun/config.json`

```json
{
    "instances": 3,
    "mmprocess_path": "/home/user/.local/bin/mmprocess",
    "mmprocess_args": ["-v"]
}
```

### Log Directory Resolution

1. If `log_dir` set in config → use it
2. Else from mmprocess config (`dirs.work`) → use it
3. Else XDG fallback → `~/.local/state/mmrun/logs`

### Log Files

Named by hostname and slot number:
- Multiple slots: `shep-1.log`, `shep-2.log`, `shep-3.log`
- Single slot: `shep.log`

### Slot Management

- PID files stored in `~/.local/state/mmrun/slot-N.pid`
- Checks system-wide for running mmprocess instances before starting more
- Cleans up stale PID files automatically

### Cron Example

```
*/10 * * * * /home/user/.local/bin/mmrun >> /home/user/logs/mmrun.log 2>&1
```

## getstat

Displays progress of active encoding jobs.

### Usage

```bash
getstat                # Show current status and exit
watch getstat          # Continuous monitoring
getstat -w /path       # Specify work directory
```

### Output Format

```
filename.mkv                    pass 1/2 45.2%    [30 Mins]    120fps 5.0x
```

Fields:
- Filename (truncated to 40 chars)
- Current pass / total passes
- Percent complete
- Estimated time remaining
- FPS and speed multiplier

### Detection

Finds active jobs by:
1. Checking for `.lock` files in work directory
2. Reading `state.json` for duration and pass info (`current_pass`, `total_passes`)
3. Parsing appropriate log file (`pass1.log` or `pass2.log`) for FFmpeg progress
4. Falls back to log file detection for legacy jobs without pass tracking
5. Supports FFmpeg encode format, stream copy format (no fps), and mencoder (old system)

### Stream Copy Jobs

For jobs using `video.codec=copy`, FFmpeg doesn't report frame/fps stats. getstat displays `0fps` for these jobs but time/percent/speed still work correctly.
