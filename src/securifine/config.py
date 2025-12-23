"""Configuration system for SecuriFine.

This module provides configuration management including loading from files,
environment variables, and merging with command-line arguments.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Union

from securifine.utils.logging import get_logger


logger = get_logger("config")


# Default configuration directory and file
DEFAULT_CONFIG_DIR = ".securifine"
DEFAULT_CONFIG_FILE = "config.json"

# Environment variable prefix
ENV_PREFIX = "SECURIFINE_"


@dataclass
class SecuriFineConfig:
    """Configuration for SecuriFine.

    Attributes:
        model_url: Default model API URL.
        model_api_key: Default API key for model authentication.
        model_name: Default model name for API requests.
        default_output_format: Default output format (json, md, html).
        registry_path: Path to the dataset registry file.
        hook_configs: Dictionary of hook configurations by tool name.
        evaluation_timeout: Default timeout for model queries in seconds.
        max_file_size: Maximum file size for dataset validation in bytes.
        max_entries: Maximum entry count for dataset validation.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        max_retries: Maximum number of retries for failed API calls.
        severe_regression_threshold: Score drop threshold for severe regression.
        significant_decrease_threshold: Aggregate decrease for failed assessment.
        minor_decrease_threshold: Aggregate decrease for warning assessment.
    """

    model_url: Optional[str] = None
    model_api_key: Optional[str] = None
    model_name: str = "default"
    default_output_format: str = "json"
    registry_path: Optional[str] = None
    hook_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    evaluation_timeout: int = 60
    max_file_size: int = 1073741824  # 1 GB
    max_entries: int = 1000000  # 1M entries
    log_level: str = "WARNING"
    max_retries: int = 3
    severe_regression_threshold: float = 0.15
    significant_decrease_threshold: float = 0.05
    minor_decrease_threshold: float = 0.02


class ConfigError(Exception):
    """Raised when configuration operations fail."""

    pass


def get_default_config_path() -> Path:
    """Get the default configuration file path.

    Returns:
        Path to ~/.securifine/config.json
    """
    home = Path.home()
    return home / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE


def load_config(path: Optional[Union[str, Path]] = None) -> SecuriFineConfig:
    """Load configuration from a JSON file.

    Args:
        path: Path to the configuration file. If None, uses default path.

    Returns:
        SecuriFineConfig with loaded values.

    Raises:
        ConfigError: If the file cannot be read or parsed.
    """
    if path is None:
        config_path = get_default_config_path()
    else:
        config_path = Path(path)

    logger.debug(f"Loading configuration from {config_path}")

    if not config_path.exists():
        logger.info(f"Configuration file not found: {config_path}, using defaults")
        return SecuriFineConfig()

    try:
        with config_path.open("r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            logger.info("Configuration file is empty, using defaults")
            return SecuriFineConfig()

        data = json.loads(content)
        return _dict_to_config(data)

    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in configuration file: {e}")
    except IOError as e:
        raise ConfigError(f"Error reading configuration file: {e}")


def save_config(
    config: SecuriFineConfig,
    path: Optional[Union[str, Path]] = None,
) -> None:
    """Save configuration to a JSON file.

    Args:
        config: The configuration to save.
        path: Path to save to. If None, uses default path.

    Raises:
        ConfigError: If the file cannot be written.
    """
    if path is None:
        config_path = get_default_config_path()
    else:
        config_path = Path(path)

    logger.debug(f"Saving configuration to {config_path}")

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = _config_to_dict(config)

        with config_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Configuration saved to {config_path}")

    except IOError as e:
        raise ConfigError(f"Error writing configuration file: {e}")


def load_from_environment() -> Dict[str, Any]:
    """Load configuration values from environment variables.

    Environment variables are prefixed with SECURIFINE_ and converted
    to lowercase. For example:
    - SECURIFINE_MODEL_URL -> model_url
    - SECURIFINE_LOG_LEVEL -> log_level

    Returns:
        Dictionary of configuration values from environment.
    """
    env_config: Dict[str, Any] = {}

    env_mappings = {
        f"{ENV_PREFIX}MODEL_URL": "model_url",
        f"{ENV_PREFIX}MODEL_API_KEY": "model_api_key",
        f"{ENV_PREFIX}MODEL_NAME": "model_name",
        f"{ENV_PREFIX}DEFAULT_OUTPUT_FORMAT": "default_output_format",
        f"{ENV_PREFIX}REGISTRY_PATH": "registry_path",
        f"{ENV_PREFIX}EVALUATION_TIMEOUT": "evaluation_timeout",
        f"{ENV_PREFIX}MAX_FILE_SIZE": "max_file_size",
        f"{ENV_PREFIX}MAX_ENTRIES": "max_entries",
        f"{ENV_PREFIX}LOG_LEVEL": "log_level",
        f"{ENV_PREFIX}MAX_RETRIES": "max_retries",
        f"{ENV_PREFIX}SEVERE_REGRESSION_THRESHOLD": "severe_regression_threshold",
        f"{ENV_PREFIX}SIGNIFICANT_DECREASE_THRESHOLD": "significant_decrease_threshold",
        f"{ENV_PREFIX}MINOR_DECREASE_THRESHOLD": "minor_decrease_threshold",
    }

    int_keys = ("evaluation_timeout", "max_file_size", "max_entries", "max_retries")
    float_keys = ("severe_regression_threshold", "significant_decrease_threshold", "minor_decrease_threshold")

    for env_var, config_key in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            # Convert numeric values
            if config_key in int_keys:
                try:
                    value = int(value)
                except ValueError:
                    logger.warning(
                        f"Invalid value for {env_var}: {value}, expected integer"
                    )
                    continue
            elif config_key in float_keys:
                try:
                    value = float(value)
                except ValueError:
                    logger.warning(
                        f"Invalid value for {env_var}: {value}, expected float"
                    )
                    continue

            env_config[config_key] = value
            logger.debug(f"Loaded {config_key} from environment variable {env_var}")

    return env_config


def merge_config_with_args(
    config: SecuriFineConfig,
    args: Any,
) -> SecuriFineConfig:
    """Merge configuration with command-line arguments.

    Command-line arguments take precedence over configuration file values.

    Args:
        config: The base configuration.
        args: Parsed argparse.Namespace with command-line arguments.

    Returns:
        New SecuriFineConfig with merged values.
    """
    merged = SecuriFineConfig(
        model_url=config.model_url,
        model_api_key=config.model_api_key,
        model_name=config.model_name,
        default_output_format=config.default_output_format,
        registry_path=config.registry_path,
        hook_configs=dict(config.hook_configs),
        evaluation_timeout=config.evaluation_timeout,
        max_file_size=config.max_file_size,
        log_level=config.log_level,
    )

    # Override with CLI arguments if present
    if hasattr(args, "model") and args.model:
        merged.model_url = args.model

    if hasattr(args, "model_key") and args.model_key:
        merged.model_api_key = args.model_key

    if hasattr(args, "model_name") and args.model_name != "default":
        merged.model_name = args.model_name

    if hasattr(args, "format") and args.format:
        merged.default_output_format = args.format

    if hasattr(args, "registry") and args.registry:
        merged.registry_path = args.registry

    if hasattr(args, "timeout") and args.timeout:
        merged.evaluation_timeout = args.timeout

    # Update log level based on verbosity
    if hasattr(args, "verbose") and args.verbose:
        if args.verbose == 1:
            merged.log_level = "INFO"
        elif args.verbose >= 2:
            merged.log_level = "DEBUG"

    if hasattr(args, "quiet") and args.quiet:
        merged.log_level = "ERROR"

    return merged


def create_default_config() -> SecuriFineConfig:
    """Create a configuration with default values.

    Returns:
        SecuriFineConfig with all default values.
    """
    return SecuriFineConfig()


def ensure_config_exists() -> Path:
    """Ensure the default configuration file exists.

    Creates the configuration directory and a default config file
    if they don't exist.

    Returns:
        Path to the configuration file.
    """
    config_path = get_default_config_path()
    config_dir = config_path.parent

    if not config_dir.exists():
        config_dir.mkdir(parents=True)
        logger.debug(f"Created configuration directory: {config_dir}")

    if not config_path.exists():
        default_config = create_default_config()
        save_config(default_config, config_path)
        logger.info(f"Created default configuration file: {config_path}")

    return config_path


def get_effective_config(
    config_path: Optional[str] = None,
    args: Optional[Any] = None,
) -> SecuriFineConfig:
    """Get the effective configuration by merging all sources.

    Priority order (highest to lowest):
    1. Command-line arguments
    2. Environment variables
    3. Configuration file
    4. Default values

    Args:
        config_path: Optional path to configuration file.
        args: Optional parsed command-line arguments.

    Returns:
        SecuriFineConfig with effective values.
    """
    # Start with file config or defaults
    try:
        config = load_config(config_path)
    except ConfigError as e:
        logger.warning(f"Failed to load configuration: {e}, using defaults")
        config = SecuriFineConfig()

    # Apply environment variables
    env_values = load_from_environment()
    if env_values:
        config_dict = _config_to_dict(config)
        config_dict.update(env_values)
        config = _dict_to_config(config_dict)

    # Apply command-line arguments
    if args is not None:
        config = merge_config_with_args(config, args)

    return config


def validate_config(config: SecuriFineConfig) -> list:
    """Validate a configuration.

    Args:
        config: The configuration to validate.

    Returns:
        List of validation error messages. Empty if valid.
    """
    errors = []

    # Validate output format
    valid_formats = {"json", "md", "html"}
    if config.default_output_format not in valid_formats:
        errors.append(
            f"Invalid output format: {config.default_output_format}. "
            f"Valid formats: {', '.join(valid_formats)}"
        )

    # Validate log level
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if config.log_level.upper() not in valid_levels:
        errors.append(
            f"Invalid log level: {config.log_level}. "
            f"Valid levels: {', '.join(valid_levels)}"
        )

    # Validate numeric values
    if config.evaluation_timeout <= 0:
        errors.append("Evaluation timeout must be positive")

    if config.max_file_size <= 0:
        errors.append("Max file size must be positive")

    return errors


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _config_to_dict(config: SecuriFineConfig) -> Dict[str, Any]:
    """Convert a SecuriFineConfig to a dictionary.

    Args:
        config: The configuration to convert.

    Returns:
        Dictionary representation.
    """
    return {
        "model_url": config.model_url,
        "model_api_key": config.model_api_key,
        "model_name": config.model_name,
        "default_output_format": config.default_output_format,
        "registry_path": config.registry_path,
        "hook_configs": config.hook_configs,
        "evaluation_timeout": config.evaluation_timeout,
        "max_file_size": config.max_file_size,
        "max_entries": config.max_entries,
        "log_level": config.log_level,
        "max_retries": config.max_retries,
        "severe_regression_threshold": config.severe_regression_threshold,
        "significant_decrease_threshold": config.significant_decrease_threshold,
        "minor_decrease_threshold": config.minor_decrease_threshold,
    }


def _dict_to_config(data: Dict[str, Any]) -> SecuriFineConfig:
    """Convert a dictionary to a SecuriFineConfig.

    Args:
        data: Dictionary to convert.

    Returns:
        SecuriFineConfig object.
    """
    return SecuriFineConfig(
        model_url=data.get("model_url"),
        model_api_key=data.get("model_api_key"),
        model_name=data.get("model_name", "default"),
        default_output_format=data.get("default_output_format", "json"),
        registry_path=data.get("registry_path"),
        hook_configs=data.get("hook_configs", {}),
        evaluation_timeout=data.get("evaluation_timeout", 60),
        max_file_size=data.get("max_file_size", 1073741824),
        max_entries=data.get("max_entries", 1000000),
        log_level=data.get("log_level", "WARNING"),
        max_retries=data.get("max_retries", 3),
        severe_regression_threshold=data.get("severe_regression_threshold", 0.15),
        significant_decrease_threshold=data.get("significant_decrease_threshold", 0.05),
        minor_decrease_threshold=data.get("minor_decrease_threshold", 0.02),
    )
