"""Hashing utilities for SecuriFine.

This module provides SHA-256 hashing functions for file integrity
verification and content hashing.
"""

import hashlib
from pathlib import Path
from typing import Union


def compute_file_hash(file_path: Union[str, Path], chunk_size: int = 8192) -> str:
    """Compute the SHA-256 hash of a file.

    Reads the file in chunks to handle large files efficiently without
    loading the entire file into memory.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Size of chunks to read at a time (default 8192 bytes).

    Returns:
        The hexadecimal SHA-256 hash of the file contents.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read.
        IsADirectoryError: If the path is a directory.
    """
    sha256_hash = hashlib.sha256()
    path = Path(file_path)

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def compute_string_hash(content: str, encoding: str = "utf-8") -> str:
    """Compute the SHA-256 hash of a string.

    Args:
        content: The string content to hash.
        encoding: The encoding to use when converting to bytes (default utf-8).

    Returns:
        The hexadecimal SHA-256 hash of the string.
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(content.encode(encoding))
    return sha256_hash.hexdigest()


def verify_file_hash(
    file_path: Union[str, Path], expected_hash: str, chunk_size: int = 8192
) -> bool:
    """Verify a file against an expected SHA-256 hash.

    Args:
        file_path: Path to the file to verify.
        expected_hash: The expected hexadecimal SHA-256 hash.
        chunk_size: Size of chunks to read at a time (default 8192 bytes).

    Returns:
        True if the file hash matches the expected hash, False otherwise.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read.
        IsADirectoryError: If the path is a directory.
    """
    actual_hash = compute_file_hash(file_path, chunk_size)
    return actual_hash.lower() == expected_hash.lower()
