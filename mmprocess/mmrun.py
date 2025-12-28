#!/usr/bin/env python3
"""
new-mmrun - Slot-based process manager for mmprocess encoding jobs.

Ensures a target number of mmprocess instances are running, with each
instance assigned to a numbered slot. Logs are written per-slot using
hostname-based naming.

Config file: ~/.config/mmrun/config.json
"""
import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_CONFIG = {
    "instances": 3,
    "mmprocess_path": "mmprocess",
    "mmprocess_args": ["-v"],
    "state_dir": "~/.local/state/mmrun",
    "log_dir": None,
}


def get_config_path() -> Path:
    """Get path to config file."""
    return Path.home() / ".config" / "mmrun" / "config.json"


def load_config() -> dict:
    """Load config from file, merging with defaults."""
    config_path = get_config_path()

    config = DEFAULT_CONFIG.copy()

    if config_path.exists():
        try:
            with open(config_path) as f:
                user_config = json.load(f)
                config.update(user_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load config: {e}", file=sys.stderr)

    return config


def save_default_config():
    """Create default config file if it doesn't exist."""
    config_path = get_config_path()

    if config_path.exists():
        print(f"Config already exists: {config_path}")
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)

    print(f"Created default config: {config_path}")


def get_state_dir(config: dict) -> Path:
    """Get state directory for PID files."""
    state_dir = Path(os.path.expanduser(config["state_dir"]))
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_log_dir(config: dict) -> Path:
    """Resolve log directory from config, mmprocess, or XDG fallback."""
    # 1. Explicit config
    if config.get("log_dir"):
        log_dir = Path(os.path.expanduser(config["log_dir"]))
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    # 2. From mmprocess config (uses its base/work resolution logic)
    try:
        from mmprocess.config import load_config as load_mmprocess_config
        mmprocess_cfg = load_mmprocess_config()
        return mmprocess_cfg.dirs.work
    except (ImportError, FileNotFoundError, ValueError):
        pass

    # 3. XDG fallback
    log_dir = Path.home() / ".local" / "state" / "mmrun" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def count_running_mmprocess() -> int:
    """Count all running mmprocess instances system-wide."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "mmprocess"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return 0

        pids = [p for p in result.stdout.strip().split("\n") if p]
        count = 0
        my_pid = os.getpid()

        for pid in pids:
            try:
                pid_int = int(pid)
                if pid_int == my_pid:
                    continue

                cmdline_path = f"/proc/{pid}/cmdline"
                if os.path.exists(cmdline_path):
                    with open(cmdline_path, "rb") as f:
                        cmdline = f.read().decode("utf-8", errors="ignore")
                        # Check it's actually mmprocess (not mmrun, editor, etc.)
                        if "mmprocess" in cmdline and "mmrun" not in cmdline:
                            if not any(x in cmdline for x in ["vim", "nano", "grep", "pgrep", "less", "cat", "tail"]):
                                count += 1
            except (ValueError, IOError):
                continue

        return count
    except FileNotFoundError:
        return 0


def get_slot_status(state_dir: Path, instances: int) -> dict[int, int | None]:
    """
    Get status of each slot.

    Returns dict mapping slot number to PID (if running) or None (if free).
    Cleans up stale PID files for dead processes.
    """
    status = {}
    for slot in range(1, instances + 1):
        pid_file = state_dir / f"slot-{slot}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if is_pid_alive(pid):
                    status[slot] = pid
                else:
                    pid_file.unlink()
                    status[slot] = None
            except (ValueError, IOError):
                pid_file.unlink()
                status[slot] = None
        else:
            status[slot] = None
    return status


def get_log_filename(instances: int, slot: int) -> str:
    """Get log filename based on hostname and slot."""
    hostname = socket.gethostname().split('.')[0]
    if instances == 1:
        return f"{hostname}.log"
    return f"{hostname}-{slot}.log"


def start_slot(slot: int, config: dict, state_dir: Path, log_dir: Path) -> int:
    """
    Start mmprocess in the given slot.

    Returns the PID of the started process.
    """
    instances = config["instances"]
    log_file = log_dir / get_log_filename(instances, slot)
    pid_file = state_dir / f"slot-{slot}.pid"

    # Start process with output redirected to log
    with open(log_file, "a") as log_fd:
        proc = subprocess.Popen(
            [config["mmprocess_path"]] + config["mmprocess_args"],
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    # Record PID
    pid_file.write_text(str(proc.pid))
    return proc.pid


def main():
    parser = argparse.ArgumentParser(
        description="Slot-based process manager for mmprocess"
    )
    parser.add_argument(
        "-n", "--instances",
        type=int,
        help="Number of slots to maintain (overrides config)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create default config file"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show slot status only, don't start any processes"
    )

    args = parser.parse_args()

    if args.init:
        save_default_config()
        return 0

    config = load_config()

    if args.instances is not None:
        config["instances"] = args.instances

    instances = config["instances"]
    state_dir = get_state_dir(config)
    log_dir = get_log_dir(config)

    # Check system-wide mmprocess count first
    system_running = count_running_mmprocess()

    # Get slot status for our managed processes
    slot_status = get_slot_status(state_dir, instances)
    slot_running = sum(1 for pid in slot_status.values() if pid is not None)
    free_slots = [slot for slot, pid in slot_status.items() if pid is None]

    if args.verbose or args.status:
        print(f"System: {system_running} mmprocess instance(s) running")
        print(f"Slots: {slot_running}/{instances} managed by mmrun")
        for slot in range(1, instances + 1):
            pid = slot_status.get(slot)
            if pid:
                print(f"  Slot {slot}: running (PID {pid})")
            else:
                print(f"  Slot {slot}: free")
        print(f"Log dir: {log_dir}")

    if args.status:
        return 0

    # Don't start more if system already has enough
    if system_running >= instances:
        if args.verbose:
            print(f"Already {system_running} instance(s) running system-wide, target is {instances}")
        return 0

    # Only start enough to reach target
    to_start = min(len(free_slots), instances - system_running)

    if to_start <= 0:
        if args.verbose:
            print("No new instances needed")
        return 0

    started = 0
    for slot in free_slots[:to_start]:
        pid = start_slot(slot, config, state_dir, log_dir)
        if args.verbose:
            print(f"Started slot {slot} (PID {pid})")
        started += 1

    if started > 0:
        print(f"Started {started} instance(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
