# Integration Guide

This document explains how to integrate SecuriFine with external red-team testing tools through the hook system, including configuration, security considerations, and troubleshooting.

## Overview

SecuriFine provides a hook system for integrating external security testing tools. Hooks enable you to:

- Run external red-team frameworks against your model
- Extend safety evaluation with specialized tools
- Integrate with existing security testing pipelines
- Combine results from multiple evaluation approaches

The hook system uses subprocess execution with standardized JSON input/output, ensuring safe and consistent integration.

---

## Hook System Architecture

### How Hooks Work

```
+------------------+     +------------------+     +------------------+
|   SecuriFine     | --> |   Input JSON     | --> |  External Tool   |
|   (hook caller)  |     |   (temp file)    |     |  (subprocess)    |
+------------------+     +------------------+     +------------------+
         ^                                                  |
         |                                                  v
         |               +------------------+     +------------------+
         +-------------- |   Output JSON    | <-- |  Tool Output     |
                         |   (parsed)       |     |  (stdout)        |
                         +------------------+     +------------------+
```

1. SecuriFine writes input data to a temporary JSON file
2. The external tool is executed as a subprocess
3. The tool reads input from the JSON file
4. The tool writes results to stdout
5. SecuriFine captures and parses the output
6. The temporary file is cleaned up

### Security Model

- **No shell execution** - Commands run directly without shell interpolation
- **Input validation** - Command components are checked for injection patterns
- **Timeout enforcement** - Processes are terminated if they exceed time limits
- **File cleanup** - Temporary files are removed after execution
- **Environment isolation** - Optional environment variable control

---

## Hook Configuration

### HookConfig Structure

```python
@dataclass
class HookConfig:
    tool_name: str              # Unique identifier
    command: List[str]          # Command and arguments
    timeout_seconds: int        # Maximum execution time (default: 300)
    input_format: str           # "json" or "args" (default: "json")
    output_format: str          # "json", "text", or "none" (default: "json")
    working_directory: str      # Optional working directory
    environment: Dict[str, str] # Optional environment overrides
```

### Configuration Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `tool_name` | Yes | - | Unique identifier for the hook |
| `command` | Yes | - | Command as list of strings |
| `timeout_seconds` | No | 300 | Max execution time (max: 3600) |
| `input_format` | No | "json" | How input is passed |
| `output_format` | No | "json" | Expected output format |
| `working_directory` | No | None | Directory to run in |
| `environment` | No | {} | Environment variable overrides |

### Command Placeholders

Use `{input_file}` as a placeholder for the JSON input file path:

```json
{
  "command": ["mytool", "--input", "{input_file}", "--output-format", "json"]
}
```

SecuriFine replaces `{input_file}` with the path to the temporary JSON file.

---

## DeepTeam Integration

DeepTeam is a red-teaming framework for testing LLM safety. SecuriFine provides built-in support for DeepTeam integration.

### Prerequisites

1. Install DeepTeam according to its documentation
2. Ensure the `deepteam` command is available in your PATH
3. Prepare any required configuration files

### Configuration

```json
{
  "tool_name": "deepteam",
  "command": ["deepteam", "evaluate", "--input", "{input_file}", "--output-format=json"],
  "timeout_seconds": 600,
  "input_format": "json",
  "output_format": "json"
}
```

### Programmatic Setup

```python
from securifine.integration.hooks import get_deepteam_hook_config, HookRunner

# Get default configuration
config = get_deepteam_hook_config(
    executable_path="/path/to/deepteam",
    config_path="/path/to/deepteam_config.yaml"
)

# Register with runner
runner = HookRunner()
runner.register_hook(config)
```

### Running DeepTeam

```bash
# Via CLI
securifine hook --tool deepteam --input prompts.json -o results.json

# With custom configuration
securifine hook --tool deepteam \
    --input prompts.json \
    --hook-config deepteam_config.json \
    -o results.json
```

### Expected Input Format

```json
{
  "prompts": [
    {
      "id": "test_001",
      "text": "Test prompt for evaluation",
      "category": "prompt_injection"
    }
  ],
  "model_config": {
    "endpoint": "http://localhost:8000/v1",
    "model_name": "target-model"
  }
}
```

### Expected Output Format

```json
{
  "results": [
    {
      "prompt_id": "test_001",
      "passed": true,
      "score": 0.95,
      "details": "Model appropriately refused the request"
    }
  ],
  "summary": {
    "total": 1,
    "passed": 1,
    "failed": 0
  }
}
```

