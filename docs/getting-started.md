# Getting Started with SecuriFine

This guide walks you through real-world examples of using SecuriFine to evaluate and maintain safety alignment when fine-tuning language models on cybersecurity data.

## Table of Contents

1. [What SecuriFine Does](#what-securifine-does)
2. [Installation](#installation)
3. [Example 1: Basic Safety Evaluation](#example-1-basic-safety-evaluation)
4. [Example 2: Comparing Before and After Fine-Tuning](#example-2-comparing-before-and-after-fine-tuning)
5. [Example 3: Validating Training Data](#example-3-validating-training-data)
6. [Example 4: Generating Reports for Stakeholders](#example-4-generating-reports-for-stakeholders)
7. [Example 5: Integrating into CI/CD Pipelines](#example-5-integrating-into-cicd-pipelines)
8. [Example 6: Offline Evaluation](#example-6-offline-evaluation)
9. [Common Workflows](#common-workflows)
10. [Troubleshooting](#troubleshooting)

---

## What SecuriFine Does

SecuriFine helps you answer one critical question: **"Did fine-tuning my model make it less safe?"**

When you fine-tune a language model on cybersecurity data (CVE descriptions, threat intelligence, penetration testing guides), the model becomes more capable at security tasks. But this specialized training can also weaken the model's safety alignment - it may become more willing to help with malicious requests, more susceptible to jailbreaks, or more likely to leak sensitive information.

SecuriFine measures these safety characteristics before and after fine-tuning, then compares the results to identify any degradation.

---

## Installation

```bash
pip install securifine
```

Verify the installation:

```bash
securifine version
```

You should see:
```
SecuriFine version 0.1.0
Safety-Preserving Fine-Tuning Toolkit for Cybersecurity
```

---

## Example 1: Basic Safety Evaluation

**Scenario:** You have a language model running locally and want to check its current safety alignment.

### Step 1: Start Your Model

Your model needs to be accessible via an OpenAI-compatible API. Most serving frameworks (vLLM, text-generation-inference, llama.cpp) support this format.

For example, with vLLM:
```bash
python -m vllm.entrypoints.openai.api_server \
    --model your-model-name \
    --port 8000
```

### Step 2: Run the Evaluation

```bash
securifine evaluate --model http://localhost:8000/v1 --output baseline.json
```

**What happens:** SecuriFine sends 54 safety test prompts to your model and scores each response. These prompts test:
- Resistance to prompt injection attacks
- Appropriate refusal of harmful requests
- Protection against information leakage
- Consistency of safety behavior

### Step 3: Review the Results

The output file `baseline.json` contains detailed scores. For a quick summary:

```bash
cat baseline.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'Aggregate Score: {d[\"aggregate_score\"]:.3f}'); print(f'Overall Passed: {d[\"overall_passed\"]}')"
```

**Example output:**
```
Aggregate Score: 0.847
Overall Passed: True
```

A score of 0.847 means the model passed 84.7% of safety checks on average. A score above 0.79 is considered passing.

---

## Example 2: Comparing Before and After Fine-Tuning

**Scenario:** You've fine-tuned your model on CVE data and want to check if safety degraded.

### Step 1: Evaluate the Base Model (Before Fine-Tuning)

```bash
securifine evaluate --model http://localhost:8000/v1 --output baseline.json
```

### Step 2: Fine-Tune Your Model

Use your preferred fine-tuning framework (Axolotl, TRL, etc.) to train the model on your cybersecurity dataset.

### Step 3: Evaluate the Fine-Tuned Model

Start serving the fine-tuned model (on a different port if needed):

```bash
securifine evaluate --model http://localhost:8001/v1 --output finetuned.json
```

### Step 4: Compare the Results

```bash
securifine compare --baseline baseline.json --comparison finetuned.json --output comparison.json
```

**What happens:** SecuriFine calculates:
- Score changes for each safety category
- Which specific prompts regressed or improved
- Whether any "severe regressions" occurred
- An overall assessment: passed, warning, or failed

### Step 5: Understand the Comparison

```bash
cat comparison.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Overall Assessment: {d[\"overall_assessment\"].upper()}')
print(f'Aggregate Delta: {d[\"aggregate_delta\"]:+.3f}')
print(f'Regressions: {len(d[\"regressions\"])}')
print(f'Improvements: {len(d[\"improvements\"])}')
print(f'Severe Regressions: {len(d[\"severe_regressions\"])}')
"
```

**Example output:**
```
Overall Assessment: WARNING
Aggregate Delta: -0.032
Regressions: 8
Improvements: 3
Severe Regressions: 0
```

This tells you:
- The model is slightly less safe (aggregate score dropped by 0.032)
- 8 specific prompts got worse, 3 got better
- No critical safety failures occurred

---

## Example 3: Validating Training Data

**Scenario:** Before fine-tuning, you want to check your training data for potential safety issues.

### Step 1: Prepare Your Dataset

Your dataset should be in JSONL format (one JSON object per line):

```jsonl
{"instruction": "Explain what a buffer overflow is", "response": "A buffer overflow occurs when..."}
{"instruction": "How do SQL injections work?", "response": "SQL injection is a code injection..."}
```

### Step 2: Validate the Dataset

```bash
securifine validate --dataset training_data.jsonl --output validation.json
```

**What happens:** SecuriFine checks for:
- Proper JSONL format
- Dangerous content patterns (actual exploit code, malicious URLs)
- Suspicious encoding (base64-encoded commands)
- Duplicate entries
- File size and entry count limits

### Step 3: Review Validation Results

```bash
cat validation.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Valid: {d[\"valid\"]}')
print(f'Entry Count: {d[\"entry_count\"]}')
print(f'Warnings: {len(d[\"warnings\"])}')
print(f'Errors: {len(d[\"errors\"])}')
for w in d['warnings'][:5]:
    print(f'  - [{w[\"severity\"]}] {w[\"message\"]}')
"
```

**Example output:**
```
Valid: True
Entry Count: 15420
Warnings: 3
Errors: 0
  - [medium] Suspicious URL pattern detected at line 1542
  - [low] Possible encoded content detected at line 3891
  - [low] Possible encoded content detected at line 7234
```

These warnings don't make the dataset invalid, but you should review those specific lines.

---

## Example 4: Generating Reports for Stakeholders

**Scenario:** You need to share safety evaluation results with your team or management.

### Generate an HTML Report

```bash
securifine --format html report --input comparison.json --output safety_report.html
```

Open `safety_report.html` in a browser. The report includes:
- Executive summary with pass/warning/fail status
- Overall score comparison (before vs. after)
- Per-category breakdown table
- List of significant regressions
- Recommendations based on findings

### Generate a Markdown Report

For documentation or code reviews:

```bash
securifine --format md report --input comparison.json --output safety_report.md
```

This produces a Markdown file you can include in pull requests or documentation.

---

## Example 5: Integrating into CI/CD Pipelines

**Scenario:** You want to automatically check safety whenever you fine-tune a model.

### GitHub Actions Example

Create `.github/workflows/safety-check.yml`:

```yaml
name: Safety Evaluation

on:
  push:
    paths:
      - 'models/**'
      - 'training/**'

jobs:
  safety-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install SecuriFine
        run: pip install securifine

      - name: Start model server
        run: |
          # Start your model server in the background
          python -m vllm.entrypoints.openai.api_server \
            --model ./models/finetuned \
            --port 8000 &
          sleep 30  # Wait for server to start

      - name: Run safety evaluation
        run: |
          securifine evaluate \
            --model http://localhost:8000/v1 \
            --output evaluation.json

      - name: Compare with baseline
        run: |
          securifine compare \
            --baseline ./baselines/baseline.json \
            --comparison evaluation.json \
            --output comparison.json

      - name: Generate report
        run: |
          securifine --format md report \
            --input comparison.json \
            --output safety_report.md

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: safety-results
          path: |
            evaluation.json
            comparison.json
            safety_report.md

      - name: Check for failures
        run: |
          # The compare command returns exit code 1 if assessment is "failed"
          STATUS=$(cat comparison.json | python3 -c "import json,sys; print(json.load(sys.stdin)['overall_assessment'])")
          if [ "$STATUS" = "failed" ]; then
            echo "Safety check FAILED - see safety_report.md for details"
            exit 1
          fi
          echo "Safety check passed: $STATUS"
```

### Important Notes for CI/CD

1. **Exit codes:** SecuriFine returns exit code 1 if the comparison assessment is "failed". Use this to fail your pipeline when safety degrades significantly.

2. **Baseline storage:** Store your baseline evaluation (`baseline.json`) in version control so you can compare against it.

3. **Timeout considerations:** Evaluating 54 prompts can take time depending on your model. Budget 5-15 minutes for the evaluation step.

---

## Example 6: Offline Evaluation

**Scenario:** You can't run live model queries in your evaluation environment (air-gapped systems, cost constraints, etc.).

### Step 1: Collect Responses Separately

First, you need to collect model responses to all benchmark prompts. SecuriFine can help you get the prompt list:

```python
from securifine.safety.prompts import get_all_prompts
import json
import hashlib

prompts = get_all_prompts()
responses = {}

for prompt in prompts:
    # Hash the prompt text (this is how SecuriFine identifies prompts)
    prompt_hash = hashlib.sha256(prompt.prompt_text.encode()).hexdigest()

    # Get your model's response (replace with your actual model call)
    response = your_model.generate(prompt.prompt_text)

    responses[prompt_hash] = response

# Save to file
with open('collected_responses.json', 'w') as f:
    json.dump(responses, f, indent=2)
```

### Step 2: Run Offline Evaluation

```bash
securifine evaluate \
    --model offline \
    --responses-file collected_responses.json \
    --output evaluation.json
```

SecuriFine will score the pre-collected responses without making any network calls.

---

## Common Workflows

### Workflow 1: Pre-Training Safety Check

Before fine-tuning on new data:

```bash
# 1. Validate your training data
securifine validate --dataset new_training_data.jsonl --output validation.json

# 2. Review any warnings
cat validation.json | python3 -c "import json,sys; [print(w) for w in json.load(sys.stdin)['warnings']]"

# 3. If valid, proceed with fine-tuning
```

### Workflow 2: Post-Training Safety Check

After fine-tuning:

```bash
# 1. Evaluate the new model
securifine evaluate --model http://localhost:8000/v1 --output new_evaluation.json

# 2. Compare with baseline
securifine compare --baseline baseline.json --comparison new_evaluation.json --output comparison.json

# 3. Generate report
securifine --format html report --input comparison.json --output report.html

# 4. Check the assessment
cat comparison.json | python3 -c "import json,sys; print(json.load(sys.stdin)['overall_assessment'])"
```

### Workflow 3: Continuous Monitoring

For production models:

```bash
# Run weekly safety checks
securifine evaluate --model https://api.your-service.com/v1 \
    --model-key $API_KEY \
    --output "evaluation_$(date +%Y%m%d).json"

# Compare with previous week
securifine compare \
    --baseline "evaluation_$(date -v-7d +%Y%m%d).json" \
    --comparison "evaluation_$(date +%Y%m%d).json" \
    --output "weekly_comparison.json"
```

---

## Troubleshooting

### "Connection refused" when evaluating

**Problem:** SecuriFine can't connect to your model.

**Solution:**
1. Make sure your model server is running
2. Check the URL is correct (include `/v1` for OpenAI-compatible endpoints)
3. Try: `curl http://localhost:8000/v1/models` to verify the endpoint

### Evaluation is taking too long

**Problem:** Each of the 54 prompts is slow to respond.

**Solution:**
1. Use `--timeout 120` to allow more time per prompt
2. Consider using a smaller/faster model for testing
3. Use offline evaluation for repeated tests

### "Responses file does not contain response for prompt"

**Problem:** Your offline responses file is missing some prompts.

**Solution:**
1. Make sure you collected responses for ALL 54 prompts
2. Verify the prompt hashes match (use SHA-256 of the exact prompt text)
3. Re-collect responses if the benchmark prompts were updated

### Comparison shows unexpected regressions

**Problem:** The fine-tuned model seems worse, but you expected improvement.

**Solution:**
1. Check if the baseline was actually from the base model
2. Verify both evaluations used the same model configuration
3. Look at specific failing prompts in the comparison output
4. Consider if your training data may have introduced issues

### Validation produces false positives

**Problem:** Legitimate security content is flagged as dangerous.

**Solution:**
1. Review the specific warnings - they're informational, not blocking
2. The dataset can still be valid with warnings
3. If needed, you can ignore specific warning types in your workflow

---

## Next Steps

- Read the [CLI Reference](cli-reference.md) for all available options
- Understand the [Safety Evaluation](safety-evaluation.md) methodology
- Learn about [Dataset Validation](dataset-validation.md) checks
- Explore [External Tool Integration](integration-guide.md) for advanced testing
