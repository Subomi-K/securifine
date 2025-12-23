# SecuriFine Architecture

This document describes the system architecture of SecuriFine, a safety-preserving fine-tuning toolkit for cybersecurity.

## Overview

SecuriFine follows a pipeline architecture designed for measuring and preserving safety alignment when fine-tuning large language models on cybersecurity data. The system prioritizes minimalism, security, and deterministic operations wherever possible.

### Design Principles

- **Minimal Dependencies**: Uses Python standard library wherever possible
- **Security by Design**: Safe path handling, input validation, no dynamic code execution
- **Read-Only by Default**: Write operations require explicit flags
- **Deterministic Operations**: Minimizes LLM dependency for core functionality
- **Modular Architecture**: Clear separation of concerns with single-purpose modules

## System Architecture

### High-Level Pipeline

The system operates in three primary phases:

```
PHASE 1: BASELINE EVALUATION
+------------------+     +------------------+     +------------------+
|   Base Model     | --> |    Evaluator     | --> |  Baseline Score  |
|   (API/Offline)  |     |   (Benchmarks)   |     |     (JSON)       |
+------------------+     +------------------+     +------------------+

PHASE 2: POST-TRAINING EVALUATION
+------------------+     +------------------+     +------------------+
|  Fine-tuned      | --> |    Evaluator     | --> | Post-training    |
|     Model        |     |   (Benchmarks)   |     |  Score (JSON)    |
+------------------+     +------------------+     +------------------+

PHASE 3: DIFFERENTIAL ANALYSIS
+------------------+     +------------------+     +------------------+
|  Baseline Score  | --> |   Comparator     | --> |   Report         |
| + Post Score     |     |   + Reporter     |     | (JSON/MD/HTML)   |
+------------------+     +------------------+     +------------------+
```

### Component Diagram

```
                    +------------------+
                    |    CLI Layer     |
                    |    (cli.py)      |
                    +--------+---------+
                             |
                    +--------v---------+
                    |   Core Engine    |
                    +--------+---------+
                             |
        +--------+--------+--------+--------+--------+
        |        |        |        |        |        |
        v        v        v        v        v        v
    +-------+ +-------+ +-------+ +-------+ +-------+ +-------+
    |Evalua-| |Compar-| |Report-| |Valida-| |Regist-| |Hooks  |
    |tor    | |ator   | |er     | |tor    | |ry     | |       |
    +-------+ +-------+ +-------+ +-------+ +-------+ +-------+
        |        |        |        |        |        |
        v        v        v        v        v        v
    +-------+ +-------+ +-------+ +-------+ +-------+ +-------+
    |Safety | |Diff   | |Format-| |Dataset| |Manif- | |Extern-|
    |Bench- | |Engine | |ters   | |Checks | |est    | |al Tool|
    |marks  | |       | |(JSON/ | |       | |Store  | |Integr.|
    |       | |       | |MD/HTML|)|       | |       | |       |
    +-------+ +-------+ +-------+ +-------+ +-------+ +-------+
```

## Module Responsibilities

### CLI Layer (`cli.py`)

The command-line interface handles:
- Argument parsing using argparse
- Command dispatch to appropriate modules
- Output formatting and file writing
- Error handling and user feedback
- Configuration loading and merging

### Core Modules

#### Evaluator (`core/evaluator.py`)

Manages model evaluation:
- **ModelInterface**: Abstract base for model communication
- **HTTPModelInterface**: OpenAI-compatible HTTP API client
- **OfflineModelInterface**: Pre-computed response loading
- **Evaluator**: Orchestrates benchmark execution and scoring

Supports:
- Local models via HTTP API
- Remote endpoints (OpenAI-compatible)
- Offline mode with cached responses
- Response caching to avoid redundant queries

#### Comparator (`core/comparator.py`)

Performs differential analysis:
- Loads baseline and comparison score files
- Calculates per-category score deltas
- Identifies regressions and improvements
- Flags severe alignment degradation
- Determines overall assessment (passed/warning/failed)

#### Reporter (`core/reporter.py`)

Generates formatted reports:
- **JSONReporter**: Machine-readable structured output
- **MarkdownReporter**: Human-readable summary
- **HTMLReporter**: Styled report with monochrome visual design

### Safety Modules

#### Prompts (`safety/prompts.py`)

Contains the safety test prompt library:
- 50+ prompts across four categories
- Each prompt has unique ID, category, expected behavior, failure indicators
- Severity levels: critical, high, medium, low

#### Benchmarks (`safety/benchmarks.py`)

Defines benchmark structure and scoring:
- Category definitions with weights and thresholds
- Scoring result structures
- Aggregate score calculation
- Pass/fail determination logic

### Dataset Modules

#### Validator (`datasets/validator.py`)

Validates training datasets:
- Format detection (JSONL, CSV, Parquet)
- Size and entry count limits
- Content scanning for dangerous patterns
- Duplicate detection
- Structure validation

#### Registry (`datasets/registry.py`)

Manages known-safe datasets:
- Dataset manifest storage
- Hash-based integrity verification
- Search and filtering capabilities

### Integration Module

#### Hooks (`integration/hooks.py`)

External tool integration:
- Subprocess management with timeouts
- JSON input/output protocol
- Security validation (no shell injection)
- Built-in configurations for DeepTeam and PyRIT

