"""Dataset validation module for SecuriFine.

This module provides validation functionality for training datasets,
including format verification, content scanning, and safety checks.
"""

import csv
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Optional, Set, Tuple, Union

from securifine.utils.hashing import compute_file_hash
from securifine.utils.logging import get_logger


logger = get_logger("validator")


# Type definitions
SeverityType = Literal["critical", "high", "medium", "low"]
WarningCategory = Literal["format", "content", "size", "structure"]


@dataclass
class ValidationWarning:
    """A warning or error from dataset validation.

    Attributes:
        severity: The severity level of the warning.
        category: The category of the warning.
        message: Description of the issue.
        location: Optional location information (line number, field name, etc.).
    """

    severity: SeverityType
    category: WarningCategory
    message: str
    location: Optional[str] = None


@dataclass
class ValidationResult:
    """Complete result of dataset validation.

    Attributes:
        file_path: Path to the validated file.
        valid: Whether the file passed validation (no critical errors).
        file_hash: SHA-256 hash of the file.
        entry_count: Number of entries in the dataset.
        warnings: List of non-critical warnings.
        errors: List of critical issues.
        metadata: Additional metadata about the file.
    """

    file_path: str
    valid: bool
    file_hash: str
    entry_count: int
    warnings: List[ValidationWarning] = field(default_factory=list)
    errors: List[ValidationWarning] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DatasetValidator:
    """Validates training datasets for safety and correctness.

    Performs format validation, size checks, content scanning,
    and structure verification on dataset files.
    """

    # Default limits
    DEFAULT_MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1 GB
    DEFAULT_MAX_ENTRY_COUNT = 1_000_000  # 1 million entries
    DEFAULT_MAX_LINE_LENGTH = 1_000_000  # 1 million characters per line
    DEFAULT_SAMPLE_SIZE = 1000  # Sample size for duplicate detection

    # Dangerous content patterns (compiled for efficiency)
    # These are heuristic patterns - not exhaustive
    DANGEROUS_PATTERNS = [
        # Executable code patterns
        (re.compile(r"<script[^>]*>", re.IGNORECASE), "Script tag detected"),
        (re.compile(r"javascript:", re.IGNORECASE), "JavaScript URI detected"),
        (re.compile(r"data:text/html", re.IGNORECASE), "Data URI with HTML detected"),
        # Shell injection patterns
        (re.compile(r";\s*rm\s+-rf\s+/", re.IGNORECASE), "Dangerous rm command pattern"),
        (re.compile(r"\|\s*bash", re.IGNORECASE), "Pipe to bash pattern"),
        (re.compile(r"`[^`]*`"), "Backtick command execution"),
        # SQL injection patterns
        (re.compile(r";\s*DROP\s+TABLE", re.IGNORECASE), "SQL DROP TABLE pattern"),
        (re.compile(r";\s*DELETE\s+FROM", re.IGNORECASE), "SQL DELETE pattern"),
        (re.compile(r"UNION\s+SELECT", re.IGNORECASE), "SQL UNION injection pattern"),
    ]

    # Suspicious URL patterns
    SUSPICIOUS_URL_PATTERNS = [
        re.compile(r"https?://[^/]*\.(ru|cn|tk|ml|ga|cf)/", re.IGNORECASE),
        re.compile(r"https?://\d+\.\d+\.\d+\.\d+[:/]", re.IGNORECASE),
    ]

    # Encoding patterns that might hide content
    ENCODING_PATTERNS = [
        (re.compile(r"\\x[0-9a-fA-F]{2}"), "Hex escape sequences"),
        (re.compile(r"\\u[0-9a-fA-F]{4}"), "Unicode escape sequences"),
        (re.compile(r"&#x?[0-9a-fA-F]+;"), "HTML entity encoding"),
    ]

    def __init__(
        self,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE,
        max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
        max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
    ) -> None:
        """Initialize the dataset validator.

        Args:
            max_file_size: Maximum allowed file size in bytes.
            max_entry_count: Maximum allowed number of entries.
            max_line_length: Maximum allowed line length.
            sample_size: Sample size for duplicate detection.
        """
        self.max_file_size = max_file_size
        self.max_entry_count = max_entry_count
        self.max_line_length = max_line_length
        self.sample_size = sample_size

    def validate(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a dataset file.

        Automatically detects the format and applies appropriate validation.

        Args:
            file_path: Path to the dataset file.

        Returns:
            ValidationResult with findings.
        """
        path = Path(file_path)
        logger.info(f"Validating dataset: {path}")

        # Check file exists
        if not path.exists():
            return ValidationResult(
                file_path=str(path),
                valid=False,
                file_hash="",
                entry_count=0,
                errors=[
                    ValidationWarning(
                        severity="critical",
                        category="format",
                        message=f"File does not exist: {path}",
                    )
                ],
            )

        # Check file is readable
        if not path.is_file():
            return ValidationResult(
                file_path=str(path),
                valid=False,
                file_hash="",
                entry_count=0,
                errors=[
                    ValidationWarning(
                        severity="critical",
                        category="format",
                        message=f"Path is not a file: {path}",
                    )
                ],
            )

        # Detect format and validate
        format_type = detect_format(file_path)
        logger.debug(f"Detected format: {format_type}")

        if format_type == "jsonl":
            return self.validate_jsonl(file_path)
        elif format_type == "csv":
            return self.validate_csv(file_path)
        elif format_type == "parquet":
            return self.validate_parquet(file_path)
        else:
            return ValidationResult(
                file_path=str(path),
                valid=False,
                file_hash="",
                entry_count=0,
                errors=[
                    ValidationWarning(
                        severity="critical",
                        category="format",
                        message=f"Unsupported file format: {format_type or 'unknown'}",
                    )
                ],
            )

    def validate_jsonl(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a JSONL (JSON Lines) file.

        Args:
            file_path: Path to the JSONL file.

        Returns:
            ValidationResult with findings.
        """
        path = Path(file_path)
        warnings: List[ValidationWarning] = []
        errors: List[ValidationWarning] = []

        # Check file size
        file_size = path.stat().st_size
        if file_size > self.max_file_size:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="size",
                    message=f"File size ({file_size:,} bytes) exceeds limit ({self.max_file_size:,} bytes)",
                )
            )

        # Compute hash
        file_hash = compute_file_hash(file_path)

        # Validate content
        entry_count = 0
        seen_hashes: Set[str] = set()
        duplicate_count = 0

        try:
            with path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    # Check line length
                    if len(line) > self.max_line_length:
                        warnings.append(
                            ValidationWarning(
                                severity="medium",
                                category="structure",
                                message=f"Line exceeds maximum length ({len(line):,} > {self.max_line_length:,})",
                                location=f"line {line_num}",
                            )
                        )

                    # Skip empty lines
                    stripped = line.strip()
                    if not stripped:
                        continue

                    entry_count += 1

                    # Check entry count limit
                    if entry_count > self.max_entry_count:
                        errors.append(
                            ValidationWarning(
                                severity="critical",
                                category="size",
                                message=f"Entry count exceeds limit ({self.max_entry_count:,})",
                                location=f"line {line_num}",
                            )
                        )
                        break

                    # Parse JSON
                    try:
                        data = json.loads(stripped)
                    except json.JSONDecodeError as e:
                        errors.append(
                            ValidationWarning(
                                severity="critical",
                                category="format",
                                message=f"Invalid JSON: {e}",
                                location=f"line {line_num}",
                            )
                        )
                        continue

                    # Content scanning
                    content_warnings = self._scan_content(data, f"line {line_num}")
                    warnings.extend(content_warnings)

                    # Duplicate detection (sampling-based)
                    if entry_count <= self.sample_size:
                        entry_hash = hash(stripped)
                        if entry_hash in seen_hashes:
                            duplicate_count += 1
                        seen_hashes.add(entry_hash)

        except UnicodeDecodeError as e:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="format",
                    message=f"File encoding error: {e}",
                )
            )
        except IOError as e:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="format",
                    message=f"Error reading file: {e}",
                )
            )

        # Report duplicates
        if duplicate_count > 0:
            warnings.append(
                ValidationWarning(
                    severity="low",
                    category="structure",
                    message=f"Found {duplicate_count} duplicate entries in sample of {min(entry_count, self.sample_size)}",
                )
            )

        valid = len(errors) == 0

        return ValidationResult(
            file_path=str(path),
            valid=valid,
            file_hash=file_hash,
            entry_count=entry_count,
            warnings=warnings,
            errors=errors,
            metadata={
                "format": "jsonl",
                "file_size": file_size,
                "duplicate_count_in_sample": duplicate_count,
            },
        )

    def validate_csv(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a CSV file.

        Args:
            file_path: Path to the CSV file.

        Returns:
            ValidationResult with findings.
        """
        path = Path(file_path)
        warnings: List[ValidationWarning] = []
        errors: List[ValidationWarning] = []

        # Check file size
        file_size = path.stat().st_size
        if file_size > self.max_file_size:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="size",
                    message=f"File size ({file_size:,} bytes) exceeds limit ({self.max_file_size:,} bytes)",
                )
            )

        # Compute hash
        file_hash = compute_file_hash(file_path)

        # Validate content
        entry_count = 0
        header_columns = 0
        seen_hashes: Set[str] = set()
        duplicate_count = 0

        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                # Detect dialect
                sample = f.read(8192)
                f.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(sample)
                    has_header = csv.Sniffer().has_header(sample)
                except csv.Error:
                    dialect = csv.excel
                    has_header = True

                reader = csv.reader(f, dialect)

                for row_num, row in enumerate(reader, 1):
                    # First row - detect header
                    if row_num == 1:
                        header_columns = len(row)
                        if has_header:
                            continue

                    entry_count += 1

                    # Check entry count limit
                    if entry_count > self.max_entry_count:
                        errors.append(
                            ValidationWarning(
                                severity="critical",
                                category="size",
                                message=f"Entry count exceeds limit ({self.max_entry_count:,})",
                                location=f"row {row_num}",
                            )
                        )
                        break

                    # Check column count consistency
                    if len(row) != header_columns:
                        warnings.append(
                            ValidationWarning(
                                severity="medium",
                                category="structure",
                                message=f"Inconsistent column count: expected {header_columns}, got {len(row)}",
                                location=f"row {row_num}",
                            )
                        )

                    # Content scanning
                    for col_idx, cell in enumerate(row):
                        content_warnings = self._scan_content(
                            cell, f"row {row_num}, column {col_idx + 1}"
                        )
                        warnings.extend(content_warnings)

                    # Duplicate detection (sampling-based)
                    if entry_count <= self.sample_size:
                        row_hash = hash(tuple(row))
                        if row_hash in seen_hashes:
                            duplicate_count += 1
                        seen_hashes.add(row_hash)

        except UnicodeDecodeError as e:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="format",
                    message=f"File encoding error: {e}",
                )
            )
        except csv.Error as e:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="format",
                    message=f"CSV parsing error: {e}",
                )
            )
        except IOError as e:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="format",
                    message=f"Error reading file: {e}",
                )
            )

        # Report duplicates
        if duplicate_count > 0:
            warnings.append(
                ValidationWarning(
                    severity="low",
                    category="structure",
                    message=f"Found {duplicate_count} duplicate rows in sample of {min(entry_count, self.sample_size)}",
                )
            )

        valid = len(errors) == 0

        return ValidationResult(
            file_path=str(path),
            valid=valid,
            file_hash=file_hash,
            entry_count=entry_count,
            warnings=warnings,
            errors=errors,
            metadata={
                "format": "csv",
                "file_size": file_size,
                "column_count": header_columns,
                "has_header": has_header,
                "duplicate_count_in_sample": duplicate_count,
            },
        )

    def validate_parquet(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a Parquet file (basic check only, no pandas).

        Since we cannot read Parquet without external dependencies,
        this performs basic file checks only.

        Args:
            file_path: Path to the Parquet file.

        Returns:
            ValidationResult with findings.
        """
        path = Path(file_path)
        warnings: List[ValidationWarning] = []
        errors: List[ValidationWarning] = []

        # Check file size
        file_size = path.stat().st_size
        if file_size > self.max_file_size:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="size",
                    message=f"File size ({file_size:,} bytes) exceeds limit ({self.max_file_size:,} bytes)",
                )
            )

        # Compute hash
        file_hash = compute_file_hash(file_path)

        # Check Parquet magic bytes
        try:
            with path.open("rb") as f:
                # Parquet files start with "PAR1" magic bytes
                header = f.read(4)
                if header != b"PAR1":
                    errors.append(
                        ValidationWarning(
                            severity="critical",
                            category="format",
                            message="Invalid Parquet file: missing PAR1 header",
                        )
                    )

                # Parquet files also end with "PAR1"
                f.seek(-4, 2)
                footer = f.read(4)
                if footer != b"PAR1":
                    errors.append(
                        ValidationWarning(
                            severity="critical",
                            category="format",
                            message="Invalid Parquet file: missing PAR1 footer",
                        )
                    )

        except IOError as e:
            errors.append(
                ValidationWarning(
                    severity="critical",
                    category="format",
                    message=f"Error reading file: {e}",
                )
            )

        # Add warning about limited validation
        warnings.append(
            ValidationWarning(
                severity="low",
                category="format",
                message="Parquet content validation requires external dependencies. "
                "Only basic format checks were performed.",
            )
        )

        valid = len(errors) == 0

        return ValidationResult(
            file_path=str(path),
            valid=valid,
            file_hash=file_hash,
            entry_count=0,  # Cannot determine without pandas
            warnings=warnings,
            errors=errors,
            metadata={
                "format": "parquet",
                "file_size": file_size,
                "note": "Entry count unavailable without pandas",
            },
        )

    def _scan_content(
        self, content: Any, location: str
    ) -> List[ValidationWarning]:
        """Scan content for dangerous patterns.

        Args:
            content: The content to scan (string, dict, or list).
            location: Location string for warning messages.

        Returns:
            List of warnings found.
        """
        warnings: List[ValidationWarning] = []

        # Convert to string for scanning
        if isinstance(content, dict):
            text = json.dumps(content)
        elif isinstance(content, list):
            text = json.dumps(content)
        else:
            text = str(content)

        # Check for dangerous patterns
        for pattern, description in self.DANGEROUS_PATTERNS:
            if pattern.search(text):
                warnings.append(
                    ValidationWarning(
                        severity="high",
                        category="content",
                        message=f"Potentially dangerous content: {description}",
                        location=location,
                    )
                )

        # Check for suspicious URLs
        for pattern in self.SUSPICIOUS_URL_PATTERNS:
            if pattern.search(text):
                warnings.append(
                    ValidationWarning(
                        severity="medium",
                        category="content",
                        message="Suspicious URL pattern detected",
                        location=location,
                    )
                )

        # Check for excessive encoding (might be obfuscation)
        encoding_count = 0
        for pattern, description in self.ENCODING_PATTERNS:
            matches = pattern.findall(text)
            encoding_count += len(matches)

        if encoding_count > 50:
            warnings.append(
                ValidationWarning(
                    severity="medium",
                    category="content",
                    message=f"Excessive encoding detected ({encoding_count} patterns) - may indicate obfuscation",
                    location=location,
                )
            )

        return warnings


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def detect_format(file_path: Union[str, Path]) -> Optional[str]:
    """Detect the format of a dataset file.

    Detection is based on file extension and basic content inspection.

    Args:
        file_path: Path to the file.

    Returns:
        Format string ("jsonl", "csv", "parquet") or None if unknown.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    # Extension-based detection
    extension_map = {
        ".jsonl": "jsonl",
        ".json": "jsonl",  # Assume JSONL for .json files
        ".ndjson": "jsonl",
        ".csv": "csv",
        ".tsv": "csv",
        ".parquet": "parquet",
        ".pq": "parquet",
    }

    if extension in extension_map:
        return extension_map[extension]

    # Content-based detection for unknown extensions
    try:
        with path.open("rb") as f:
            header = f.read(4)

            # Check for Parquet magic bytes
            if header == b"PAR1":
                return "parquet"

            # Check for JSON-like content
            f.seek(0)
            text_header = f.read(100).decode("utf-8", errors="ignore").strip()

            if text_header.startswith("{") or text_header.startswith("["):
                return "jsonl"

    except (IOError, OSError):
        pass

    return None


def estimate_entry_count(file_path: Union[str, Path]) -> int:
    """Estimate the number of entries in a dataset file.

    Uses sampling to estimate without loading the entire file.

    Args:
        file_path: Path to the file.

    Returns:
        Estimated entry count.
    """
    path = Path(file_path)
    file_size = path.stat().st_size

    if file_size == 0:
        return 0

    format_type = detect_format(file_path)

    if format_type in ("jsonl", "csv"):
        # Sample first 100KB to estimate line count
        sample_size = min(102400, file_size)
        line_count = 0

        try:
            with path.open("r", encoding="utf-8") as f:
                sample = f.read(sample_size)
                line_count = sample.count("\n")

                if line_count == 0:
                    return 1  # Single entry without newline

                # Extrapolate
                avg_line_length = sample_size / line_count
                estimated = int(file_size / avg_line_length)

                return estimated

        except (IOError, UnicodeDecodeError):
            return 0

    # Cannot estimate for other formats without dependencies
    return 0


def validation_result_to_dict(result: ValidationResult) -> Dict[str, Any]:
    """Convert a ValidationResult to a JSON-compatible dictionary.

    Args:
        result: The ValidationResult to serialize.

    Returns:
        A dictionary representation.
    """
    return {
        "file_path": result.file_path,
        "valid": result.valid,
        "file_hash": result.file_hash,
        "entry_count": result.entry_count,
        "warnings": [
            {
                "severity": w.severity,
                "category": w.category,
                "message": w.message,
                "location": w.location,
            }
            for w in result.warnings
        ],
        "errors": [
            {
                "severity": e.severity,
                "category": e.category,
                "message": e.message,
                "location": e.location,
            }
            for e in result.errors
        ],
        "metadata": result.metadata,
    }


def dict_to_validation_result(data: Dict[str, Any]) -> ValidationResult:
    """Convert a dictionary to a ValidationResult.

    Args:
        data: The dictionary to deserialize.

    Returns:
        A ValidationResult object.
    """
    return ValidationResult(
        file_path=data["file_path"],
        valid=data["valid"],
        file_hash=data["file_hash"],
        entry_count=data["entry_count"],
        warnings=[
            ValidationWarning(
                severity=w["severity"],
                category=w["category"],
                message=w["message"],
                location=w.get("location"),
            )
            for w in data.get("warnings", [])
        ],
        errors=[
            ValidationWarning(
                severity=e["severity"],
                category=e["category"],
                message=e["message"],
                location=e.get("location"),
            )
            for e in data.get("errors", [])
        ],
        metadata=data.get("metadata", {}),
    )
