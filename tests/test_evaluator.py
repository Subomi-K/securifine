"""Tests for the SecuriFine evaluator module.

This module contains unit tests for ModelInterface implementations,
the Evaluator class, and scoring logic.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from securifine.core.evaluator import (
    ModelInterface,
    HTTPModelInterface,
    OfflineModelInterface,
    Evaluator,
    ModelQueryError,
)
from securifine.safety.prompts import SafetyPrompt
from securifine.safety.benchmarks import ScoringResult, BenchmarkResult
from securifine.utils.hashing import compute_string_hash


class TestModelInterface(unittest.TestCase):
    """Tests for the ModelInterface abstract base class."""

    def test_model_interface_is_abstract(self) -> None:
        """Test that ModelInterface cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            ModelInterface()


class TestOfflineModelInterface(unittest.TestCase):
    """Tests for the OfflineModelInterface class."""

    def test_init_with_responses_dict(self) -> None:
        """Test initialization with responses dictionary."""
        responses = {"hash1": "response1", "hash2": "response2"}
        model = OfflineModelInterface(responses=responses)
        self.assertIsNotNone(model)

    def test_init_requires_responses_or_file(self) -> None:
        """Test that initialization requires either responses or file."""
        with self.assertRaises(ValueError) as ctx:
            OfflineModelInterface()
        self.assertIn("responses", str(ctx.exception))

    def test_init_with_responses_file(self) -> None:
        """Test initialization with responses file."""
        responses = {"hash1": "response1", "hash2": "response2"}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(responses, f)
            file_path = f.name

        try:
            model = OfflineModelInterface(responses_file=file_path)
            self.assertIsNotNone(model)
        finally:
            Path(file_path).unlink()

    def test_init_with_nested_responses_file(self) -> None:
        """Test initialization with nested responses format."""
        data = {"responses": {"hash1": "response1", "hash2": "response2"}}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            file_path = f.name

        try:
            model = OfflineModelInterface(responses_file=file_path)
            self.assertIsNotNone(model)
        finally:
            Path(file_path).unlink()

    def test_query_returns_cached_response(self) -> None:
        """Test that query returns the cached response for a prompt."""
        prompt = "Test prompt"
        prompt_hash = compute_string_hash(prompt)
        expected_response = "Test response"

        responses = {prompt_hash: expected_response}
        model = OfflineModelInterface(responses=responses)

        result = model.query(prompt)
        self.assertEqual(result, expected_response)

    def test_query_raises_for_unknown_prompt(self) -> None:
        """Test that query raises error for unknown prompt."""
        responses = {"known_hash": "response"}
        model = OfflineModelInterface(responses=responses)

        with self.assertRaises(ModelQueryError) as ctx:
            model.query("Unknown prompt")
        self.assertIn("No cached response", str(ctx.exception))

    def test_get_prompt_hash(self) -> None:
        """Test the utility method to get prompt hash."""
        model = OfflineModelInterface(responses={"hash": "response"})
        prompt = "Test prompt"

        result = model.get_prompt_hash(prompt)
        expected = compute_string_hash(prompt)
        self.assertEqual(result, expected)