---

## PyRIT Integration

PyRIT (Python Risk Identification Toolkit) is Microsoft's framework for AI red-teaming.

### Prerequisites

1. Install PyRIT: `pip install pyrit`
2. Create an evaluation script that accepts SecuriFine's input format
3. Ensure Python is available in your PATH

### Configuration

```json
{
  "tool_name": "pyrit",
  "command": ["python", "pyrit_evaluate.py", "--input", "{input_file}"],
  "timeout_seconds": 600,
  "input_format": "json",
  "output_format": "json"
}
```

### Programmatic Setup

```python
from securifine.integration.hooks import get_pyrit_hook_config, HookRunner

# Get default configuration
config = get_pyrit_hook_config(
    python_path="/path/to/python",
    script_path="/path/to/pyrit_evaluate.py"
)

# Register with runner
runner = HookRunner()
runner.register_hook(config)
```

### Example Wrapper Script

Create a `pyrit_evaluate.py` script that bridges SecuriFine and PyRIT:

```python
#!/usr/bin/env python3
"""PyRIT wrapper for SecuriFine integration."""

import argparse
import json
import sys

# Import PyRIT components as needed
# from pyrit import ...

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input JSON file")
    args = parser.parse_args()

    # Load input
    with open(args.input, "r") as f:
        input_data = json.load(f)

    # Run PyRIT evaluation
    results = run_pyrit_evaluation(input_data)

    # Output JSON results
    json.dump(results, sys.stdout, indent=2)

def run_pyrit_evaluation(input_data):
    # Implement PyRIT evaluation logic
    results = {
        "results": [],
        "summary": {"total": 0, "passed": 0, "failed": 0}
    }

    for prompt in input_data.get("prompts", []):
        # Run PyRIT tests
        result = {
            "prompt_id": prompt["id"],
            "passed": True,
            "score": 1.0,
            "details": "Evaluation complete"
        }
        results["results"].append(result)
        results["summary"]["total"] += 1
        results["summary"]["passed"] += 1 if result["passed"] else 0
        results["summary"]["failed"] += 0 if result["passed"] else 1

    return results

if __name__ == "__main__":
    main()
```

### Running PyRIT

```bash
securifine hook --tool pyrit --input prompts.json -o results.json
```

---

## Custom Tool Integration

Any tool that can read JSON input and produce structured output can be integrated with SecuriFine.

### Requirements

1. **Executable** - The tool must be executable from the command line
2. **JSON input** - The tool must accept input via a JSON file
3. **Structured output** - The tool should produce parseable output

### Creating a Hook Configuration

#### JSON Configuration File

Create a file like `my_tool_hook.json`:

```json
{
  "tool_name": "my_scanner",
  "command": ["my-scanner", "--config", "scanner.yml", "--input", "{input_file}"],
  "timeout_seconds": 300,
  "input_format": "json",
  "output_format": "json",
  "working_directory": "/opt/my-scanner",
  "environment": {
    "SCANNER_MODE": "strict",
    "LOG_LEVEL": "warn"
  }
}
```

#### Programmatic Configuration

```python
from securifine.integration.hooks import HookConfig, HookRunner

config = HookConfig(
    tool_name="my_scanner",
    command=["my-scanner", "--config", "scanner.yml", "--input", "{input_file}"],
    timeout_seconds=300,
    input_format="json",
    output_format="json",
    working_directory="/opt/my-scanner",
    environment={"SCANNER_MODE": "strict"}
)

runner = HookRunner()
runner.register_hook(config)

# Run the hook
result = runner.run_hook("my_scanner", {"prompts": [...]})
```

### Input Formats

#### JSON Input (Recommended)

Input data is written to a temporary JSON file. Use `{input_file}` placeholder.

```json
{
  "input_format": "json",
  "command": ["tool", "--input", "{input_file}"]
}
```

#### Args Input

Input data is converted to command-line arguments.

```json
{
  "input_format": "args",
  "command": ["tool"]
}
```

With input `{"model": "gpt-4", "timeout": 60}`, the command becomes:
```
tool --model gpt-4 --timeout 60
```

### Output Formats

#### JSON Output

Tool stdout is parsed as JSON and stored in `output_data`:

```json
{
  "output_format": "json"
}
```

#### Text Output

Tool stdout is captured as raw text:

```json
{
  "output_format": "text"
}
```

#### No Output

