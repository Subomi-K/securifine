# SecuriFine CLI Reference

Complete command-line reference for SecuriFine.

## Installation

```bash
pip install securifine
```

Or from source:

```bash
git clone https://github.com/clay-good/securifine.git
cd securifine
pip install -e .
```

## General Usage

```
securifine [global-options] <command> [command-options]
```

## Global Options

These options can be used with any command and must be placed before the command name.

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--verbose` | `-v` | Increase output verbosity. Can be repeated (-vv for debug). | WARNING level |
| `--quiet` | `-q` | Suppress non-essential output. | False |
| `--output FILE` | `-o FILE` | Write output to file instead of stdout. | stdout |
| `--format FORMAT` | `-f FORMAT` | Output format: json, md, html. | json |
| `--config FILE` | `-c FILE` | Path to configuration file. | ~/.securifine/config.json |

## Commands

### evaluate

Run safety evaluation against a model.

```
securifine evaluate --model MODEL [options]
```

#### Options

| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--model URL` | Yes | Model API URL or "offline" for cached responses. | - |
| `--model-key KEY` | No | API key for model authentication. | None |
| `--model-name NAME` | No | Model name to send in API requests. | "default" |
| `--responses-file FILE` | No* | Path to cached responses file (required if --model is "offline"). | None |
| `--timeout SECONDS` | No | Timeout for model queries in seconds. | 60 |

#### Examples

Evaluate a local model:
```bash
securifine evaluate --model http://localhost:8000/v1 -o baseline.json
```

Evaluate with API key:
```bash
securifine evaluate --model https://api.openai.com/v1 \
    --model-key sk-your-key \
    --model-name gpt-4 \
    -o baseline.json
```

Evaluate using offline responses:
```bash
securifine evaluate --model offline \
    --responses-file responses.json \
    -o evaluation.json
```

Verbose evaluation with custom timeout:
```bash
securifine -v evaluate --model http://localhost:8000 \
    --timeout 120 \
    -o baseline.json
```

---

### compare

Compare two evaluation results to identify safety regressions.

```
securifine compare --baseline FILE --comparison FILE [options]
```

#### Options

| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--baseline FILE` | Yes | Path to baseline evaluation result (before fine-tuning). | - |
| `--comparison FILE` | Yes | Path to comparison evaluation result (after fine-tuning). | - |

#### Examples

Compare baseline and fine-tuned results:
```bash
securifine compare --baseline baseline.json --comparison finetuned.json \
    -o comparison.json
```

Compare and output as Markdown:
```bash
securifine -f md compare --baseline baseline.json --comparison finetuned.json \
    -o comparison.md
```

---

### report

Generate a formatted report from a comparison result.

```
securifine report --input FILE [options]
```

#### Options

| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--input FILE` | Yes | Path to comparison result file. | - |

#### Examples

Generate JSON report:
```bash
securifine report --input comparison.json -o report.json
```

Generate Markdown report:
```bash
securifine -f md report --input comparison.json -o report.md
```

Generate HTML report:
```bash
securifine -f html report --input comparison.json -o report.html
```

---

### validate

Validate a training dataset for safety concerns.

```
securifine validate --dataset FILE [options]
```

#### Options

| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--dataset FILE` | Yes | Path to the dataset file to validate. | - |
| `--registry FILE` | No | Path to custom registry file. | ~/.securifine/registry.json |
| `--check-registry NAME` | No | Verify dataset against named registry entry. | None |

#### Examples

Validate a JSONL dataset:
```bash
securifine validate --dataset training_data.jsonl -o validation.json
```

Validate and check against registry:
```bash
securifine validate --dataset cve_data.jsonl \
    --check-registry cve-descriptions-2024 \
    -o validation.json
```

Verbose validation with custom registry:
```bash
securifine -v validate --dataset data.jsonl \
    --registry my_registry.json \
    -o validation.json
