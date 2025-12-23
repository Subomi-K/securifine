"""Path handling utilities for SecuriFine.

This module provides safe path handling functions including validation,
normalization, and path traversal prevention.
"""

from pathlib import Path
from typing import Union


class PathValidationError(Exception):
    """Raised when path validation fails."""

    pass


def validate_file_exists(path: Union[str, Path]) -> Path:
    """Validate that a path exists and is a file.

    Args:
        path: The path to validate.

    Returns:
        The resolved Path object.

    Raises:
        PathValidationError: If the path does not exist or is not a file.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise PathValidationError(f"Path does not exist: {resolved}")
    if not resolved.is_file():
        raise PathValidationError(f"Path is not a file: {resolved}")
    return resolved


def validate_directory_exists(path: Union[str, Path]) -> Path:
    """Validate that a path exists and is a directory.

    Args:
        path: The path to validate.

    Returns:
        The resolved Path object.

    Raises:
        PathValidationError: If the path does not exist or is not a directory.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise PathValidationError(f"Path does not exist: {resolved}")
    if not resolved.is_dir():
        raise PathValidationError(f"Path is not a directory: {resolved}")
    return resolved


def normalize_path(path: Union[str, Path]) -> Path:
    """Normalize and resolve a path safely.

    This function resolves the path to an absolute path, eliminating any
    symbolic links, '..' components, and redundant separators.

    Args:
        path: The path to normalize.

    Returns:
        The normalized, resolved Path object.

    Raises:
        PathValidationError: If the path cannot be normalized.
    """
    try:
        return Path(path).resolve()
    except (OSError, ValueError) as e:
        raise PathValidationError(f"Cannot normalize path '{path}': {e}")


def ensure_parent_directory(path: Union[str, Path]) -> Path:
    """Ensure that the parent directory of a path exists.

    Creates the parent directory and any necessary intermediate directories
    if they do not exist.

    Args:
        path: The path whose parent directory should exist.

    Returns:
        The resolved Path object.

    Raises:
        PathValidationError: If the parent directory cannot be created.
    """
    resolved = Path(path).resolve()
    parent = resolved.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise PathValidationError(
            f"Cannot create parent directory '{parent}': {e}"
        )
    return resolved


def is_path_within_directory(
    path: Union[str, Path], base_directory: Union[str, Path]
) -> bool:
    """Check if a path is within an allowed base directory.

    This function prevents path traversal attacks by ensuring that the
    resolved path is contained within the specified base directory.

    Args:
        path: The path to check.
        base_directory: The base directory that should contain the path.

    Returns:
        True if the path is within the base directory, False otherwise.
    """
    try:
        resolved_path = Path(path).resolve()
        resolved_base = Path(base_directory).resolve()
        # Use is_relative_to for Python 3.9+
        return resolved_path == resolved_base or resolved_base in resolved_path.parents
    except (OSError, ValueError):
        return False


def safe_path_join(
    base_directory: Union[str, Path], *parts: str
) -> Path:
    """Safely join path components, preventing path traversal.

    Args:
        base_directory: The base directory to join paths within.
        *parts: Path components to join.

    Returns:
        The joined and resolved Path object.

    Raises:
        PathValidationError: If the resulting path would be outside the
            base directory (path traversal attempt).
    """
    resolved_base = Path(base_directory).resolve()
    joined = resolved_base.joinpath(*parts)
    resolved_joined = joined.resolve()

    if not is_path_within_directory(resolved_joined, resolved_base):
        raise PathValidationError(
            f"Path traversal detected: '{'/'.join(parts)}' escapes base directory"
        )

    return resolved_joined
