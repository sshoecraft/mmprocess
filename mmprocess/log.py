"""
Logging configuration for mmprocess.
"""

import logging
import sys
from pathlib import Path

# Module-level logger
logger = logging.getLogger("mmprocess")


def setup_logging(verbosity: int = 0, log_file: Path | None = None) -> None:
    """
    Configure logging for mmprocess.

    Args:
        verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG
        log_file: Optional file path for logging output
    """
    # Determine log level based on verbosity
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    # Configure root logger for mmprocess
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def get_job_logger(job_dir: Path, name: str) -> logging.Logger:
    """
    Get a logger for a specific job that writes to the job directory.

    Args:
        job_dir: Directory for job files (work/{filename}/)
        name: Log file name (e.g., "encode", "mux")

    Returns:
        Logger configured to write to job_dir/{name}.log
    """
    job_logger = logging.getLogger(f"mmprocess.job.{name}")
    job_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    job_logger.handlers.clear()

    # Create file handler for this job
    log_file = job_dir / f"{name}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    job_logger.addHandler(file_handler)

    # Don't propagate to parent logger
    job_logger.propagate = False

    return job_logger
