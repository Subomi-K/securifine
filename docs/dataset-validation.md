# Dataset Validation Guide

This document explains how to validate training datasets with SecuriFine, including format requirements, validation checks, the registry system, and manifest specifications.

## Overview

Dataset validation is a critical step before fine-tuning language models on cybersecurity data. SecuriFine provides validation tools to detect potential issues including:

- Malformed or corrupted data files
- Dangerous content patterns that could compromise model safety
- Structural inconsistencies that may cause training issues
- Duplicate entries that could bias the model

Validating datasets before use helps ensure training data quality and reduces the risk of introducing safety regressions during fine-tuning.

## Supported Formats

SecuriFine supports three dataset formats commonly used in LLM fine-tuning workflows.

### JSONL (JSON Lines)

**Extensions:** `.jsonl`, `.json`, `.ndjson`

JSONL is the preferred format for fine-tuning datasets. Each line contains a valid JSON object.

#### Requirements

- UTF-8 encoding
- One valid JSON object per line
- Empty lines are skipped
- Maximum line length: 1,000,000 characters (configurable)

#### Example

```json
{"prompt": "What is SQL injection?", "response": "SQL injection is a code injection technique..."}
{"prompt": "Explain XSS attacks", "response": "Cross-site scripting (XSS) is a security vulnerability..."}
```

---

### CSV (Comma-Separated Values)

**Extensions:** `.csv`, `.tsv`

CSV format is supported for tabular datasets.

#### Requirements

- UTF-8 encoding
- Consistent column count across all rows
- Optional header row (auto-detected)
- Standard CSV escaping for special characters

#### Example

```csv
prompt,response
"What is SQL injection?","SQL injection is a code injection technique..."
"Explain XSS attacks","Cross-site scripting (XSS) is a security vulnerability..."
```

---

### Parquet

**Extensions:** `.parquet`, `.pq`

Parquet format is supported with limited validation due to stdlib-only constraints.

#### Requirements

- Valid Parquet file structure (PAR1 magic bytes at start and end)
- File must be readable

#### Limitations

- Entry count cannot be determined without external dependencies
- Content scanning is not performed
- Only basic file structure validation is available

---

## Format Auto-Detection

SecuriFine automatically detects file formats using:

1. **File extension** - Primary detection method
2. **Content inspection** - Fallback for unknown extensions

| Extension | Detected Format |
|-----------|-----------------|
| `.jsonl` | JSONL |
| `.json` | JSONL |
| `.ndjson` | JSONL |
| `.csv` | CSV |
| `.tsv` | CSV |
| `.parquet` | Parquet |
| `.pq` | Parquet |

For files without recognized extensions, SecuriFine inspects the first few bytes to determine the format.

---

## Validation Checks

### Format Validation

Verifies the file conforms to its detected format.

| Check | Description | Severity |
|-------|-------------|----------|
| File exists | File must exist at specified path | Critical |
| File readable | File must be a regular file | Critical |
| Valid syntax | Each entry must be valid for format | Critical |
| Encoding | File must be valid UTF-8 | Critical |

### Size Validation

Enforces size limits to prevent resource exhaustion.

| Check | Default Limit | Configurable | Severity |
|-------|---------------|--------------|----------|
| File size | 1 GB | Yes | Critical |
| Entry count | 1,000,000 | Yes | Critical |
| Line length | 1,000,000 chars | Yes | Medium |

### Content Validation

Scans for potentially dangerous patterns in the data.

#### Dangerous Patterns Detected

| Pattern Category | Description | Severity |
|------------------|-------------|----------|
| Script tags | `<script>` HTML tags | High |
| JavaScript URIs | `javascript:` protocol | High |
| Data URIs | `data:text/html` patterns | High |
| Shell injection | `rm -rf /`, pipe to bash | High |
| SQL injection | DROP TABLE, DELETE FROM, UNION SELECT | High |
| Suspicious URLs | IP-based URLs, suspicious TLDs | Medium |
| Excessive encoding | Many hex/unicode escapes | Medium |

#### Suspicious URL Patterns

The validator flags URLs matching these patterns:

- URLs with IP addresses: `http://192.168.1.1/`
- URLs with suspicious TLDs: `.ru`, `.cn`, `.tk`, `.ml`, `.ga`, `.cf`

