"""Tests for the SecuriFine CLI module.

This module contains unit tests for CLI argument parsing, command handlers,
and error handling.
"""

import argparse
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from securifine import __version__
from securifine.cli import (
    create_parser,
    main,
    cmd_version,
    cmd_evaluate,
    cmd_compare,
    cmd_report,
    cmd_validate,
    cmd_hook,
    EXIT_SUCCESS,
    EXIT_ERROR,
    EXIT_USAGE_ERROR,
)


class TestCreateParser(unittest.TestCase):
    """Tests for argument parser creation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.parser = create_parser()

    def test_parser_prog_name(self) -> None:
        """Test that parser has correct program name."""
        self.assertEqual(self.parser.prog, "securifine")

    def test_parser_has_description(self) -> None:
        """Test that parser has a description."""
        self.assertIn("SecuriFine", self.parser.description)

    def test_global_verbose_option(self) -> None:
        """Test --verbose global option parsing."""
        args = self.parser.parse_args(["-v", "version"])
        self.assertEqual(args.verbose, 1)

        args = self.parser.parse_args(["-vv", "version"])
        self.assertEqual(args.verbose, 2)

    def test_global_quiet_option(self) -> None:
        """Test --quiet global option parsing."""
        args = self.parser.parse_args(["-q", "version"])
        self.assertTrue(args.quiet)

    def test_global_output_option(self) -> None:
        """Test --output global option parsing."""
        args = self.parser.parse_args(["-o", "output.json", "version"])
        self.assertEqual(args.output, "output.json")

    def test_global_format_option(self) -> None:
        """Test --format global option parsing."""
        for fmt in ["json", "md", "html"]:
            args = self.parser.parse_args(["-f", fmt, "version"])
            self.assertEqual(args.format, fmt)

    def test_global_config_option(self) -> None:
        """Test --config global option parsing."""
        args = self.parser.parse_args(["-c", "config.json", "version"])
        self.assertEqual(args.config, "config.json")

    def test_version_command(self) -> None:
        """Test version command is recognized."""
        args = self.parser.parse_args(["version"])
        self.assertEqual(args.command, "version")


class TestEvaluateCommand(unittest.TestCase):
    """Tests for the evaluate command argument parsing."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.parser = create_parser()

    def test_evaluate_requires_model(self) -> None:
        """Test that evaluate command requires --model argument."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["evaluate"])

    def test_evaluate_with_model_url(self) -> None:
        """Test evaluate command with model URL."""
        args = self.parser.parse_args(
            ["evaluate", "--model", "http://localhost:8000/v1"]
        )
        self.assertEqual(args.command, "evaluate")
        self.assertEqual(args.model, "http://localhost:8000/v1")

    def test_evaluate_offline_mode(self) -> None:
        """Test evaluate command in offline mode."""
        args = self.parser.parse_args([
            "evaluate",
            "--model", "offline",
            "--responses-file", "responses.json"
        ])
        self.assertEqual(args.model, "offline")
        self.assertEqual(args.responses_file, "responses.json")

    def test_evaluate_with_api_key(self) -> None:
        """Test evaluate command with API key."""
        args = self.parser.parse_args([
            "evaluate",
            "--model", "http://localhost:8000",
            "--model-key", "sk-test-key"
        ])
        self.assertEqual(args.model_key, "sk-test-key")

    def test_evaluate_with_model_name(self) -> None:
        """Test evaluate command with model name."""
        args = self.parser.parse_args([
            "evaluate",
            "--model", "http://localhost:8000",
            "--model-name", "llama-3-70b"
        ])
        self.assertEqual(args.model_name, "llama-3-70b")

    def test_evaluate_timeout_default(self) -> None:
        """Test evaluate command timeout default value."""
        args = self.parser.parse_args([
            "evaluate",
            "--model", "http://localhost:8000"
        ])
        self.assertEqual(args.timeout, 60)

    def test_evaluate_with_timeout(self) -> None:
        """Test evaluate command with custom timeout."""
        args = self.parser.parse_args([
            "evaluate",
            "--model", "http://localhost:8000",
            "--timeout", "120"
        ])
        self.assertEqual(args.timeout, 120)


class TestCompareCommand(unittest.TestCase):
    """Tests for the compare command argument parsing."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.parser = create_parser()

    def test_compare_requires_baseline(self) -> None:
        """Test that compare command requires --baseline argument."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["compare", "--comparison", "comp.json"])

    def test_compare_requires_comparison(self) -> None:
        """Test that compare command requires --comparison argument."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["compare", "--baseline", "base.json"])

    def test_compare_with_both_files(self) -> None:
        """Test compare command with both required files."""
        args = self.parser.parse_args([
            "compare",
            "--baseline", "baseline.json",
            "--comparison", "comparison.json"
        ])
        self.assertEqual(args.command, "compare")
        self.assertEqual(args.baseline, "baseline.json")
        self.assertEqual(args.comparison, "comparison.json")