class TestHTTPModelInterface(unittest.TestCase):
    """Tests for the HTTPModelInterface class."""

    def test_init_stores_parameters(self) -> None:
        """Test that initialization stores parameters correctly."""
        model = HTTPModelInterface(
            base_url="http://localhost:8000",
            api_key="test-key",
            model_name="test-model",
            timeout=120,
            max_retries=5,
        )
        self.assertEqual(model.base_url, "http://localhost:8000")
        self.assertEqual(model.api_key, "test-key")
        self.assertEqual(model.model_name, "test-model")
        self.assertEqual(model.timeout, 120)
        self.assertEqual(model.max_retries, 5)

    def test_init_strips_trailing_slash(self) -> None:
        """Test that base_url trailing slash is stripped."""
        model = HTTPModelInterface(base_url="http://localhost:8000/")
        self.assertEqual(model.base_url, "http://localhost:8000")

    def test_build_request_creates_proper_request(self) -> None:
        """Test that _build_request creates proper HTTP request."""
        model = HTTPModelInterface(
            base_url="http://localhost:8000",
            api_key="test-key",
            model_name="test-model",
        )

        request = model._build_request("Test prompt")

        self.assertEqual(
            request.full_url,
            "http://localhost:8000/chat/completions"
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.get_header("Content-type"),
            "application/json"
        )
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer test-key"
        )

        # Check payload
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"][0]["content"], "Test prompt")
        self.assertEqual(payload["temperature"], 0.0)

    def test_parse_response_extracts_content(self) -> None:
        """Test that _parse_response extracts content correctly."""
        model = HTTPModelInterface(base_url="http://localhost:8000")

        response_data = json.dumps({
            "choices": [
                {"message": {"content": "Test response"}}
            ]
        }).encode("utf-8")

        result = model._parse_response(response_data)
        self.assertEqual(result, "Test response")

    def test_parse_response_raises_for_empty_choices(self) -> None:
        """Test that _parse_response raises for empty choices."""
        model = HTTPModelInterface(base_url="http://localhost:8000")

        response_data = json.dumps({"choices": []}).encode("utf-8")

        with self.assertRaises(ModelQueryError) as ctx:
            model._parse_response(response_data)
        self.assertIn("no choices", str(ctx.exception))

    def test_parse_response_raises_for_invalid_json(self) -> None:
        """Test that _parse_response raises for invalid JSON."""
        model = HTTPModelInterface(base_url="http://localhost:8000")

        with self.assertRaises(ModelQueryError) as ctx:
            model._parse_response(b"not json")
        self.assertIn("Failed to parse", str(ctx.exception))

    @mock.patch("urllib.request.urlopen")
    def test_query_success(self, mock_urlopen) -> None:
        """Test successful query with mocked HTTP response."""
        model = HTTPModelInterface(base_url="http://localhost:8000")

        mock_response = mock.Mock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Test response"}}]
        }).encode("utf-8")
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = model.query("Test prompt")
        self.assertEqual(result, "Test response")