#### Encoding Detection

Excessive use of encoding patterns may indicate obfuscation:

- Hex escapes: `\x41`
- Unicode escapes: `\u0041`
- HTML entities: `&#65;` or `&#x41;`

More than 50 encoding patterns in a single entry triggers a warning.

### Structure Validation

Checks for structural consistency.

| Check | Description | Severity |
|-------|-------------|----------|
| Column consistency (CSV) | All rows have same column count | Medium |
| Duplicates | Identical entries in sample | Low |

Duplicate detection uses sampling (default 1,000 entries) to identify repeated content without loading the entire file.

---

## Warning Severities

Validation findings are classified by severity.

### Critical

Issues that must be fixed before use.

- File does not exist or is not readable
- Invalid format (parsing errors)
- File exceeds size limits
- Entry count exceeds limits

**Action:** Do not use the dataset until resolved.

### High

Issues that strongly indicate problems.

- Dangerous content patterns detected
- Potential security risks in data

**Action:** Review flagged entries and remove or sanitize problematic content.

### Medium

Issues that should be reviewed.

- Suspicious URL patterns
- Excessive encoding (possible obfuscation)
- Inconsistent structure (CSV column count)
- Excessively long entries

**Action:** Manually inspect flagged entries to determine if they are legitimate.

### Low

Informational findings.

- Duplicate entries detected
- Parquet validation limitations

**Action:** Consider removing duplicates to improve training efficiency.

---

## Using the Validator

### Basic Validation

```bash
securifine validate --dataset training_data.jsonl -o validation.json
```

### Verbose Output

```bash
securifine -v validate --dataset training_data.jsonl -o validation.json
```

### Custom Limits

Configure limits in the configuration file:

```json
{
  "max_file_size": 2147483648,
  "evaluation_timeout": 120
}
```

---

## ValidationResult Structure

Validation produces a structured result:

```json
{
  "file_path": "/path/to/dataset.jsonl",
  "valid": true,
  "file_hash": "sha256:abc123...",
  "entry_count": 10000,
  "warnings": [
    {
      "severity": "low",
      "category": "structure",
      "message": "Found 5 duplicate entries in sample of 1000",
      "location": null
    }
  ],
  "errors": [],
  "metadata": {
    "format": "jsonl",
    "file_size": 15728640,
    "duplicate_count_in_sample": 5
  }
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | string | Path to the validated file |
| `valid` | boolean | True if no critical errors |
| `file_hash` | string | SHA-256 hash of the file |
| `entry_count` | integer | Number of entries found |
| `warnings` | array | Non-critical issues |
| `errors` | array | Critical issues |
| `metadata` | object | Additional file information |

---

## Registry System

The dataset registry provides a way to track and verify known-safe datasets.

### Purpose

- Maintain a catalog of validated datasets
- Verify dataset integrity via hash comparison
- Document safety review status
- Enable dataset discovery and search

### Registry Location

Default location: `~/.securifine/registry.json`

The registry is automatically created on first use.

### Registry Operations

#### List Registered Datasets

```bash
# Programmatic access
from securifine.datasets.registry import DatasetRegistry

registry = DatasetRegistry()
registry.load_registry()
for manifest in registry.list_datasets():
    print(f"{manifest.name}: {manifest.description}")
```

#### Verify Against Registry

```bash
securifine validate --dataset data.jsonl --check-registry cve-descriptions-2024
```

This compares the file's SHA-256 hash against the registered dataset's hash.

#### Search Datasets

```python
from securifine.datasets.registry import DatasetRegistry

