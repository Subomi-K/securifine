"""Dataset validation and registry modules."""

from securifine.datasets.validator import (
    ValidationWarning,
    ValidationResult,
    DatasetValidator,
    detect_format,
    estimate_entry_count,
    validation_result_to_dict,
    dict_to_validation_result,
)

from securifine.datasets.registry import (
    DatasetManifest,
    DatasetRegistry,
    RegistryError,
    get_default_registry_path,
    ensure_registry_exists,
    validate_manifest,
    manifest_to_dict,
    dict_to_manifest,
)

__all__ = [
    # validator
    "ValidationWarning",
    "ValidationResult",
    "DatasetValidator",
    "detect_format",
    "estimate_entry_count",
    "validation_result_to_dict",
    "dict_to_validation_result",
    # registry
    "DatasetManifest",
    "DatasetRegistry",
    "RegistryError",
    "get_default_registry_path",
    "ensure_registry_exists",
    "validate_manifest",
    "manifest_to_dict",
    "dict_to_manifest",
]
