"""Utility modules for path handling, hashing, and logging."""

from securifine.utils.paths import (
    PathValidationError,
    validate_file_exists,
    validate_directory_exists,
    normalize_path,
    ensure_parent_directory,
    is_path_within_directory,
    safe_path_join,
)

from securifine.utils.hashing import (
    compute_file_hash,
    compute_string_hash,
    verify_file_hash,
)

from securifine.utils.logging import (
    LOG_FORMAT,
    setup_logging,
    set_verbosity,
    set_quiet_mode,
    get_logger,
)

__all__ = [
    # paths
    "PathValidationError",
    "validate_file_exists",
    "validate_directory_exists",
    "normalize_path",
    "ensure_parent_directory",
    "is_path_within_directory",
    "safe_path_join",
    # hashing
    "compute_file_hash",
    "compute_string_hash",
    "verify_file_hash",
    # logging
    "LOG_FORMAT",
    "setup_logging",
    "set_verbosity",
    "set_quiet_mode",
    "get_logger",
]
