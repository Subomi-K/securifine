"""Dataset registry module for SecuriFine.

This module provides a registry system for managing known-safe datasets
with manifests containing metadata and integrity verification.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from securifine.utils.hashing import verify_file_hash
from securifine.utils.logging import get_logger


logger = get_logger("registry")


# Default registry location
DEFAULT_REGISTRY_DIR = ".securifine"
DEFAULT_REGISTRY_FILE = "registry.json"


@dataclass
class DatasetManifest:
    """Manifest for a registered dataset.

    Attributes:
        name: Unique name identifier for the dataset.
        version: Version string (semver format recommended).
        description: Description of the dataset contents.
        source_url: Optional URL where the dataset can be obtained.
        license: License under which the dataset is distributed.
        sha256_hash: SHA-256 hash of the dataset file.
        entry_count: Number of entries in the dataset.
        categories: List of category tags for the dataset.
        safety_reviewed: Whether the dataset has been reviewed for safety.
        safety_notes: Optional notes about safety considerations.
        added_date: ISO format date string when added to registry.
    """

    name: str
    version: str
    description: str
    source_url: Optional[str]
    license: str
    sha256_hash: str
    entry_count: int
    categories: List[str] = field(default_factory=list)
    safety_reviewed: bool = False
    safety_notes: Optional[str] = None
    added_date: str = ""


class RegistryError(Exception):
    """Raised when registry operations fail."""

    pass


class DatasetRegistry:
    """Manages a registry of known datasets with manifests.

    The registry stores dataset manifests in a JSON file and provides
    methods for adding, removing, searching, and verifying datasets.
    """

    def __init__(self, registry_path: Optional[Union[str, Path]] = None) -> None:
        """Initialize the dataset registry.

        Args:
            registry_path: Path to the registry JSON file.
                If None, uses the default path.
        """
        if registry_path is None:
            self._registry_path = get_default_registry_path()
        else:
            self._registry_path = Path(registry_path)

        self._datasets: Dict[str, DatasetManifest] = {}
        self._loaded = False

    @property
    def registry_path(self) -> Path:
        """Get the registry file path."""
        return self._registry_path

    def load_registry(self, path: Optional[Union[str, Path]] = None) -> None:
        """Load the registry from a JSON file.

        Args:
            path: Path to load from. If None, uses the configured path.

        Raises:
            RegistryError: If the file cannot be loaded or parsed.
        """
        load_path = Path(path) if path else self._registry_path
        logger.debug(f"Loading registry from {load_path}")

        if not load_path.exists():
            logger.info(f"Registry file not found, starting with empty registry")
            self._datasets = {}
            self._loaded = True
            return

        try:
            with load_path.open("r", encoding="utf-8") as f:
                content = f.read().strip()

            # Handle empty files
            if not content:
                logger.info(f"Registry file is empty, starting with empty registry")
                self._datasets = {}
                self._loaded = True
                return

            data = json.loads(content)

            self._datasets = {}
            datasets_data = data.get("datasets", {})

            for name, manifest_data in datasets_data.items():
                try:
                    manifest = _dict_to_manifest(manifest_data)
                    self._datasets[name] = manifest
                except (KeyError, TypeError) as e:
                    logger.warning(f"Skipping invalid manifest '{name}': {e}")

            self._loaded = True
            logger.info(f"Loaded {len(self._datasets)} datasets from registry")

        except json.JSONDecodeError as e:
            raise RegistryError(f"Invalid JSON in registry file: {e}")
        except IOError as e:
            raise RegistryError(f"Error reading registry file: {e}")

    def save_registry(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the registry to a JSON file.

        Args:
            path: Path to save to. If None, uses the configured path.

        Raises:
            RegistryError: If the file cannot be written.
        """
        save_path = Path(path) if path else self._registry_path
        logger.debug(f"Saving registry to {save_path}")

        # Ensure parent directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "datasets": {
                name: _manifest_to_dict(manifest)
                for name, manifest in self._datasets.items()
            },
        }

        try:
            with save_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self._datasets)} datasets to registry")

        except IOError as e:
            raise RegistryError(f"Error writing registry file: {e}")

    def _ensure_loaded(self) -> None:
        """Ensure the registry is loaded."""
        if not self._loaded:
            self.load_registry()

    def add_dataset(self, manifest: DatasetManifest) -> None:
        """Add a dataset to the registry.

        Args:
            manifest: The dataset manifest to add.

        Raises:
            RegistryError: If validation fails or dataset already exists.
        """
        self._ensure_loaded()

        # Validate manifest
        errors = validate_manifest(manifest)
        if errors:
            raise RegistryError(f"Invalid manifest: {'; '.join(errors)}")

        if manifest.name in self._datasets:
            raise RegistryError(
                f"Dataset '{manifest.name}' already exists. "
                "Remove it first or use a different name."
            )

        self._datasets[manifest.name] = manifest
        logger.info(f"Added dataset '{manifest.name}' to registry")

    def remove_dataset(self, name: str) -> None:
        """Remove a dataset from the registry.

        Args:
            name: Name of the dataset to remove.

        Raises:
            RegistryError: If the dataset does not exist.
        """
        self._ensure_loaded()

        if name not in self._datasets:
            raise RegistryError(f"Dataset '{name}' not found in registry")

        del self._datasets[name]
        logger.info(f"Removed dataset '{name}' from registry")

    def get_dataset(self, name: str) -> Optional[DatasetManifest]:
        """Get a dataset manifest by name.

        Args:
            name: Name of the dataset.

        Returns:
            The DatasetManifest if found, None otherwise.
        """
        self._ensure_loaded()
        return self._datasets.get(name)

    def list_datasets(self) -> List[DatasetManifest]:
        """List all datasets in the registry.

        Returns:
            List of all DatasetManifest objects.
        """
        self._ensure_loaded()
        return list(self._datasets.values())

    def verify_dataset(
        self, name: str, file_path: Union[str, Path]
    ) -> bool:
        """Verify a file against a registered dataset's hash.

        Args:
            name: Name of the dataset in the registry.
            file_path: Path to the file to verify.

        Returns:
            True if the file hash matches the manifest hash.

        Raises:
            RegistryError: If the dataset is not in the registry.
            FileNotFoundError: If the file does not exist.
        """
        self._ensure_loaded()

        manifest = self._datasets.get(name)
        if manifest is None:
            raise RegistryError(f"Dataset '{name}' not found in registry")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        result = verify_file_hash(file_path, manifest.sha256_hash)
        logger.debug(f"Verification of '{name}' against {path}: {result}")

        return result

    def search_datasets(self, query: str) -> List[DatasetManifest]:
        """Search for datasets matching a query.

        Performs simple text search across name, description, and categories.

        Args:
            query: Search query string.

        Returns:
            List of matching DatasetManifest objects.
        """
        self._ensure_loaded()

        if not query:
            return self.list_datasets()

        query_lower = query.lower()
        results = []

        for manifest in self._datasets.values():
            # Search in name
            if query_lower in manifest.name.lower():
                results.append(manifest)
                continue

            # Search in description
            if query_lower in manifest.description.lower():
                results.append(manifest)
                continue

            # Search in categories
            if any(query_lower in cat.lower() for cat in manifest.categories):
                results.append(manifest)
                continue

        return results

    def update_dataset(self, manifest: DatasetManifest) -> None:
        """Update an existing dataset in the registry.

        Args:
            manifest: The updated dataset manifest.

        Raises:
            RegistryError: If validation fails or dataset does not exist.
        """
        self._ensure_loaded()

        # Validate manifest
        errors = validate_manifest(manifest)
        if errors:
            raise RegistryError(f"Invalid manifest: {'; '.join(errors)}")

        if manifest.name not in self._datasets:
            raise RegistryError(
                f"Dataset '{manifest.name}' not found. Use add_dataset for new entries."
            )

        self._datasets[manifest.name] = manifest
        logger.info(f"Updated dataset '{manifest.name}' in registry")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_default_registry_path() -> Path:
    """Get the default registry file path.

    Uses ~/.securifine/registry.json on Unix-like systems.

    Returns:
        Path to the default registry file.
    """
    home = Path.home()
    return home / DEFAULT_REGISTRY_DIR / DEFAULT_REGISTRY_FILE


