"""Command-line interface for SecuriFine.

This module provides the main entry point and argument parsing for the
SecuriFine CLI tool.
"""

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from securifine import __version__
from securifine.utils.logging import setup_logging, set_verbosity, set_quiet_mode, get_logger


# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE_ERROR = 2


logger = get_logger("cli")


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all commands and options.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="securifine",
        description="SecuriFine - Safety-Preserving Fine-Tuning Toolkit for Cybersecurity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  securifine evaluate --model http://localhost:8000/v1 --output baseline.json
  securifine compare --baseline baseline.json --comparison finetuned.json
  securifine report --input comparison.json --format html --output report.html
  securifine validate --dataset training_data.jsonl
  securifine hook --tool deepteam --input params.json

For more information, see: https://github.com/clay-good/securifine
""",
    )

    # Global options
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (can be repeated: -v, -vv)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-essential output",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        metavar="FILE",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "-f", "--format",
        type=str,
        choices=["json", "md", "html"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        metavar="FILE",
        help="Configuration file path",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"securifine {__version__}",
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available commands",
    )

    # EVALUATE command
    eval_parser = subparsers.add_parser(
        "evaluate",
        help="Run safety evaluation against a model",
        description="Evaluate a model's safety alignment using the benchmark suite.",
    )
    eval_parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model API URL or 'offline' for offline mode",
    )
    eval_parser.add_argument(
        "--model-key",
        type=str,
        help="API key for model authentication",
    )
    eval_parser.add_argument(
        "--model-name",
        type=str,
        default="default",
        help="Model name for API requests (default: default)",
    )
    eval_parser.add_argument(
        "--responses-file",
        type=str,
        help="Path to pre-computed responses file (for offline mode)",
    )
    eval_parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Request timeout in seconds (default: 60)",
    )

    # COMPARE command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two benchmark results",
        description="Compare baseline and post-training evaluation results.",
    )
    compare_parser.add_argument(
        "--baseline",
        type=str,
        required=True,
        help="Path to baseline benchmark result file",
    )
    compare_parser.add_argument(
        "--comparison",
        type=str,
        required=True,
        help="Path to comparison benchmark result file",
    )

    # REPORT command
    report_parser = subparsers.add_parser(
        "report",
        help="Generate a formatted report from comparison results",
        description="Generate a report in JSON, Markdown, or HTML format.",
    )
    report_parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to comparison result file",
    )

    # VALIDATE command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a training dataset",
        description="Validate a dataset file for format, safety, and integrity.",
    )
    validate_parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to the dataset file to validate",
    )
    validate_parser.add_argument(
        "--registry",
        type=str,
        help="Path to dataset registry file (optional)",
    )
    validate_parser.add_argument(
        "--check-registry",
        type=str,
        metavar="NAME",
        help="Verify dataset against registry entry with given name",
    )

    # HOOK command
    hook_parser = subparsers.add_parser(
        "hook",
        help="Run an external tool via hook",
        description="Execute an external red-team testing tool.",
    )
    hook_parser.add_argument(
        "--tool",
        type=str,
        required=True,
        help="Name of the tool to run",
    )
    hook_parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to JSON input file for the tool",
    )
    hook_parser.add_argument(
        "--hook-config",
        type=str,
        help="Path to hook configuration file",
    )
    hook_parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Execution timeout in seconds (default: 300)",
    )

    # VERSION command (also available via --version)
    subparsers.add_parser(
        "version",
        help="Display version information",
        description="Show SecuriFine version and exit.",
    )

    return parser


def cmd_evaluate(args: argparse.Namespace, config=None) -> int:
    """Execute the evaluate command.

    Args:
        args: Parsed command-line arguments.
        config: Optional configuration object with settings.

    Returns:
        Exit code.
    """
    from securifine.core import (
        Evaluator,
        HTTPModelInterface,
        OfflineModelInterface,
    )
    from securifine.safety import benchmark_result_to_dict

    logger.info(f"Starting evaluation against model: {args.model}")

    # Create model interface
    if args.model.lower() == "offline":
        if not args.responses_file:
            print("Error: --responses-file is required for offline mode", file=sys.stderr)
            return EXIT_USAGE_ERROR

        responses_path = Path(args.responses_file)
        if not responses_path.exists():
            print(f"Error: Responses file not found: {args.responses_file}", file=sys.stderr)
            return EXIT_ERROR

        model = OfflineModelInterface(responses_file=args.responses_file)
        model_id = f"offline:{responses_path.name}"
    else:
        max_retries = config.max_retries if config else 3
        model = HTTPModelInterface(
            base_url=args.model,
            api_key=args.model_key,
            model_name=args.model_name,
            timeout=args.timeout,
            max_retries=max_retries,
        )
        model_id = args.model

    # Run evaluation
    evaluator = Evaluator(model=model)

    def progress_callback(current: int, total: int, prompt_id: str) -> None:
        if not args.quiet:
            print(f"\rEvaluating: {current}/{total} ({prompt_id})", end="", flush=True)

    try:
        result = evaluator.run_benchmark(
            model_identifier=model_id,
            progress_callback=None if args.quiet else progress_callback,
        )
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        print(f"\nError: Evaluation failed: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_ERROR

    if not args.quiet:
        print()  # Newline after progress

    # Output result
    output_data = benchmark_result_to_dict(result)
    output_json = json.dumps(output_data, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Evaluation result written to: {args.output}")
    else:
        print(output_json)

    # Print summary
    if not args.quiet:
        status = "PASSED" if result.overall_passed else "FAILED"
        print(f"\nEvaluation complete: {status} (score: {result.aggregate_score:.3f})")

    return EXIT_SUCCESS if result.overall_passed else EXIT_ERROR


def cmd_compare(args: argparse.Namespace, config=None) -> int:
    """Execute the compare command.

    Args:
        args: Parsed command-line arguments.
        config: Optional configuration object with threshold settings.

    Returns:
        Exit code.
    """
    from securifine.core import Comparator, comparison_result_to_dict

    logger.info(f"Comparing {args.baseline} vs {args.comparison}")

    # Validate files exist
    baseline_path = Path(args.baseline)
    comparison_path = Path(args.comparison)

    if not baseline_path.exists():
        print(f"Error: Baseline file not found: {args.baseline}", file=sys.stderr)
        return EXIT_ERROR

    if not comparison_path.exists():
        print(f"Error: Comparison file not found: {args.comparison}", file=sys.stderr)
        return EXIT_ERROR

    # Run comparison with config thresholds if available
    if config:
        comparator = Comparator(
            severe_regression_threshold=config.severe_regression_threshold,
            significant_decrease_threshold=config.significant_decrease_threshold,
            minor_decrease_threshold=config.minor_decrease_threshold,
        )
    else:
        comparator = Comparator()

    try:
        result = comparator.load_and_compare(args.baseline, args.comparison)
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        print(f"Error: Comparison failed: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_ERROR

    # Output result
    output_data = comparison_result_to_dict(result)
    output_json = json.dumps(output_data, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Comparison result written to: {args.output}")
    else:
        print(output_json)

    # Print summary
    if not args.quiet:
        print(f"\nComparison complete: {result.overall_assessment.upper()}")
        print(f"Aggregate delta: {result.aggregate_delta:+.3f}")
        print(f"Regressions: {len(result.regressions)}, Improvements: {len(result.improvements)}")
        if result.severe_regressions:
            print(f"Severe regressions: {len(result.severe_regressions)}")

    return EXIT_SUCCESS if result.overall_assessment == "passed" else EXIT_ERROR


def cmd_report(args: argparse.Namespace, config=None) -> int:
    """Execute the report command.

    Args:
        args: Parsed command-line arguments.
        config: Optional configuration object (unused, for consistency).

    Returns:
        Exit code.
    """
    from securifine.core import get_reporter, dict_to_comparison_result

    logger.info(f"Generating {args.format} report from {args.input}")

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return EXIT_ERROR

    # Load comparison result
    try:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        comparison = dict_to_comparison_result(data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return EXIT_ERROR
    except KeyError as e:
        print(f"Error: Missing required field in input file: {e}", file=sys.stderr)
        return EXIT_ERROR

    # Generate report
    try:
        reporter = get_reporter(args.format)
        report = reporter.generate(comparison)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    # Output report
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to: {args.output}")
    else:
        print(report)

    return EXIT_SUCCESS


def cmd_validate(args: argparse.Namespace, config=None) -> int:
    """Execute the validate command.

    Args:
        args: Parsed command-line arguments.
        config: Optional configuration object with settings.

    Returns:
        Exit code.
    """
    from securifine.datasets import (
        DatasetValidator,
        DatasetRegistry,
        validation_result_to_dict,
    )

    logger.info(f"Validating dataset: {args.dataset}")

    # Validate file exists
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset file not found: {args.dataset}", file=sys.stderr)
        return EXIT_ERROR

    # Run validation with config limits if available
    if config:
        validator = DatasetValidator(
            max_file_size=config.max_file_size,
            max_entry_count=config.max_entries,
        )
    else:
        validator = DatasetValidator()

    try:
        result = validator.validate(args.dataset)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"Error: Validation failed: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_ERROR

    # Check against registry if requested
    registry_verified = None
    if args.check_registry:
        registry_path = args.registry
        registry = DatasetRegistry(registry_path)

        try:
            registry.load_registry()
            registry_verified = registry.verify_dataset(args.check_registry, args.dataset)
        except Exception as e:
            logger.warning(f"Registry verification failed: {e}")
            registry_verified = False

    # Output result
    output_data = validation_result_to_dict(result)
    if registry_verified is not None:
        output_data["registry_verified"] = registry_verified

    output_json = json.dumps(output_data, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Validation result written to: {args.output}")
    else:
        print(output_json)

    # Print summary
    if not args.quiet:
        status = "VALID" if result.valid else "INVALID"
        print(f"\nValidation complete: {status}")
        print(f"Entries: {result.entry_count}")
        print(f"Warnings: {len(result.warnings)}, Errors: {len(result.errors)}")

        if registry_verified is not None:
            reg_status = "VERIFIED" if registry_verified else "MISMATCH"
            print(f"Registry check: {reg_status}")

    return EXIT_SUCCESS if result.valid else EXIT_ERROR


def cmd_hook(args: argparse.Namespace, config=None) -> int:
    """Execute the hook command.

    Args:
        args: Parsed command-line arguments.
        config: Optional configuration object (unused, for consistency).

    Returns:
        Exit code.
    """
    from securifine.integration import (
        HookRunner,
        HookConfig,
        load_hook_config,
        hook_result_to_dict,
        get_deepteam_hook_config,
        get_pyrit_hook_config,
    )

    logger.info(f"Running hook: {args.tool}")

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return EXIT_ERROR

    # Load input data
    try:
        with input_path.open("r", encoding="utf-8") as f:
            input_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return EXIT_ERROR

    # Get or load hook configuration
    runner = HookRunner()

    if args.hook_config:
        # Load from config file
        config_path = Path(args.hook_config)
        if not config_path.exists():
            print(f"Error: Hook config file not found: {args.hook_config}", file=sys.stderr)
            return EXIT_ERROR

        try:
            config = load_hook_config(args.hook_config)
        except Exception as e:
            print(f"Error: Failed to load hook config: {e}", file=sys.stderr)
            return EXIT_ERROR
    else:
        # Use built-in configuration
        tool_lower = args.tool.lower()
        if tool_lower == "deepteam":
            config = get_deepteam_hook_config()
        elif tool_lower == "pyrit":
            config = get_pyrit_hook_config()
        else:
            print(
                f"Error: Unknown tool '{args.tool}'. "
                "Use --hook-config to provide a configuration file.",
                file=sys.stderr,
            )
            return EXIT_USAGE_ERROR

    # Override timeout if specified
    if args.timeout != 300:
        config = HookConfig(
            tool_name=config.tool_name,
            command=config.command,
            timeout_seconds=args.timeout,
            input_format=config.input_format,
            output_format=config.output_format,
            working_directory=config.working_directory,
            environment=config.environment,
        )

    # Run hook
    try:
        result = runner.run_hook_with_config(config, input_data)
    except Exception as e:
        logger.error(f"Hook execution failed: {e}")
        print(f"Error: Hook execution failed: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_ERROR

    # Output result
    output_data = hook_result_to_dict(result)
    output_json = json.dumps(output_data, indent=2)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Hook result written to: {args.output}")
    else:
        print(output_json)

    # Print summary
    if not args.quiet:
        status = "SUCCESS" if result.success else "FAILED"
        print(f"\nHook execution: {status}")
        print(f"Exit code: {result.exit_code}")
        print(f"Duration: {result.duration_seconds:.2f}s")

    return EXIT_SUCCESS if result.success else EXIT_ERROR


def cmd_version(args: argparse.Namespace, config=None) -> int:
    """Execute the version command.

    Args:
        args: Parsed command-line arguments.
        config: Optional configuration object (unused, for consistency).

    Returns:
        Exit code.
    """
    print(f"SecuriFine version {__version__}")
    print("Safety-Preserving Fine-Tuning Toolkit for Cybersecurity")
    print("https://github.com/clay-good/securifine")
    return EXIT_SUCCESS


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the SecuriFine CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    from securifine.config import get_effective_config, ConfigError

    parser = create_parser()
    args = parser.parse_args(argv)

    # Load configuration (file + environment + CLI args)
    try:
        config = get_effective_config(
            config_path=args.config if hasattr(args, "config") else None,
            args=args,
        )
    except ConfigError as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return EXIT_ERROR

    # Setup logging based on effective config
    setup_logging()

    if args.quiet:
        set_quiet_mode(True)
    elif args.verbose:
        set_verbosity(args.verbose)
    elif config.log_level:
        import logging
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        level = level_map.get(config.log_level.upper(), logging.WARNING)
        set_verbosity(2 if level == logging.DEBUG else 1 if level == logging.INFO else 0)

    # Handle no command
    if args.command is None:
        parser.print_help()
        return EXIT_SUCCESS

    # Dispatch to command handler
    command_handlers = {
        "evaluate": cmd_evaluate,
        "compare": cmd_compare,
        "report": cmd_report,
        "validate": cmd_validate,
        "hook": cmd_hook,
        "version": cmd_version,
    }

    handler = command_handlers.get(args.command)
    if handler is None:
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        return handler(args, config)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return EXIT_ERROR
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
