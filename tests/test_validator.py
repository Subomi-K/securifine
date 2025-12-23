"""Tests for the SecuriFine dataset validator module.

This module contains unit tests for dataset validation, including
format detection, content scanning, and size limit enforcement.
"""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from securifine.datasets.validator import (
    DatasetValidator,
    ValidationWarning,
    ValidationResult,
    detect_format,
    estimate_entry_count,
    validation_result_to_dict,
    dict_to_validation_result,
)


class TestValidationWarning(unittest.TestCase):
    """Tests for the ValidationWarning dataclass."""

    def test_create_warning(self) -> None:
        """Test creating a ValidationWarning."""
        warning = ValidationWarning(
            severity="high",
            category="content",
            message="Test message",
            location="line 42",
        )
        self.assertEqual(warning.severity, "high")
        self.assertEqual(warning.category, "content")
        self.assertEqual(warning.message, "Test message")
        self.assertEqual(warning.location, "line 42")

    def test_create_warning_no_location(self) -> None:
        """Test creating a ValidationWarning without location."""
        warning = ValidationWarning(
            severity="low",
            category="format",
            message="Test",
        )
        self.assertIsNone(warning.location)


class TestValidationResult(unittest.TestCase):
    """Tests for the ValidationResult dataclass."""

    def test_create_valid_result(self) -> None:
        """Test creating a valid ValidationResult."""
        result = ValidationResult(
            file_path="/path/to/file.jsonl",
            valid=True,
            file_hash="abc123",
            entry_count=100,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.file_path, "/path/to/file.jsonl")
        self.assertEqual(result.file_hash, "abc123")
        self.assertEqual(result.entry_count, 100)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(len(result.errors), 0)

    def test_create_result_with_warnings(self) -> None:
        """Test creating a ValidationResult with warnings."""
        warnings = [
            ValidationWarning(
                severity="medium",
                category="content",
                message="Warning 1",
            )
        ]
        result = ValidationResult(
            file_path="/path/to/file.jsonl",
            valid=True,
            file_hash="abc123",
            entry_count=100,
            warnings=warnings,
        )
        self.assertEqual(len(result.warnings), 1)


class TestDetectFormat(unittest.TestCase):
    """Tests for format detection."""

    def test_detect_jsonl_extension(self) -> None:
        """Test detection of JSONL by extension."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            f.write(b'{"test": 1}\n')
            path = f.name

        try:
            result = detect_format(path)
            self.assertEqual(result, "jsonl")
        finally:
            Path(path).unlink()

    def test_detect_json_extension(self) -> None:
        """Test detection of JSON by extension."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"test": 1}\n')
            path = f.name

        try:
            result = detect_format(path)
            self.assertEqual(result, "jsonl")
        finally:
            Path(path).unlink()

    def test_detect_csv_extension(self) -> None:
        """Test detection of CSV by extension."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b'a,b,c\n1,2,3\n')
            path = f.name

        try:
            result = detect_format(path)
            self.assertEqual(result, "csv")
        finally:
            Path(path).unlink()

    def test_detect_parquet_by_magic(self) -> None:
        """Test detection of Parquet by magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f:
            # Write Parquet magic bytes
            f.write(b'PAR1')
            f.write(b'\x00' * 100)
            f.seek(-4, 2)
            f.write(b'PAR1')
            path = f.name

        try:
            result = detect_format(path)
            self.assertEqual(result, "parquet")
        finally:
            Path(path).unlink()

    def test_detect_json_by_content(self) -> None:
        """Test detection of JSON by content."""
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f:
            f.write(b'{"key": "value"}\n')
            path = f.name

        try:
            result = detect_format(path)
            self.assertEqual(result, "jsonl")
        finally:
            Path(path).unlink()


