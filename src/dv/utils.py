"""Logging and utility functions for dv."""

import sys
from loguru import logger


def setup_logging(verbose: bool = False) -> None:
    """Configure loguru logging.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise WARNING.
    """
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