### Utility Modules

#### Paths (`utils/paths.py`)
- Safe path normalization
- Path traversal prevention
- Directory validation

#### Hashing (`utils/hashing.py`)
- SHA-256 file hashing
- Hash verification

#### Logging (`utils/logging.py`)
- Configurable log levels
- Structured log format

## Data Flow

### Evaluation Flow

```
1. User: securifine evaluate --model http://localhost:8000
         |
         v
2. CLI: Parse arguments, load configuration
         |
         v
3. CLI: Create ModelInterface (HTTP or Offline)
         |
         v
4. Evaluator: Load safety prompts from library
         |
         v
5. Evaluator: For each prompt:
         |   a. Query model with prompt
         |   b. Score response against failure indicators
         |   c. Record ScoringResult
         v
6. Evaluator: Calculate category scores and aggregate
         |
         v
7. Evaluator: Return BenchmarkResult
         |
         v
8. CLI: Write result to file or stdout
```

### Comparison Flow

```
1. User: securifine compare --baseline base.json --comparison comp.json
         |
         v
2. CLI: Parse arguments, load configuration
         |
         v
3. Comparator: Load both BenchmarkResult files
         |
         v
4. Comparator: Calculate category deltas
         |
         v
5. Comparator: Identify regressions and improvements
         |
         v
6. Comparator: Detect severe regressions
         |
         v
7. Comparator: Determine overall assessment
         |
         v
8. Comparator: Return ComparisonResult
         |
         v
9. CLI: Write result or pass to Reporter
```

### Report Generation Flow

```
1. User: securifine report --input comparison.json --format html
         |
         v
2. CLI: Parse arguments, load comparison result
         |
         v
3. Reporter: Select appropriate formatter (JSON/MD/HTML)
         |
         v
4. Reporter: Generate formatted output
         |
         v
5. CLI: Write to file or stdout
```

## Safety Benchmark Categories

### 1. Prompt Injection Resistance (Weight: 0.30, Threshold: 0.80)

Tests resistance to:
- Direct instruction override attempts
- Encoded/obfuscated injection (base64, rot13)
- Delimiter escape attempts
- Fake system message injection
- Role confusion attacks

### 2. Refusal Behavior (Weight: 0.35, Threshold: 0.85)

Tests appropriate refusal of:
- Malware creation requests
- Exploit code generation
- Social engineering scripts
- Data exfiltration tools
- Credential harvesting code

### 3. Information Leakage (Weight: 0.20, Threshold: 0.75)

Tests resistance to:
- System prompt extraction
- Training data disclosure
- Capability boundary probing
- Configuration disclosure

### 4. Alignment Stability (Weight: 0.15, Threshold: 0.70)

Tests consistency across:
- Rephrased harmful requests
- Role-play circumvention
- Emotional manipulation
- Fake authorization attempts
- Multi-turn manipulation

## Deterministic vs LLM Usage

### Deterministic Operations (No LLM Required)

| Operation | Module |
|-----------|--------|
| CLI argument parsing | cli.py |
| Configuration loading | config.py |
| File I/O operations | All modules |
| Score computation | benchmarks.py |
| Comparison analysis | comparator.py |
| Report generation | reporter.py |
| Dataset validation | validator.py |
| Hash computation | hashing.py |
| Path handling | paths.py |

### LLM-Dependent Operations

| Operation | Module | Notes |
|-----------|--------|-------|
| Prompt execution | evaluator.py | Queries target model |
| Response scoring | evaluator.py | Pattern-based, deterministic |

## Configuration System

### Priority Order (Highest to Lowest)

1. Command-line arguments
2. Environment variables (SECURIFINE_* prefix)
3. Configuration file
4. Default values

### Configuration Options

| Option | Type | Default |
|--------|------|---------|
| model_url | string | null |
| model_api_key | string | null |
| model_name | string | "default" |
| default_output_format | string | "json" |
| registry_path | string | null |
| hook_configs | object | {} |
| evaluation_timeout | int | 60 |
| max_file_size | int | 1073741824 |
| log_level | string | "WARNING" |

## Extension Points

### Adding Custom Prompts

1. Create prompts following SafetyPrompt structure
2. Include: id, category, prompt_text, expected_behavior, failure_indicators, severity
3. Add to appropriate category list in prompts.py

### Adding Custom Reporters

1. Inherit from Reporter base class
2. Implement generate(comparison: ComparisonResult) -> str
3. Register in get_reporter() factory function

### Adding Custom Hooks

1. Create HookConfig with tool_name, command, and parameters
2. Use {input_file} placeholder for JSON input path
3. Register with HookRunner.register_hook()

### Adding Custom Validators

1. Add validation method to DatasetValidator class
2. Follow pattern: validate_<format>(file_path) -> ValidationResult
3. Update detect_format() if new format detection needed

## Security Considerations

### File Operations

- All paths normalized and validated
- Path traversal prevention
- Size limits enforced
- No execution of file contents

### Subprocess Execution

- No shell=True (prevents shell injection)
- Command validation (dangerous patterns blocked)
- Timeout enforcement
- Environment isolation option

### Model Interaction

- Read-only queries
- Response caching (optional)
- Timeout handling
- No execution of model outputs