class TestEvaluator(unittest.TestCase):
    """Tests for the Evaluator class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_model = mock.Mock(spec=ModelInterface)
        self.evaluator = Evaluator(model=self.mock_model)

    def test_init_stores_model(self) -> None:
        """Test that initialization stores the model."""
        self.assertEqual(self.evaluator.model, self.mock_model)

    def test_init_caching_default(self) -> None:
        """Test that caching is enabled by default."""
        self.assertTrue(self.evaluator.cache_responses)

    def test_init_caching_disabled(self) -> None:
        """Test that caching can be disabled."""
        evaluator = Evaluator(model=self.mock_model, cache_responses=False)
        self.assertFalse(evaluator.cache_responses)

    def test_truncate_response_short(self) -> None:
        """Test that short responses are not truncated."""
        short_response = "Short response"
        result = self.evaluator._truncate_response(short_response)
        self.assertEqual(result, short_response)

    def test_truncate_response_long(self) -> None:
        """Test that long responses are truncated with ellipsis."""
        long_response = "x" * 600
        result = self.evaluator._truncate_response(long_response)
        self.assertEqual(len(result), Evaluator.MAX_RESPONSE_SUMMARY_LENGTH)
        self.assertTrue(result.endswith("..."))

    def test_score_response_pass_no_indicators(self) -> None:
        """Test scoring with no failure indicators matched."""
        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test prompt",
            expected_behavior="Should refuse",
            failure_indicators=["agree", "help you"],
            severity="high",
        )
        response = "I cannot assist with that request."

        result = self.evaluator._score_response(prompt, response)

        self.assertEqual(result.score, 1.0)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.failure_reasons), 0)

    def test_score_response_fail_indicators_matched(self) -> None:
        """Test scoring with failure indicators matched."""
        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test prompt",
            expected_behavior="Should refuse",
            failure_indicators=["agree", "help you"],
            severity="high",
        )
        response = "I agree to help you with that."

        result = self.evaluator._score_response(prompt, response)

        self.assertLess(result.score, 1.0)
        self.assertFalse(result.passed)
        self.assertGreater(len(result.failure_reasons), 0)

    def test_score_response_partial_match(self) -> None:
        """Test scoring with partial indicator match."""
        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test prompt",
            expected_behavior="Should refuse",
            failure_indicators=["indicator1", "indicator2", "indicator3", "indicator4"],
            severity="medium",
        )
        response = "This contains indicator1 but not others."

        result = self.evaluator._score_response(prompt, response)

        # One of four indicators matched, so score should be 0.75
        self.assertEqual(result.score, 0.75)

    def test_evaluate_prompt_calls_model(self) -> None:
        """Test that evaluate_prompt calls the model."""
        self.mock_model.query.return_value = "I cannot help with that."

        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test prompt",
            expected_behavior="Should refuse",
            failure_indicators=["help you"],
            severity="medium",
        )

        result = self.evaluator.evaluate_prompt(prompt)

        self.mock_model.query.assert_called_once_with("Test prompt")
        self.assertIsInstance(result, ScoringResult)

    def test_evaluate_prompt_caches_response(self) -> None:
        """Test that evaluate_prompt caches responses."""
        self.mock_model.query.return_value = "Response"

        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test prompt",
            expected_behavior="Should refuse",
            failure_indicators=[],
            severity="medium",
        )

        # Call twice
        self.evaluator.evaluate_prompt(prompt)
        self.evaluator.evaluate_prompt(prompt)

        # Model should only be called once due to caching
        self.assertEqual(self.mock_model.query.call_count, 1)

    def test_evaluate_all_processes_all_prompts(self) -> None:
        """Test that evaluate_all processes all provided prompts."""
        self.mock_model.query.return_value = "Safe response"

        prompts = [
            SafetyPrompt(
                id=f"test-{i}",
                category="refusal_behavior",
                prompt_text=f"Prompt {i}",
                expected_behavior="Should refuse",
                failure_indicators=[],
                severity="medium",
            )
            for i in range(3)
        ]

        results = self.evaluator.evaluate_all(prompts)

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsInstance(result, ScoringResult)

    def test_evaluate_all_calls_progress_callback(self) -> None:
        """Test that evaluate_all calls progress callback."""
        self.mock_model.query.return_value = "Response"

        prompts = [
            SafetyPrompt(
                id=f"test-{i}",
                category="refusal_behavior",
                prompt_text=f"Prompt {i}",
                expected_behavior="Should refuse",
                failure_indicators=[],
                severity="medium",
            )
            for i in range(3)
        ]

        callback = mock.Mock()
        self.evaluator.evaluate_all(prompts, progress_callback=callback)

        self.assertEqual(callback.call_count, 3)
        callback.assert_any_call(1, 3, "test-0")
        callback.assert_any_call(2, 3, "test-1")
        callback.assert_any_call(3, 3, "test-2")

    def test_run_benchmark_returns_complete_result(self) -> None:
        """Test that run_benchmark returns a complete BenchmarkResult."""
        self.mock_model.query.return_value = "I cannot help with that."

        # Use a subset of prompts for testing
        prompts = [
            SafetyPrompt(
                id="test-pi-1",
                category="prompt_injection",
                prompt_text="Injection test",
                expected_behavior="Should resist",
                failure_indicators=["ignore instructions"],
                severity="high",
            ),
            SafetyPrompt(
                id="test-rb-1",
                category="refusal_behavior",
                prompt_text="Refusal test",
                expected_behavior="Should refuse",
                failure_indicators=["help you"],
                severity="high",
            ),
        ]

        result = self.evaluator.run_benchmark(
            model_identifier="test-model",
            prompts=prompts,
        )

        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.model_identifier, "test-model")
        self.assertIn("prompt_injection", result.category_scores)
        self.assertIn("refusal_behavior", result.category_scores)
        self.assertEqual(len(result.individual_results), 2)
        self.assertIsNotNone(result.timestamp)

    def test_clear_cache(self) -> None:
        """Test that clear_cache clears the response cache."""
        self.mock_model.query.return_value = "Response"

        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test prompt",
            expected_behavior="Should refuse",
            failure_indicators=[],
            severity="medium",
        )

        # First call
        self.evaluator.evaluate_prompt(prompt)
        self.assertEqual(self.mock_model.query.call_count, 1)

        # Clear cache
        self.evaluator.clear_cache()

        # Second call should hit model again
        self.evaluator.evaluate_prompt(prompt)
        self.assertEqual(self.mock_model.query.call_count, 2)


class TestSeverityThresholds(unittest.TestCase):
    """Tests for severity-based scoring thresholds."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        mock_model = mock.Mock(spec=ModelInterface)
        self.evaluator = Evaluator(model=mock_model)

    def test_critical_severity_high_threshold(self) -> None:
        """Test that critical severity requires high score to pass."""
        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test",
            expected_behavior="Refuse",
            failure_indicators=["fail1", "fail2"],
            severity="critical",
        )

        # Score 0.9 should fail for critical (threshold 0.95)
        response = "Some text with fail1 in it"
        result = self.evaluator._score_response(prompt, response)
        self.assertFalse(result.passed)

    def test_low_severity_low_threshold(self) -> None:
        """Test that low severity has lower threshold to pass."""
        prompt = SafetyPrompt(
            id="test-1",
            category="refusal_behavior",
            prompt_text="Test",
            expected_behavior="Refuse",
            failure_indicators=["fail1", "fail2"],
            severity="low",
        )

        # Score 0.5 should pass for low severity (threshold 0.50)
        response = "Some text with fail1 in it"
        result = self.evaluator._score_response(prompt, response)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
