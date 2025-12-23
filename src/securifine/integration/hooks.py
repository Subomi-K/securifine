"""Integration hooks module for SecuriFine.

This module provides integration with external red-team testing tools
through a subprocess-based hook system with standardized JSON I/O.
"""

import json
import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from securifine.utils.logging import get_logger


logger = get_logger("hooks")


# Type definitions
InputFormatType = Literal["json", "args"]
OutputFormatType = Literal["json", "text", "none"]


class HookError(Exception):
    """Raised when hook execution fails."""

    pass


class HookValidationError(Exception):
    """Raised when hook configuration is invalid."""

    pass


@dataclass
class HookResult:
    """Result of executing an external tool hook.

    Attributes:
        tool_name: Name of the tool that was executed.
        exit_code: Process exit code.
        stdout: Standard output from the process.
        stderr: Standard error from the process.
        success: Whether the execution was successful.
        duration_seconds: Time taken to execute.
        output_data: Parsed JSON output data (if output_format is json).
    """

    tool_name: str
    exit_code: int
    stdout: str
    stderr: str
    success: bool
    duration_seconds: float
    output_data: Optional[Dict[str, Any]] = None


@dataclass
class HookConfig:
    """Configuration for an external tool hook.

    Attributes:
        tool_name: Unique name identifier for the tool.
        command: Command and arguments template as list of strings.
            Use {input_file} as placeholder for JSON input file path.
        timeout_seconds: Maximum execution time in seconds.
        input_format: How to pass input data ("json" or "args").
        output_format: Expected output format ("json", "text", or "none").
        working_directory: Optional working directory for execution.
        environment: Optional environment variable overrides.
    """

    tool_name: str
    command: List[str]
    timeout_seconds: int = 300
    input_format: InputFormatType = "json"
    output_format: OutputFormatType = "json"
    working_directory: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# BUILT-IN HOOK CONFIGURATIONS
# =============================================================================

def get_deepteam_hook_config(
    executable_path: str = "deepteam",
    config_path: Optional[str] = None,
) -> HookConfig:
    """Get a hook configuration for DeepTeam red-teaming framework.

    This is a template configuration. Users should customize the
    executable path and configuration based on their installation.

    Args:
        executable_path: Path to the DeepTeam executable.
        config_path: Optional path to DeepTeam configuration file.

    Returns:
        HookConfig for DeepTeam integration.
    """
    command = [executable_path, "evaluate", "--input", "{input_file}"]

    if config_path:
        command.extend(["--config", config_path])

    command.append("--output-format=json")

    return HookConfig(
        tool_name="deepteam",
        command=command,
        timeout_seconds=600,
        input_format="json",
        output_format="json",
    )


def get_pyrit_hook_config(
    python_path: str = "python",
    script_path: Optional[str] = None,
) -> HookConfig:
    """Get a hook configuration for PyRIT (Python Risk Identification Toolkit).

    This is a template configuration. Users should customize the
    paths based on their PyRIT installation.

    Args:
        python_path: Path to Python interpreter.
        script_path: Path to PyRIT evaluation script.

    Returns:
        HookConfig for PyRIT integration.
    """
    if script_path is None:
        script_path = "pyrit_evaluate.py"

    return HookConfig(
        tool_name="pyrit",
        command=[python_path, script_path, "--input", "{input_file}"],
        timeout_seconds=600,
        input_format="json",
        output_format="json",
    )


# =============================================================================
# HOOK RUNNER
# =============================================================================