registry = DatasetRegistry()
registry.load_registry()
results = registry.search_datasets("vulnerability")
```

---

## Dataset Manifest Format

Each registered dataset has a manifest with the following fields.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier (alphanumeric, hyphens, underscores) |
| `version` | string | Semantic version (e.g., "1.0.0") |
| `description` | string | Description of the dataset |
| `license` | string | License under which the dataset is distributed |
| `sha256_hash` | string | SHA-256 hash (64 hex characters) |
| `entry_count` | integer | Number of entries |
| `added_date` | string | ISO date when added (e.g., "2024-03-15") |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `source_url` | string | URL where dataset can be obtained |
| `categories` | array | Category tags (e.g., ["vulnerability", "threat_intel"]) |
| `safety_reviewed` | boolean | Whether the dataset has been safety reviewed |
| `safety_notes` | string | Notes about safety considerations |

### Example Manifest

```json
{
  "name": "cve-descriptions-2024",
  "version": "1.0.0",
  "description": "CVE vulnerability descriptions from NVD for 2024",
  "source_url": "https://nvd.nist.gov/",
  "license": "Public Domain",
  "sha256_hash": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234abcd",
  "entry_count": 25000,
  "categories": ["vulnerability", "cve"],
  "safety_reviewed": true,
  "safety_notes": "Contains vulnerability descriptions only, no exploit code",
  "added_date": "2024-03-15"
}
```

---

## Adding Datasets to Registry

### Step 1: Validate the Dataset

```bash
securifine validate --dataset my_dataset.jsonl -o validation.json
```

Ensure the dataset passes validation with no critical errors.

### Step 2: Create a Manifest

```python
from securifine.datasets.registry import DatasetManifest, DatasetRegistry
from securifine.utils.hashing import compute_file_hash

# Compute file hash
file_hash = compute_file_hash("my_dataset.jsonl")

# Create manifest
manifest = DatasetManifest(
    name="my-dataset",
    version="1.0.0",
    description="My custom cybersecurity dataset",
    source_url=None,
    license="MIT",
    sha256_hash=file_hash,
    entry_count=5000,
    categories=["custom", "security"],
    safety_reviewed=True,
    safety_notes="Manually reviewed for harmful content",
    added_date="2024-03-15"
)

# Add to registry
registry = DatasetRegistry()
registry.load_registry()
registry.add_dataset(manifest)
registry.save_registry()
```

### Step 3: Verify Registration

```python
from securifine.datasets.registry import DatasetRegistry

registry = DatasetRegistry()
registry.load_registry()

# Verify file against registry
is_valid = registry.verify_dataset("my-dataset", "my_dataset.jsonl")
print(f"Dataset verification: {'PASSED' if is_valid else 'FAILED'}")
```

---

## Example Workflows

### Validate New Dataset Before Training

```bash
# 1. Run validation
securifine validate --dataset new_training_data.jsonl -o validation.json

# 2. Check results
cat validation.json | python -c "import json,sys; d=json.load(sys.stdin); print('Valid' if d['valid'] else 'Invalid'); print(f'Warnings: {len(d[\"warnings\"])}'); print(f'Errors: {len(d[\"errors\"])}')"
```

### Verify Downloaded Dataset

```bash
# 1. Download dataset from known source

# 2. Validate format and content
securifine validate --dataset downloaded_data.jsonl -o validation.json

# 3. Verify against registry (if registered)
securifine validate --dataset downloaded_data.jsonl \
    --check-registry known-dataset-name \
    -o verification.json
```

### Batch Validation

```bash
# Validate multiple datasets
for file in datasets/*.jsonl; do
    securifine validate --dataset "$file" -o "results/$(basename $file .jsonl)_validation.json"
done

# Check for failures
grep -l '"valid": false' results/*.json
```

---

## Best Practices

### Before Fine-Tuning

1. **Always validate** datasets before use
2. **Review warnings** even if validation passes
3. **Register** datasets after validation for future verification
4. **Document** any manual safety reviews in the manifest

### Content Review

1. **Inspect flagged entries** to determine if they are false positives
2. **Remove or sanitize** genuinely problematic content
3. **Consider context** - some patterns may be legitimate in cybersecurity data

### Registry Maintenance

1. **Update hashes** when datasets change
2. **Version datasets** using semantic versioning
3. **Review periodically** as standards and requirements evolve

---

## Limitations

### Pattern Matching

- Dangerous pattern detection uses heuristics and may have false positives
- Sophisticated obfuscation may evade detection
- Content analysis is text-based only

### Format Support

- Parquet validation is limited without pandas
- Nested JSON structures are serialized for scanning
- Binary content is not analyzed

### Duplicate Detection

- Uses sampling for large files
- May miss duplicates outside the sample
- Based on exact matching only

### What This Does Not Validate

- Semantic correctness of the data
- Quality or accuracy of content
- Appropriateness for specific use cases
- Copyright or licensing compliance

