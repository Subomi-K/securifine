"""Logging utilities for SecuriFine.

This module provides logging configuration and utilities for consistent
logging across the SecuriFine package.
"""

import logging
from typing import Optional


# Default log format as specified in instructions
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

# Root logger name for SecuriFine
ROOT_LOGGER_NAME = "securifine"

# Module-level logger instance
_root_logger: Optional[logging.Logger] = None


def setup_logging(
    level: int = logging.WARNING,
    log_format: str = LOG_FORMAT,
) -> logging.Logger:
    """Configure the root SecuriFine logger.

    Sets up the root logger with a console handler and the specified
    format and level.

    Args:
        level: The logging level (default WARNING).
        log_format: The log message format string.

    Returns:
        The configured root logger.
    """
    global _root_logger

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Create formatter and add to handler
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    _root_logger = logger
    return logger


def set_verbosity(verbosity: int) -> None:
    """Set logging level based on verbosity flags.

    Maps verbosity count to logging levels:
    - 0: WARNING (default)
    - 1: INFO
    - 2+: DEBUG

    Args:
        verbosity: The verbosity level (count of -v flags).
    """
    if verbosity <= 0:
        level = logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logger = get_logger()
    logger.setLevel(level)

    for handler in logger.handlers:
        handler.setLevel(level)


def set_quiet_mode(quiet: bool = True) -> None:
    """Enable or disable quiet mode.

    In quiet mode, logging level is set to ERROR to suppress
    non-essential output.

    Args:
        quiet: If True, enable quiet mode; if False, restore WARNING level.
    """
    if quiet:
        level = logging.ERROR
    else:
        level = logging.WARNING

    logger = get_logger()
    logger.setLevel(level)

    for handler in logger.handlers:
        handler.setLevel(level)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger for a specific module.

    If no name is provided, returns the root SecuriFine logger.
    If a name is provided, returns a child logger under the SecuriFine
    namespace.

    Args:
        name: Optional module name for the logger. If provided, the logger
            will be named 'securifine.{name}'.

    Returns:
        The requested logger instance.
    """
    global _root_logger

    # Ensure root logger is set up
    if _root_logger is None:
        setup_logging()

    if name is None:
        return logging.getLogger(ROOT_LOGGER_NAME)

    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