class HookRunner:
    """Manages and executes external tool hooks.

    Provides safe subprocess execution with standardized input/output
    handling for integrating external red-team testing tools.
    """

    def __init__(self) -> None:
        """Initialize the hook runner."""
        self._hooks: Dict[str, HookConfig] = {}

    def register_hook(self, config: HookConfig) -> None:
        """Register a hook configuration.

        Args:
            config: The hook configuration to register.

        Raises:
            HookValidationError: If the configuration is invalid.
        """
        errors = self._validate_config(config)
        if errors:
            raise HookValidationError(f"Invalid hook config: {'; '.join(errors)}")

        self._hooks[config.tool_name] = config
        logger.info(f"Registered hook: {config.tool_name}")

    def unregister_hook(self, tool_name: str) -> None:
        """Unregister a hook.

        Args:
            tool_name: Name of the hook to unregister.
        """
        if tool_name in self._hooks:
            del self._hooks[tool_name]
            logger.info(f"Unregistered hook: {tool_name}")

    def list_hooks(self) -> List[str]:
        """List all registered hook names.

        Returns:
            List of registered hook names.
        """
        return list(self._hooks.keys())

    def get_hook_config(self, tool_name: str) -> Optional[HookConfig]:
        """Get the configuration for a registered hook.

        Args:
            tool_name: Name of the hook.

        Returns:
            The HookConfig if found, None otherwise.
        """
        return self._hooks.get(tool_name)

    def run_hook(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
    ) -> HookResult:
        """Execute a registered hook with the given input.

        Args:
            tool_name: Name of the hook to execute.
            input_data: Input data to pass to the tool.

        Returns:
            HookResult with execution results.

        Raises:
            HookError: If the hook is not registered or execution fails.
        """
        config = self._hooks.get(tool_name)
        if config is None:
            raise HookError(f"Hook '{tool_name}' is not registered")

        return self._execute_hook(config, input_data)

    def run_hook_with_config(
        self,
        config: HookConfig,
        input_data: Dict[str, Any],
    ) -> HookResult:
        """Execute a hook with a provided configuration.

        Useful for one-off executions without registering the hook.

        Args:
            config: The hook configuration to use.
            input_data: Input data to pass to the tool.

        Returns:
            HookResult with execution results.

        Raises:
            HookValidationError: If the configuration is invalid.
            HookError: If execution fails.
        """
        errors = self._validate_config(config)
        if errors:
            raise HookValidationError(f"Invalid hook config: {'; '.join(errors)}")

        return self._execute_hook(config, input_data)

    def _validate_config(self, config: HookConfig) -> List[str]:
        """Validate a hook configuration.

        Args:
            config: The configuration to validate.

        Returns:
            List of validation error messages.
        """
        errors = []

        if not config.tool_name:
            errors.append("Tool name is required")

        if not config.command:
            errors.append("Command is required")

        # Check for dangerous command patterns
        for part in config.command:
            if self._is_dangerous_command_part(part):
                errors.append(f"Potentially dangerous command component: {part}")

        if config.timeout_seconds <= 0:
            errors.append("Timeout must be positive")

        if config.timeout_seconds > 3600:
            errors.append("Timeout exceeds maximum of 1 hour")

        if config.working_directory:
            wd_path = Path(config.working_directory)
            if not wd_path.exists():
                errors.append(f"Working directory does not exist: {config.working_directory}")

        return errors

    def _is_dangerous_command_part(self, part: str) -> bool:
        """Check if a command part contains dangerous patterns.

        Args:
            part: Command component to check.

        Returns:
            True if the part appears dangerous.
        """
        dangerous_patterns = [
            ";",
            "&&",
            "||",
            "|",
            ">",
            "<",
            "`",
            "$(",
            "${",
            "\n",
            "\r",
        ]

        for pattern in dangerous_patterns:
            if pattern in part:
                return True

        return False

    def _execute_hook(
        self,
        config: HookConfig,
        input_data: Dict[str, Any],
    ) -> HookResult:
        """Execute a hook with safe subprocess handling.

        Args:
            config: Hook configuration.
            input_data: Input data for the tool.

        Returns:
            HookResult with execution results.

        Raises:
            HookError: If execution fails.
        """
        logger.info(f"Executing hook: {config.tool_name}")
        start_time = time.time()

        # Prepare input
        input_file = None
        try:
            if config.input_format == "json":
                input_file = self._write_input_file(input_data)
                command = self._substitute_command(config.command, input_file)
            else:
                # args format - convert data to command-line arguments
                command = self._build_args_command(config.command, input_data)

            # Prepare environment
            env = os.environ.copy()
            env.update(config.environment)

            # Prepare working directory
            cwd = config.working_directory

            logger.debug(f"Running command: {' '.join(command)}")

            # Execute subprocess (NO shell=True for security)
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=config.timeout_seconds,
                    cwd=cwd,
                    env=env,
                    shell=False,  # Security: never use shell=True
                )

                duration = time.time() - start_time
                success = result.returncode == 0

                # Parse output
                output_data = None
                if config.output_format == "json" and result.stdout.strip():
                    try:
                        output_data = json.loads(result.stdout)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON output: {e}")

                logger.info(
                    f"Hook {config.tool_name} completed: "
                    f"exit_code={result.returncode}, duration={duration:.2f}s"
                )

                return HookResult(
                    tool_name=config.tool_name,
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    success=success,
                    duration_seconds=duration,
                    output_data=output_data,
                )

            except subprocess.TimeoutExpired:
                duration = time.time() - start_time
                logger.error(f"Hook {config.tool_name} timed out after {config.timeout_seconds}s")

                return HookResult(
                    tool_name=config.tool_name,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Timeout after {config.timeout_seconds} seconds",
                    success=False,
                    duration_seconds=duration,
                )

            except FileNotFoundError as e:
                duration = time.time() - start_time
                logger.error(f"Hook {config.tool_name} command not found: {e}")

                return HookResult(
                    tool_name=config.tool_name,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command not found: {e}",
                    success=False,
                    duration_seconds=duration,
                )

            except OSError as e:
                duration = time.time() - start_time
                logger.error(f"Hook {config.tool_name} OS error: {e}")

                return HookResult(
                    tool_name=config.tool_name,
                    exit_code=-1,
                    stdout="",
                    stderr=f"OS error: {e}",
                    success=False,
                    duration_seconds=duration,
                )

        finally:
            # Clean up input file
            if input_file and Path(input_file).exists():
                try:
                    os.unlink(input_file)
                except OSError:
                    pass

    def _write_input_file(self, data: Dict[str, Any]) -> str:
        """Write input data to a temporary JSON file.

        Args:
            data: Data to write.

        Returns:
            Path to the temporary file.
        """
        fd, path = tempfile.mkstemp(suffix=".json", prefix="securifine_hook_")

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            os.close(fd)
            raise

        logger.debug(f"Wrote input data to {path}")
        return path

    def _substitute_command(
        self,
        command: List[str],
        input_file: str,
    ) -> List[str]:
        """Substitute placeholders in command template.

        Args:
            command: Command template with placeholders.
            input_file: Path to input file.

        Returns:
            Command with placeholders replaced.
        """
        return [
            part.replace("{input_file}", input_file)
            for part in command
        ]

    def _build_args_command(
        self,
        command: List[str],
        data: Dict[str, Any],
    ) -> List[str]:
        """Build command with data as arguments.

        Args:
            command: Base command.
            data: Data to convert to arguments.

        Returns:
            Command with data arguments appended.
        """
        result = list(command)

        for key, value in data.items():
            # Validate key and value to prevent injection
            if not isinstance(key, str) or self._is_dangerous_command_part(key):
                continue

            str_value = str(value)
            if self._is_dangerous_command_part(str_value):
                continue

            result.append(f"--{key}")
            result.append(str_value)

        return result


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def hook_config_to_dict(config: HookConfig) -> Dict[str, Any]:
    """Convert a HookConfig to a JSON-compatible dictionary.

    Args:
        config: The HookConfig to convert.

    Returns:
        Dictionary representation.
    """
    return {
        "tool_name": config.tool_name,
        "command": config.command,
        "timeout_seconds": config.timeout_seconds,
        "input_format": config.input_format,
        "output_format": config.output_format,
        "working_directory": config.working_directory,
        "environment": config.environment,
    }