def ensure_registry_exists() -> Path:
    """Ensure the default registry directory and file exist.

    Creates an empty registry file if it doesn't exist.

    Returns:
        Path to the registry file.
    """
    registry_path = get_default_registry_path()
    registry_dir = registry_path.parent

    if not registry_dir.exists():
        registry_dir.mkdir(parents=True)
        logger.debug(f"Created registry directory: {registry_dir}")

    if not registry_path.exists():
        # Create empty registry
        data = {"version": "1.0", "datasets": {}}
        with registry_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Created empty registry file: {registry_path}")

    return registry_path


def validate_manifest(manifest: DatasetManifest) -> List[str]:
    """Validate a dataset manifest.

    Args:
        manifest: The manifest to validate.

    Returns:
        List of validation error messages. Empty list if valid.
    """
    errors = []

    # Required fields
    if not manifest.name:
        errors.append("Name is required")
    elif not re.match(r"^[a-zA-Z0-9_-]+$", manifest.name):
        errors.append(
            "Name must contain only alphanumeric characters, underscores, and hyphens"
        )

    if not manifest.version:
        errors.append("Version is required")
    elif not _is_valid_semver(manifest.version):
        errors.append(
            "Version should follow semver format (e.g., 1.0.0, 2.1.0-beta)"
        )

    if not manifest.description:
        errors.append("Description is required")

    if not manifest.license:
        errors.append("License is required")

    if not manifest.sha256_hash:
        errors.append("SHA-256 hash is required")
    elif not _is_valid_sha256(manifest.sha256_hash):
        errors.append("SHA-256 hash must be a 64-character hexadecimal string")

    if manifest.entry_count < 0:
        errors.append("Entry count must be non-negative")

    if not manifest.added_date:
        errors.append("Added date is required")

    return errors