class TestReportCommand(unittest.TestCase):
    """Tests for the report command argument parsing."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.parser = create_parser()

    def test_report_requires_input(self) -> None:
        """Test that report command requires --input argument."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["report"])

    def test_report_with_input(self) -> None:
        """Test report command with input file."""
        args = self.parser.parse_args([
            "report",
            "--input", "comparison.json"
        ])
        self.assertEqual(args.command, "report")
        self.assertEqual(args.input, "comparison.json")

    def test_report_with_format(self) -> None:
        """Test report command with format option."""
        args = self.parser.parse_args([
            "-f", "html",
            "report",
            "--input", "comparison.json"
        ])
        self.assertEqual(args.format, "html")


class TestValidateCommand(unittest.TestCase):
    """Tests for the validate command argument parsing."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.parser = create_parser()

    def test_validate_requires_dataset(self) -> None:
        """Test that validate command requires --dataset argument."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["validate"])

    def test_validate_with_dataset(self) -> None:
        """Test validate command with dataset file."""
        args = self.parser.parse_args([
            "validate",
            "--dataset", "training_data.jsonl"
        ])
        self.assertEqual(args.command, "validate")
        self.assertEqual(args.dataset, "training_data.jsonl")

    def test_validate_with_registry(self) -> None:
        """Test validate command with registry file."""
        args = self.parser.parse_args([
            "validate",
            "--dataset", "training_data.jsonl",
            "--registry", "registry.json"
        ])
        self.assertEqual(args.registry, "registry.json")

    def test_validate_with_check_registry(self) -> None:
        """Test validate command with registry check."""
        args = self.parser.parse_args([
            "validate",
            "--dataset", "training_data.jsonl",
            "--check-registry", "my-dataset"
        ])
        self.assertEqual(args.check_registry, "my-dataset")


class TestHookCommand(unittest.TestCase):
    """Tests for the hook command argument parsing."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.parser = create_parser()

    def test_hook_requires_tool(self) -> None:
        """Test that hook command requires --tool argument."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["hook", "--input", "input.json"])

    def test_hook_requires_input(self) -> None:
        """Test that hook command requires --input argument."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["hook", "--tool", "deepteam"])

    def test_hook_with_required_args(self) -> None:
        """Test hook command with required arguments."""
        args = self.parser.parse_args([
            "hook",
            "--tool", "deepteam",
            "--input", "input.json"
        ])
        self.assertEqual(args.command, "hook")
        self.assertEqual(args.tool, "deepteam")
        self.assertEqual(args.input, "input.json")

    def test_hook_timeout_default(self) -> None:
        """Test hook command timeout default value."""
        args = self.parser.parse_args([
            "hook",
            "--tool", "deepteam",
            "--input", "input.json"
        ])
        self.assertEqual(args.timeout, 300)

    def test_hook_with_custom_timeout(self) -> None:
        """Test hook command with custom timeout."""
        args = self.parser.parse_args([
            "hook",
            "--tool", "deepteam",
            "--input", "input.json",
            "--timeout", "600"
        ])
        self.assertEqual(args.timeout, 600)

    def test_hook_with_config(self) -> None:
        """Test hook command with hook config file."""
        args = self.parser.parse_args([
            "hook",
            "--tool", "custom",
            "--input", "input.json",
            "--hook-config", "hook_config.json"
        ])
        self.assertEqual(args.hook_config, "hook_config.json")


class TestCmdVersion(unittest.TestCase):
    """Tests for the version command handler."""

    def test_version_output(self) -> None:
        """Test that version command outputs version string."""
        args = argparse.Namespace()

        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = cmd_version(args)

        output = mock_stdout.getvalue()
        self.assertEqual(result, EXIT_SUCCESS)
        self.assertIn(__version__, output)
        self.assertIn("SecuriFine", output)


class TestMainFunction(unittest.TestCase):
    """Tests for the main entry point function."""

    @mock.patch("securifine.config.get_effective_config")
    def test_main_no_command_shows_help(self, mock_config) -> None:
        """Test that main with no command shows help."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = main([])

        output = mock_stdout.getvalue()
        self.assertEqual(result, EXIT_SUCCESS)
        self.assertIn("securifine", output.lower())

    @mock.patch("securifine.config.get_effective_config")
    def test_main_version_command(self, mock_config) -> None:
        """Test main with version command."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = main(["version"])

        output = mock_stdout.getvalue()
        self.assertEqual(result, EXIT_SUCCESS)
        self.assertIn(__version__, output)

    @mock.patch("securifine.config.get_effective_config")
    def test_main_invalid_format_option(self, mock_config) -> None:
        """Test main with invalid format option."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        # argparse should reject invalid format
        with self.assertRaises(SystemExit):
            main(["-f", "invalid", "version"])


