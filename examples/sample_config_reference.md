# SecuriFine Configuration Reference

This document describes all configuration options available in SecuriFine.

## Configuration File Location

The default configuration file is located at:
- `~/.securifine/config.json`

You can specify a custom configuration file using the `-c` or `--config` option:
```
securifine -c /path/to/config.json evaluate --model http://localhost:8000
```

## Configuration Options

### model_url

- **Type**: string or null
- **Default**: null
- **Description**: Default URL for the model API endpoint. Used when `--model` is not specified on the command line.
- **Example**: `"http://localhost:8000/v1"`

### model_api_key

- **Type**: string or null
- **Default**: null
- **Description**: API key for authenticating with the model endpoint. For security, consider using the `SECURIFINE_MODEL_API_KEY` environment variable instead of storing in the config file.
- **Example**: `"sk-your-api-key-here"`

### model_name

- **Type**: string
- **Default**: `"default"`
- **Description**: Model name to use in API requests. This is sent to the model endpoint to identify which model to use.
- **Example**: `"gpt-4"`, `"llama-3-70b"`

### default_output_format

- **Type**: string
- **Default**: `"json"`
- **Valid values**: `"json"`, `"md"`, `"html"`
- **Description**: Default format for output when `-f` is not specified on the command line.

### registry_path

- **Type**: string or null
- **Default**: null (uses `~/.securifine/registry.json`)
- **Description**: Path to the dataset registry file. If null, uses the default location.
- **Example**: `"/path/to/custom/registry.json"`

### hook_configs

- **Type**: object
- **Default**: `{}`
- **Description**: Dictionary of hook configurations keyed by tool name. Each hook configuration should contain `command`, `timeout_seconds`, `input_format`, and `output_format`.
- **Example**:
```json
{
  "hook_configs": {
    "my-tool": {
      "tool_name": "my-tool",
      "command": ["/usr/bin/my-tool", "--input", "{input_file}"],
      "timeout_seconds": 300,
      "input_format": "json",
      "output_format": "json"
    }
  }
}
```

### evaluation_timeout

- **Type**: integer
- **Default**: `60`
- **Description**: Timeout in seconds for individual model query requests during evaluation.
- **Valid range**: 1-3600

### max_file_size

- **Type**: integer
- **Default**: `1073741824` (1 GB)
- **Description**: Maximum file size in bytes for dataset validation. Files larger than this limit will fail validation.
- **Examples**:
  - 100 MB: `104857600`
  - 500 MB: `524288000`
  - 1 GB: `1073741824`

### log_level

- **Type**: string
- **Default**: `"WARNING"`
- **Valid values**: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`
- **Description**: Logging level for output. Lower levels show more detailed information.

### max_entries

- **Type**: integer
- **Default**: `1000000` (1 million)
- **Description**: Maximum number of entries allowed in dataset validation. Datasets with more entries will fail validation.

### max_retries

- **Type**: integer
- **Default**: `3`
- **Description**: Maximum number of retry attempts for failed API calls during model evaluation.
- **Valid range**: 1-10

### severe_regression_threshold

- **Type**: float
- **Default**: `0.15`
- **Description**: Score drop threshold for flagging a severe regression in comparison. A score drop greater than or equal to this value is considered severe.
- **Valid range**: 0.0-1.0

### significant_decrease_threshold

- **Type**: float
- **Default**: `0.05`
- **Description**: Aggregate score decrease threshold for "failed" assessment in comparison.
- **Valid range**: 0.0-1.0

### minor_decrease_threshold

- **Type**: float
- **Default**: `0.02`
- **Description**: Aggregate score decrease threshold for "warning" assessment in comparison.
- **Valid range**: 0.0-1.0

## Environment Variables

All configuration options can be overridden using environment variables with the `SECURIFINE_` prefix:

| Environment Variable | Config Option |
|---------------------|---------------|
| `SECURIFINE_MODEL_URL` | model_url |
| `SECURIFINE_MODEL_API_KEY` | model_api_key |
| `SECURIFINE_MODEL_NAME` | model_name |
| `SECURIFINE_DEFAULT_OUTPUT_FORMAT` | default_output_format |
| `SECURIFINE_REGISTRY_PATH` | registry_path |
| `SECURIFINE_EVALUATION_TIMEOUT` | evaluation_timeout |
| `SECURIFINE_MAX_FILE_SIZE` | max_file_size |
| `SECURIFINE_MAX_ENTRIES` | max_entries |
| `SECURIFINE_LOG_LEVEL` | log_level |
| `SECURIFINE_MAX_RETRIES` | max_retries |
| `SECURIFINE_SEVERE_REGRESSION_THRESHOLD` | severe_regression_threshold |
| `SECURIFINE_SIGNIFICANT_DECREASE_THRESHOLD` | significant_decrease_threshold |
| `SECURIFINE_MINOR_DECREASE_THRESHOLD` | minor_decrease_threshold |

## Configuration Priority

Configuration values are loaded in the following order (later sources override earlier ones):

1. Default values (built into SecuriFine)
2. Configuration file (`~/.securifine/config.json` or custom path)
3. Environment variables (`SECURIFINE_*`)
4. Command-line arguments

## Example Configuration

Here is a complete example configuration file:

```json
{
  "model_url": "http://localhost:8000/v1",
  "model_api_key": null,
  "model_name": "llama-3-70b",
  "default_output_format": "json",
  "registry_path": "~/.securifine/registry.json",
  "hook_configs": {
    "deepteam": {
      "tool_name": "deepteam",
      "command": ["deepteam", "evaluate", "--input", "{input_file}", "--output-format=json"],
      "timeout_seconds": 600,
      "input_format": "json",
      "output_format": "json"
    }
  },
  "evaluation_timeout": 120,
  "max_file_size": 536870912,
  "max_entries": 500000,
  "log_level": "INFO",
  "max_retries": 5,
  "severe_regression_threshold": 0.10,
  "significant_decrease_threshold": 0.03,
  "minor_decrease_threshold": 0.01
}
```

## Security Considerations

- Avoid storing API keys in the configuration file. Use environment variables instead.
- Ensure the configuration file has appropriate permissions (readable only by your user).
- The configuration directory (`~/.securifine/`) is created with default permissions.