```

---

### hook

Run an external red-team testing tool.

```
securifine hook --tool NAME --input FILE [options]
```

#### Options

| Option | Required | Description | Default |
|--------|----------|-------------|---------|
| `--tool NAME` | Yes | Name of the hook to run (e.g., "deepteam", "pyrit"). | - |
| `--input FILE` | Yes | Path to JSON input file for the tool. | - |
| `--hook-config FILE` | No | Path to custom hook configuration file. | None |
| `--timeout SECONDS` | No | Timeout for hook execution in seconds. | 300 |

#### Examples

Run DeepTeam hook:
```bash
securifine hook --tool deepteam --input prompts.json -o results.json
```

Run with custom configuration:
```bash
securifine hook --tool custom_scanner \
    --input data.json \
    --hook-config hooks.json \
    --timeout 600 \
    -o results.json
```

---

### version

Display version information.

```
securifine version
```

#### Example

```bash
securifine version
```

Output:
```
SecuriFine version 0.1.0
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Runtime error (file not found, invalid data, etc.) |
| 2 | Usage error (invalid arguments, missing required options) |

---

## Environment Variables

All configuration options can be set via environment variables with the `SECURIFINE_` prefix.

| Environment Variable | Config Option | Description |
|---------------------|---------------|-------------|
| `SECURIFINE_MODEL_URL` | model_url | Default model API URL |
| `SECURIFINE_MODEL_API_KEY` | model_api_key | API key for model authentication |
| `SECURIFINE_MODEL_NAME` | model_name | Model name for API requests |
| `SECURIFINE_DEFAULT_OUTPUT_FORMAT` | default_output_format | Default output format |
| `SECURIFINE_REGISTRY_PATH` | registry_path | Path to dataset registry |
| `SECURIFINE_EVALUATION_TIMEOUT` | evaluation_timeout | Model query timeout |
| `SECURIFINE_MAX_FILE_SIZE` | max_file_size | Maximum dataset file size |
| `SECURIFINE_LOG_LEVEL` | log_level | Logging level |

Example:
```bash
export SECURIFINE_MODEL_URL="http://localhost:8000/v1"
export SECURIFINE_LOG_LEVEL="DEBUG"
securifine evaluate -o baseline.json
```

---

## Configuration File

SecuriFine uses JSON configuration files. The default location is `~/.securifine/config.json`.

### Configuration Priority

1. Command-line arguments (highest priority)
2. Environment variables
3. Configuration file
4. Default values (lowest priority)

### Configuration Format

```json
{
  "model_url": "http://localhost:8000/v1",
  "model_api_key": null,
  "model_name": "default",
  "default_output_format": "json",
  "registry_path": "~/.securifine/registry.json",
  "hook_configs": {
    "deepteam": {
      "tool_name": "deepteam",
      "command": ["deepteam", "evaluate", "--input", "{input_file}"],
      "timeout_seconds": 600,
      "input_format": "json",
      "output_format": "json"
    }
  },
  "evaluation_timeout": 60,
  "max_file_size": 1073741824,
  "log_level": "WARNING"
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| model_url | string/null | null | Default model API endpoint |
| model_api_key | string/null | null | API key for model authentication |
| model_name | string | "default" | Model name for API requests |
| default_output_format | string | "json" | Output format (json, md, html) |
| registry_path | string/null | null | Path to dataset registry file |
| hook_configs | object | {} | Hook configurations by tool name |
| evaluation_timeout | int | 60 | Timeout for model queries (seconds) |
| max_file_size | int | 1073741824 | Max dataset file size (bytes, default 1GB) |
| log_level | string | "WARNING" | Log level (DEBUG, INFO, WARNING, ERROR) |

---

## Common Workflows

### Complete Evaluation Workflow

```bash
# 1. Evaluate base model
securifine evaluate --model http://localhost:8000/v1 \
    -o baseline.json

# 2. Fine-tune your model (using your preferred tool)

# 3. Evaluate fine-tuned model
securifine evaluate --model http://localhost:8001/v1 \
    -o finetuned.json

# 4. Compare results
securifine compare --baseline baseline.json --comparison finetuned.json \
    -o comparison.json

# 5. Generate report
securifine -f html report --input comparison.json -o report.html
```

### Dataset Validation Workflow

```bash
# Validate before training
securifine validate --dataset training_data.jsonl -o validation.json

# Check the results
cat validation.json | jq '.valid'
```

### Offline Evaluation Workflow

```bash
# Collect responses manually and save to file

# Evaluate using cached responses
securifine evaluate --model offline \
    --responses-file collected_responses.json \
    -o evaluation.json
```