class TestCmdEvaluateOffline(unittest.TestCase):
    """Tests for the evaluate command in offline mode."""

    @mock.patch("securifine.config.get_effective_config")
    def test_evaluate_offline_missing_responses_file(self, mock_config) -> None:
        """Test that offline mode requires responses file."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = main(["evaluate", "--model", "offline"])

        self.assertEqual(result, EXIT_USAGE_ERROR)
        self.assertIn("responses-file", mock_stderr.getvalue())

    @mock.patch("securifine.config.get_effective_config")
    def test_evaluate_offline_missing_file(self, mock_config) -> None:
        """Test that offline mode fails gracefully with missing file."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = main([
                "evaluate",
                "--model", "offline",
                "--responses-file", "/nonexistent/responses.json"
            ])

        self.assertEqual(result, EXIT_ERROR)
        self.assertIn("not found", mock_stderr.getvalue())


class TestCmdCompareErrors(unittest.TestCase):
    """Tests for compare command error handling."""

    @mock.patch("securifine.config.get_effective_config")
    def test_compare_missing_baseline(self, mock_config) -> None:
        """Test that compare fails gracefully with missing baseline."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            comparison_path = f.name

        try:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = main([
                    "compare",
                    "--baseline", "/nonexistent/baseline.json",
                    "--comparison", comparison_path
                ])

            self.assertEqual(result, EXIT_ERROR)
            self.assertIn("not found", mock_stderr.getvalue())
        finally:
            Path(comparison_path).unlink()

    @mock.patch("securifine.config.get_effective_config")
    def test_compare_missing_comparison(self, mock_config) -> None:
        """Test that compare fails gracefully with missing comparison."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            baseline_path = f.name

        try:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = main([
                    "compare",
                    "--baseline", baseline_path,
                    "--comparison", "/nonexistent/comparison.json"
                ])

            self.assertEqual(result, EXIT_ERROR)
            self.assertIn("not found", mock_stderr.getvalue())
        finally:
            Path(baseline_path).unlink()


class TestCmdReportErrors(unittest.TestCase):
    """Tests for report command error handling."""

    @mock.patch("securifine.config.get_effective_config")
    def test_report_missing_input(self, mock_config) -> None:
        """Test that report fails gracefully with missing input."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = main([
                "report",
                "--input", "/nonexistent/comparison.json"
            ])

        self.assertEqual(result, EXIT_ERROR)
        self.assertIn("not found", mock_stderr.getvalue())

    @mock.patch("securifine.config.get_effective_config")
    def test_report_invalid_json(self, mock_config) -> None:
        """Test that report fails gracefully with invalid JSON."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json")
            input_path = f.name

        try:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = main([
                    "report",
                    "--input", input_path
                ])

            self.assertEqual(result, EXIT_ERROR)
            self.assertIn("Invalid JSON", mock_stderr.getvalue())
        finally:
            Path(input_path).unlink()


class TestCmdValidateErrors(unittest.TestCase):
    """Tests for validate command error handling."""

    @mock.patch("securifine.config.get_effective_config")
    def test_validate_missing_dataset(self, mock_config) -> None:
        """Test that validate fails gracefully with missing dataset."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = main([
                "validate",
                "--dataset", "/nonexistent/dataset.jsonl"
            ])

        self.assertEqual(result, EXIT_ERROR)
        self.assertIn("not found", mock_stderr.getvalue())


class TestCmdHookErrors(unittest.TestCase):
    """Tests for hook command error handling."""

    @mock.patch("securifine.config.get_effective_config")
    def test_hook_missing_input(self, mock_config) -> None:
        """Test that hook fails gracefully with missing input."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            result = main([
                "hook",
                "--tool", "deepteam",
                "--input", "/nonexistent/input.json"
            ])

        self.assertEqual(result, EXIT_ERROR)
        self.assertIn("not found", mock_stderr.getvalue())

    @mock.patch("securifine.config.get_effective_config")
    def test_hook_unknown_tool(self, mock_config) -> None:
        """Test that hook fails gracefully with unknown tool."""
        from securifine.config import SecuriFineConfig
        mock_config.return_value = SecuriFineConfig()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "data"}, f)
            input_path = f.name

        try:
            with mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                result = main([
                    "hook",
                    "--tool", "unknown_tool",
                    "--input", input_path
                ])

            self.assertEqual(result, EXIT_USAGE_ERROR)
            self.assertIn("Unknown tool", mock_stderr.getvalue())
        finally:
            Path(input_path).unlink()


if __name__ == "__main__":
    unittest.main()