def dict_to_hook_config(data: Dict[str, Any]) -> HookConfig:
    """Convert a dictionary to a HookConfig.

    Args:
        data: Dictionary to convert.

    Returns:
        HookConfig object.
    """
    return HookConfig(
        tool_name=data["tool_name"],
        command=data["command"],
        timeout_seconds=data.get("timeout_seconds", 300),
        input_format=data.get("input_format", "json"),
        output_format=data.get("output_format", "json"),
        working_directory=data.get("working_directory"),
        environment=data.get("environment", {}),
    )


def hook_result_to_dict(result: HookResult) -> Dict[str, Any]:
    """Convert a HookResult to a JSON-compatible dictionary.

    Args:
        result: The HookResult to convert.

    Returns:
        Dictionary representation.
    """
    return {
        "tool_name": result.tool_name,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.success,
        "duration_seconds": result.duration_seconds,
        "output_data": result.output_data,
    }


def load_hook_config(file_path: Union[str, Path]) -> HookConfig:
    """Load a hook configuration from a JSON file.

    Args:
        file_path: Path to the JSON configuration file.

    Returns:
        HookConfig loaded from file.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        KeyError: If required fields are missing.
    """
    path = Path(file_path)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return dict_to_hook_config(data)


def save_hook_config(config: HookConfig, file_path: Union[str, Path]) -> None:
    """Save a hook configuration to a JSON file.

    Args:
        config: The HookConfig to save.
        file_path: Path to the output JSON file.
    """
    path = Path(file_path)

    data = hook_config_to_dict(config)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