Output is not captured:

```json
{
  "output_format": "none"
}
```

---

## JSON Protocol Reference

### Standard Input Structure

SecuriFine provides input in this general format:

```json
{
  "version": "1.0",
  "request_id": "unique-request-id",
  "prompts": [
    {
      "id": "prompt_001",
      "category": "prompt_injection",
      "text": "The prompt text to test",
      "metadata": {}
    }
  ],
  "model_config": {
    "endpoint": "http://localhost:8000/v1",
    "model_name": "target-model",
    "api_key": null
  },
  "options": {}
}
```

### Standard Output Structure

Tools should return output in this format:

```json
{
  "version": "1.0",
  "request_id": "unique-request-id",
  "status": "success",
  "results": [
    {
      "prompt_id": "prompt_001",
      "passed": true,
      "score": 0.95,
      "response": "Model's response text",
      "details": "Explanation of the result",
      "failure_reasons": []
    }
  ],
  "summary": {
    "total": 1,
    "passed": 1,
    "failed": 0,
    "error": 0
  },
  "metadata": {
    "tool_version": "1.0.0",
    "execution_time_seconds": 5.2
  }
}
```

### Required Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success", "error", or "partial" |
| `results` | array | Per-prompt results |
| `results[].prompt_id` | string | Matches input prompt ID |
| `results[].passed` | boolean | Whether the test passed |

### Optional Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `results[].score` | number | Numeric score (0.0-1.0) |
| `results[].response` | string | Model's response |
| `results[].details` | string | Human-readable explanation |
| `results[].failure_reasons` | array | List of failure reasons |
| `summary` | object | Aggregate statistics |
| `metadata` | object | Tool-specific metadata |

### Error Reporting

On error, return:

```json
{
  "status": "error",
  "error": {
    "code": "TIMEOUT",
    "message": "Model query timed out after 60 seconds",
    "details": {}
  },
  "results": []
}
```

---

## Security Considerations

### Shell Injection Prevention

SecuriFine never uses `shell=True` for subprocess execution. All commands are executed directly.

**Safe:**
```python
subprocess.run(["tool", "--input", file_path], shell=False)
```

**Avoided:**
```python
# SecuriFine never does this
subprocess.run(f"tool --input {file_path}", shell=True)
```

### Command Validation

Command components are validated to reject dangerous patterns:

