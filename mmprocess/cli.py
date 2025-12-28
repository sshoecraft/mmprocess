"""
Command-line interface for mmprocess.
"""

import argparse
import sys
from pathlib import Path

from mmprocess import __version__


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="mmprocess",
        description="Batch video transcoding system with intelligent quality/size optimization",
        epilog="If FILE is not specified, runs in batch mode scanning the input directory.",
    )

    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        metavar="FILE",
        help="Video file to process (single-file mode)",
    )

    parser.add_argument(
        "-p", "--profile",
        metavar="NAME",
        help="Profile to use for encoding",
    )

    parser.add_argument(
        "-c", "--config",
        type=Path,
        metavar="PATH",
        help="Path to config file (default: ~/.config/mmprocess/config.toml)",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        metavar="PATH",
        help="Override output directory",
    )

    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be done without actually processing",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (can be repeated)",
    )

    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main entry point for mmprocess."""
    parsed = parse_args(args)

    # Import here to avoid circular imports and allow CLI to load fast
    from mmprocess.config import load_config
    from mmprocess.log import setup_logging
    from mmprocess.pipeline import run_batch, run_single

    # Setup logging based on verbosity
    setup_logging(parsed.verbose)

    # Load configuration
    config = load_config(parsed.config)

    # Override output directory if specified
    if parsed.output:
        config.dirs.out = parsed.output

    # Run in appropriate mode
    if parsed.file:
        # Single-file mode
        if not parsed.file.exists():
            print(f"Error: File not found: {parsed.file}", file=sys.stderr)
            return 1
        return run_single(config, parsed.file, parsed.profile, parsed.dry_run)
    else:
        # Batch mode
        return run_batch(config, parsed.dry_run)


if __name__ == "__main__":
    sys.exit(main())