def _is_valid_semver(version: str) -> bool:
    """Check if a version string follows semver pattern.

    This is a simple check, not strict semver validation.

    Args:
        version: Version string to check.

    Returns:
        True if the version looks like semver.
    """
    # Simple pattern: major.minor.patch with optional prerelease
    pattern = r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?(\+[a-zA-Z0-9.]+)?$"
    return bool(re.match(pattern, version))


def _is_valid_sha256(hash_str: str) -> bool:
    """Check if a string is a valid SHA-256 hash.

    Args:
        hash_str: Hash string to check.

    Returns:
        True if valid SHA-256 format.
    """
    return bool(re.match(r"^[a-fA-F0-9]{64}$", hash_str))


def _manifest_to_dict(manifest: DatasetManifest) -> Dict[str, Any]:
    """Convert a DatasetManifest to a dictionary.

    Args:
        manifest: The manifest to convert.

    Returns:
        Dictionary representation.
    """
    return {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "source_url": manifest.source_url,
        "license": manifest.license,
        "sha256_hash": manifest.sha256_hash,
        "entry_count": manifest.entry_count,
        "categories": manifest.categories,
        "safety_reviewed": manifest.safety_reviewed,
        "safety_notes": manifest.safety_notes,
        "added_date": manifest.added_date,
    }


def _dict_to_manifest(data: Dict[str, Any]) -> DatasetManifest:
    """Convert a dictionary to a DatasetManifest.

    Args:
        data: Dictionary to convert.

    Returns:
        DatasetManifest object.

    Raises:
        KeyError: If required fields are missing.
    """
    return DatasetManifest(
        name=data["name"],
        version=data["version"],
        description=data["description"],
        source_url=data.get("source_url"),
        license=data["license"],
        sha256_hash=data["sha256_hash"],
        entry_count=data["entry_count"],
        categories=data.get("categories", []),
        safety_reviewed=data.get("safety_reviewed", False),
        safety_notes=data.get("safety_notes"),
        added_date=data.get("added_date", ""),
    )


def manifest_to_dict(manifest: DatasetManifest) -> Dict[str, Any]:
    """Public function to convert a DatasetManifest to a dictionary.

    Args:
        manifest: The manifest to convert.

    Returns:
        Dictionary representation.
    """
    return _manifest_to_dict(manifest)


def dict_to_manifest(data: Dict[str, Any]) -> DatasetManifest:
    """Public function to convert a dictionary to a DatasetManifest.

    Args:
        data: Dictionary to convert.

    Returns:
        DatasetManifest object.
    """
    return _dict_to_manifest(data)