class TestDatasetValidatorJSONL(unittest.TestCase):
    """Tests for JSONL validation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.validator = DatasetValidator()

    def test_validate_valid_jsonl(self) -> None:
        """Test validation of a valid JSONL file."""
        content = '{"text": "Hello"}\n{"text": "World"}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(result.valid)
            self.assertEqual(result.entry_count, 2)
            self.assertEqual(len(result.errors), 0)
        finally:
            Path(path).unlink()

    def test_validate_invalid_json_line(self) -> None:
        """Test validation catches invalid JSON lines."""
        content = '{"valid": true}\nnot json\n{"also_valid": true}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertFalse(result.valid)
            self.assertTrue(any(
                "Invalid JSON" in e.message for e in result.errors
            ))
        finally:
            Path(path).unlink()

    def test_validate_empty_lines_ignored(self) -> None:
        """Test that empty lines are ignored."""
        content = '{"text": "Hello"}\n\n{"text": "World"}\n\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(result.valid)
            self.assertEqual(result.entry_count, 2)
        finally:
            Path(path).unlink()

    def test_validate_file_not_found(self) -> None:
        """Test validation of non-existent file."""
        result = self.validator.validate("/nonexistent/file.jsonl")
        self.assertFalse(result.valid)
        self.assertTrue(any(
            "does not exist" in e.message for e in result.errors
        ))

    def test_validate_detects_duplicates(self) -> None:
        """Test that validation detects duplicate entries."""
        content = '{"text": "same"}\n{"text": "same"}\n{"text": "different"}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(result.valid)  # Duplicates are warnings, not errors
            self.assertTrue(any(
                "duplicate" in w.message.lower() for w in result.warnings
            ))
        finally:
            Path(path).unlink()

    def test_validate_file_size_limit(self) -> None:
        """Test that file size limit is enforced."""
        validator = DatasetValidator(max_file_size=100)

        # Create a file larger than 100 bytes
        content = '{"text": "' + "x" * 200 + '"}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = validator.validate(path)
            self.assertFalse(result.valid)
            self.assertTrue(any(
                "exceeds limit" in e.message for e in result.errors
            ))
        finally:
            Path(path).unlink()

    def test_validate_entry_count_limit(self) -> None:
        """Test that entry count limit is enforced."""
        validator = DatasetValidator(max_entry_count=5)

        # Create a file with more than 5 entries
        content = "\n".join(
            [f'{{"id": {i}}}' for i in range(10)]
        ) + "\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = validator.validate(path)
            self.assertFalse(result.valid)
            self.assertTrue(any(
                "exceeds limit" in e.message for e in result.errors
            ))
        finally:
            Path(path).unlink()


class TestDatasetValidatorCSV(unittest.TestCase):
    """Tests for CSV validation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.validator = DatasetValidator()

    def test_validate_valid_csv(self) -> None:
        """Test validation of a valid CSV file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["col1", "col2", "col3"])
            writer.writerow(["a", "b", "c"])
            writer.writerow(["d", "e", "f"])
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(result.valid)
            self.assertEqual(result.entry_count, 2)  # Excluding header
        finally:
            Path(path).unlink()

    def test_validate_csv_inconsistent_columns(self) -> None:
        """Test validation catches inconsistent column counts."""
        content = "a,b,c\n1,2,3\n4,5\n6,7,8,9\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            # Inconsistent columns are warnings, not errors
            self.assertTrue(any(
                "Inconsistent column count" in w.message
                for w in result.warnings
            ))
        finally:
            Path(path).unlink()


class TestDatasetValidatorParquet(unittest.TestCase):
    """Tests for Parquet validation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.validator = DatasetValidator()

    def test_validate_parquet_magic_bytes(self) -> None:
        """Test validation of Parquet file by magic bytes."""
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".parquet", delete=False
        ) as f:
            # Write valid Parquet magic bytes (header and footer)
            f.write(b'PAR1')
            f.write(b'\x00' * 100)
            f.seek(-4, 2)
            f.write(b'PAR1')
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(result.valid)
            # Should have warning about limited validation
            self.assertTrue(any(
                "external dependencies" in w.message
                for w in result.warnings
            ))
        finally:
            Path(path).unlink()

    def test_validate_invalid_parquet_header(self) -> None:
        """Test validation catches invalid Parquet header."""
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".parquet", delete=False
        ) as f:
            f.write(b'NOTPAR1')
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertFalse(result.valid)
            self.assertTrue(any(
                "missing PAR1" in e.message for e in result.errors
            ))
        finally:
            Path(path).unlink()