| Pattern | Blocked | Reason |
|---------|---------|--------|
| `;` | Yes | Command chaining |
| `&&` | Yes | Conditional execution |
| `\|\|` | Yes | Conditional execution |
| `\|` | Yes | Pipe operator |
| `>` | Yes | Output redirection |
| `<` | Yes | Input redirection |
| `` ` `` | Yes | Command substitution |
| `$(` | Yes | Command substitution |
| `${` | Yes | Variable expansion |
| `\n` | Yes | Newline injection |

### Timeout Enforcement

- Default timeout: 300 seconds (5 minutes)
- Maximum timeout: 3600 seconds (1 hour)
- Processes are terminated on timeout

### Working Directory Isolation

Use `working_directory` to run tools in isolated directories:

```json
{
  "working_directory": "/sandboxed/tool/directory"
}
```

### Environment Control

Override environment variables to limit tool capabilities:

```json
{
  "environment": {
    "PATH": "/usr/bin:/bin",
    "HOME": "/tmp/tool_home"
  }
}
```

Note: This adds to the existing environment. Use with caution.

### File Cleanup

Temporary input files are automatically deleted after hook execution, even on errors.

### User Responsibility

While SecuriFine implements security measures, users are responsible for:

- Vetting external tools before use
- Ensuring tools do not have vulnerabilities
- Running tools with appropriate system permissions
- Monitoring tool behavior

---

## Running Hooks via CLI

### Basic Usage

```bash
securifine hook --tool TOOL_NAME --input INPUT_FILE [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--tool NAME` | Name of the hook to run |
| `--input FILE` | Path to JSON input file |
| `--hook-config FILE` | Custom hook configuration file |
| `--timeout SECONDS` | Override timeout |
| `-o FILE` | Output file path |
| `-f FORMAT` | Output format (json) |

### Examples

```bash
# Run registered hook
securifine hook --tool deepteam --input prompts.json -o results.json

# Run with custom config
securifine hook --tool custom_scanner \
    --input data.json \
    --hook-config scanner_config.json \
    -o results.json

# Verbose output
securifine -v hook --tool pyrit --input prompts.json -o results.json
```

---

## HookResult Structure

Hook execution returns a structured result:

```python
@dataclass
class HookResult:
    tool_name: str           # Name of the executed tool
    exit_code: int           # Process exit code (-1 on error)
    stdout: str              # Standard output
    stderr: str              # Standard error
    success: bool            # True if exit_code == 0
    duration_seconds: float  # Execution time
    output_data: dict        # Parsed JSON output (if applicable)
```

### JSON Representation

```json
{
  "tool_name": "deepteam",
  "exit_code": 0,
  "stdout": "{\"results\": [...]}",
  "stderr": "",
  "success": true,
  "duration_seconds": 45.2,
  "output_data": {
    "results": [...]
  }
}
```

---

## Troubleshooting

### Common Issues

#### Command Not Found

**Error:** `Command not found: mytool`

**Causes:**
- Tool not installed
- Tool not in PATH
- Wrong executable path in config

**Solutions:**
1. Verify tool is installed: `which mytool`
2. Use absolute path in command: `["/usr/local/bin/mytool", ...]`
3. Check working_directory if tool expects specific location

#### Timeout Exceeded

**Error:** `Timeout after 300 seconds`

**Causes:**
- Tool takes longer than timeout
- Tool is hanging
- Network issues (for remote APIs)

**Solutions:**
1. Increase timeout: `"timeout_seconds": 600`
2. Check tool logs for issues
3. Test tool manually outside SecuriFine

#### JSON Parse Error

**Error:** `Failed to parse JSON output`

**Causes:**
- Tool produces non-JSON output
- Tool writes to stderr instead of stdout
- Mixed stdout content (logs + JSON)

**Solutions:**
1. Verify tool outputs valid JSON to stdout
2. Check output_format setting matches tool output
3. Configure tool to suppress non-JSON output

#### Permission Denied

**Error:** `OS error: [Errno 13] Permission denied`

**Causes:**
- Tool not executable
- Working directory not accessible
- Temp file location not writable

**Solutions:**
1. Make tool executable: `chmod +x mytool`
2. Check working_directory permissions
3. Verify `/tmp` or temp directory is writable

### Debugging Techniques

#### Enable Verbose Logging

```bash
securifine -vv hook --tool mytool --input data.json -o results.json
```

#### Test Tool Manually

```bash
# Create test input
echo '{"prompts": []}' > /tmp/test_input.json

# Run tool directly
mytool --input /tmp/test_input.json

# Check exit code
echo $?
```

#### Inspect Hook Configuration

```python
from securifine.integration.hooks import HookRunner

runner = HookRunner()
# ... register hooks ...

config = runner.get_hook_config("mytool")
print(f"Command: {config.command}")
print(f"Timeout: {config.timeout_seconds}")
print(f"Output format: {config.output_format}")
```

#### Check Input File Content

```python
import json
import tempfile

# Simulate what SecuriFine does
data = {"prompts": [...]}
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(data, f, indent=2)
    print(f"Input written to: {f.name}")
```

### Log Interpretation

SecuriFine logs hook events at different levels:

| Level | Message | Meaning |
|-------|---------|---------|
| INFO | `Registered hook: mytool` | Hook added to runner |
| INFO | `Executing hook: mytool` | Hook execution started |
| DEBUG | `Running command: mytool --input /tmp/...` | Actual command being run |
| INFO | `Hook mytool completed: exit_code=0, duration=5.2s` | Execution finished |
| WARNING | `Failed to parse JSON output` | Output parsing issue |
| ERROR | `Hook mytool timed out after 300s` | Timeout occurred |

---

## Best Practices

### Hook Development

1. **Test independently** before integrating with SecuriFine
2. **Use absolute paths** for reliability
3. **Handle errors gracefully** in your tool
4. **Produce valid JSON** for output_format="json"
5. **Log to stderr**, not stdout, for debugging

### Configuration

1. **Set reasonable timeouts** based on expected runtime
2. **Use working_directory** for tools with file dependencies
3. **Version hook configs** alongside your code
4. **Document custom hooks** for team members

### Security

1. **Audit external tools** before use
2. **Limit permissions** where possible
3. **Monitor resource usage** during execution
4. **Review output** before trusting results

### Integration

1. **Start simple** with minimal configuration
2. **Add complexity gradually** as needed
3. **Test edge cases** (empty input, large input, errors)
4. **Handle failures gracefully** in your workflow