class TestContentScanning(unittest.TestCase):
    """Tests for dangerous content detection."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.validator = DatasetValidator()

    def test_detect_script_tag(self) -> None:
        """Test detection of script tags."""
        content = '{"text": "<script>alert(1)</script>"}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(any(
                "Script tag" in w.message for w in result.warnings
            ))
        finally:
            Path(path).unlink()

    def test_detect_sql_injection(self) -> None:
        """Test detection of SQL injection patterns."""
        content = '{"text": "; DROP TABLE users"}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(any(
                "SQL" in w.message for w in result.warnings
            ))
        finally:
            Path(path).unlink()

    def test_detect_shell_injection(self) -> None:
        """Test detection of shell injection patterns."""
        content = '{"text": "; rm -rf /"}\n'

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = self.validator.validate(path)
            self.assertTrue(any(
                "rm command" in w.message.lower() for w in result.warnings
            ))
        finally:
            Path(path).unlink()


class TestEstimateEntryCount(unittest.TestCase):
    """Tests for entry count estimation."""

    def test_estimate_jsonl_entry_count(self) -> None:
        """Test estimation of JSONL entry count."""
        content = "\n".join(
            [f'{{"id": {i}}}' for i in range(100)]
        ) + "\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(content)
            path = f.name

        try:
            estimate = estimate_entry_count(path)
            # Estimate should be roughly 100 (allow some variance)
            self.assertGreater(estimate, 50)
            self.assertLess(estimate, 200)
        finally:
            Path(path).unlink()

    def test_estimate_empty_file(self) -> None:
        """Test estimation for empty file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = f.name

        try:
            estimate = estimate_entry_count(path)
            self.assertEqual(estimate, 0)
        finally:
            Path(path).unlink()


class TestValidationResultSerialization(unittest.TestCase):
    """Tests for ValidationResult serialization."""

    def test_to_dict(self) -> None:
        """Test converting ValidationResult to dictionary."""
        warnings = [
            ValidationWarning(
                severity="medium",
                category="content",
                message="Warning message",
                location="line 1",
            )
        ]
        result = ValidationResult(
            file_path="/path/to/file.jsonl",
            valid=True,
            file_hash="abc123def456",
            entry_count=100,
            warnings=warnings,
            metadata={"format": "jsonl"},
        )

        data = validation_result_to_dict(result)

        self.assertEqual(data["file_path"], "/path/to/file.jsonl")
        self.assertTrue(data["valid"])
        self.assertEqual(data["file_hash"], "abc123def456")
        self.assertEqual(data["entry_count"], 100)
        self.assertEqual(len(data["warnings"]), 1)
        self.assertEqual(data["metadata"]["format"], "jsonl")

    def test_from_dict(self) -> None:
        """Test creating ValidationResult from dictionary."""
        data = {
            "file_path": "/path/to/file.jsonl",
            "valid": True,
            "file_hash": "abc123def456",
            "entry_count": 100,
            "warnings": [
                {
                    "severity": "medium",
                    "category": "content",
                    "message": "Warning",
                    "location": "line 1",
                }
            ],
            "errors": [],
            "metadata": {"format": "jsonl"},
        }

        result = dict_to_validation_result(data)

        self.assertEqual(result.file_path, "/path/to/file.jsonl")
        self.assertTrue(result.valid)
        self.assertEqual(result.file_hash, "abc123def456")
        self.assertEqual(result.entry_count, 100)
        self.assertEqual(len(result.warnings), 1)

    def test_round_trip_serialization(self) -> None:
        """Test round-trip serialization."""
        original = ValidationResult(
            file_path="/path/to/file.jsonl",
            valid=True,
            file_hash="abc123",
            entry_count=50,
            warnings=[
                ValidationWarning(
                    severity="low",
                    category="structure",
                    message="Test",
                )
            ],
        )

        data = validation_result_to_dict(original)
        restored = dict_to_validation_result(data)

        self.assertEqual(original.file_path, restored.file_path)
        self.assertEqual(original.valid, restored.valid)
        self.assertEqual(original.file_hash, restored.file_hash)
        self.assertEqual(original.entry_count, restored.entry_count)
        self.assertEqual(len(original.warnings), len(restored.warnings))


class TestUnsupportedFormat(unittest.TestCase):
    """Tests for unsupported file formats."""

    def test_unsupported_format(self) -> None:
        """Test validation of unsupported file format."""
        validator = DatasetValidator()

        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".xyz", delete=False
        ) as f:
            f.write(b'\x00\x01\x02\x03')  # Binary garbage
            path = f.name

        try:
            result = validator.validate(path)
            self.assertFalse(result.valid)
            self.assertTrue(any(
                "Unsupported" in e.message for e in result.errors
            ))
        finally:
            Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
