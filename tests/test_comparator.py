"""Tests for the SecuriFine comparator module.

This module contains unit tests for benchmark result comparison,
regression detection, and assessment logic.
"""

import json
import tempfile
import unittest
from pathlib import Path

from securifine.core.comparator import (
    Comparator,
    ComparisonResult,
    comparison_result_to_dict,
    dict_to_comparison_result,
    load_benchmark_result,
    save_benchmark_result,
    is_statistically_significant,
)
from securifine.safety.benchmarks import (
    BenchmarkResult,
    ScoringResult,
    benchmark_result_to_dict,
)


def create_scoring_result(
    prompt_id: str,
    category: str,
    score: float,
    passed: bool,
) -> ScoringResult:
    """Helper to create a ScoringResult."""
    return ScoringResult(
        prompt_id=prompt_id,
        category=category,
        score=score,
        passed=passed,
        response_summary="Test response",
        failure_reasons=[] if passed else ["Failed test"],
    )


def create_benchmark_result(
    model_identifier: str,
    category_scores: dict,
    individual_results: list,
    aggregate_score: float,
    overall_passed: bool,
) -> BenchmarkResult:
    """Helper to create a BenchmarkResult."""
    category_passed = {
        cat: score >= 0.7 for cat, score in category_scores.items()
    }
    return BenchmarkResult(
        model_identifier=model_identifier,
        timestamp="2024-01-01T00:00:00Z",
        category_scores=category_scores,
        category_passed=category_passed,
        individual_results=individual_results,
        aggregate_score=aggregate_score,
        overall_passed=overall_passed,
    )


class TestComparator(unittest.TestCase):
    """Tests for the Comparator class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.comparator = Comparator()

    def test_compare_identical_results(self) -> None:
        """Test comparison of identical results."""
        individual_results = [
            create_scoring_result("test-1", "refusal_behavior", 1.0, True),
            create_scoring_result("test-2", "prompt_injection", 0.9, True),
        ]

        baseline = create_benchmark_result(
            model_identifier="model-base",
            category_scores={
                "refusal_behavior": 1.0,
                "prompt_injection": 0.9,
            },
            individual_results=individual_results,
            aggregate_score=0.95,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="model-finetuned",
            category_scores={
                "refusal_behavior": 1.0,
                "prompt_injection": 0.9,
            },
            individual_results=individual_results,
            aggregate_score=0.95,
            overall_passed=True,
        )

        result = self.comparator.compare(baseline, comparison)

        self.assertEqual(result.aggregate_delta, 0.0)
        self.assertEqual(len(result.regressions), 0)
        self.assertEqual(len(result.improvements), 0)
        self.assertEqual(result.overall_assessment, "passed")

    def test_compare_with_improvement(self) -> None:
        """Test comparison showing improvement."""
        baseline_results = [
            create_scoring_result("test-1", "refusal_behavior", 0.7, True),
        ]
        comparison_results = [
            create_scoring_result("test-1", "refusal_behavior", 0.9, True),
        ]

        baseline = create_benchmark_result(
            model_identifier="model-base",
            category_scores={"refusal_behavior": 0.7},
            individual_results=baseline_results,
            aggregate_score=0.7,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="model-finetuned",
            category_scores={"refusal_behavior": 0.9},
            individual_results=comparison_results,
            aggregate_score=0.9,
            overall_passed=True,
        )

        result = self.comparator.compare(baseline, comparison)

        self.assertGreater(result.aggregate_delta, 0)
        self.assertEqual(len(result.regressions), 0)
        self.assertEqual(len(result.improvements), 1)
        self.assertEqual(result.overall_assessment, "passed")

    def test_compare_with_regression(self) -> None:
        """Test comparison showing regression."""
        baseline_results = [
            create_scoring_result("test-1", "refusal_behavior", 0.9, True),
        ]
        comparison_results = [
            create_scoring_result("test-1", "refusal_behavior", 0.7, True),
        ]

        baseline = create_benchmark_result(
            model_identifier="model-base",
            category_scores={"refusal_behavior": 0.9},
            individual_results=baseline_results,
            aggregate_score=0.9,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="model-finetuned",
            category_scores={"refusal_behavior": 0.7},
            individual_results=comparison_results,
            aggregate_score=0.7,
            overall_passed=True,
        )

        result = self.comparator.compare(baseline, comparison)

        self.assertLess(result.aggregate_delta, 0)
        self.assertEqual(len(result.regressions), 1)
        self.assertEqual(len(result.improvements), 0)
        # Large regression should trigger warning or failure
        self.assertIn(result.overall_assessment, ["warning", "failed"])

    def test_compare_with_severe_regression(self) -> None:
        """Test comparison with severe regression triggers failure."""
        baseline_results = [
            create_scoring_result("test-1", "refusal_behavior", 1.0, True),
        ]
        comparison_results = [
            create_scoring_result("test-1", "refusal_behavior", 0.7, False),
        ]

        baseline = create_benchmark_result(
            model_identifier="model-base",
            category_scores={"refusal_behavior": 1.0},
            individual_results=baseline_results,
            aggregate_score=1.0,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="model-finetuned",
            category_scores={"refusal_behavior": 0.7},
            individual_results=comparison_results,
            aggregate_score=0.7,
            overall_passed=True,
        )

        result = self.comparator.compare(baseline, comparison)

        # 0.3 drop exceeds severe regression threshold (0.15)
        self.assertGreater(len(result.severe_regressions), 0)
        self.assertEqual(result.overall_assessment, "failed")

    def test_compare_mixed_changes(self) -> None:
        """Test comparison with both improvements and regressions."""
        baseline_results = [
            create_scoring_result("test-1", "refusal_behavior", 0.8, True),
            create_scoring_result("test-2", "prompt_injection", 0.9, True),
        ]
        comparison_results = [
            create_scoring_result("test-1", "refusal_behavior", 0.9, True),
            create_scoring_result("test-2", "prompt_injection", 0.8, True),
        ]

        baseline = create_benchmark_result(
            model_identifier="model-base",
            category_scores={
                "refusal_behavior": 0.8,
                "prompt_injection": 0.9,
            },
            individual_results=baseline_results,
            aggregate_score=0.85,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="model-finetuned",
            category_scores={
                "refusal_behavior": 0.9,
                "prompt_injection": 0.8,
            },
            individual_results=comparison_results,
            aggregate_score=0.85,
            overall_passed=True,
        )

        result = self.comparator.compare(baseline, comparison)

        self.assertEqual(len(result.regressions), 1)
        self.assertEqual(len(result.improvements), 1)
        self.assertEqual(result.regressions[0]["prompt_id"], "test-2")
        self.assertEqual(result.improvements[0]["prompt_id"], "test-1")


class TestCategoryDeltas(unittest.TestCase):
    """Tests for category delta calculation."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.comparator = Comparator()

    def test_calculate_category_deltas(self) -> None:
        """Test category delta calculation."""
        baseline = create_benchmark_result(
            model_identifier="base",
            category_scores={
                "refusal_behavior": 0.8,
                "prompt_injection": 0.9,
                "information_leakage": 0.7,
            },
            individual_results=[],
            aggregate_score=0.8,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="comparison",
            category_scores={
                "refusal_behavior": 0.9,  # +0.1
                "prompt_injection": 0.85,  # -0.05
                "information_leakage": 0.7,  # 0
            },
            individual_results=[],
            aggregate_score=0.82,
            overall_passed=True,
        )

        deltas = self.comparator._calculate_category_deltas(baseline, comparison)

        self.assertAlmostEqual(deltas["refusal_behavior"], 0.1)
        self.assertAlmostEqual(deltas["prompt_injection"], -0.05)
        self.assertAlmostEqual(deltas["information_leakage"], 0.0)


class TestAssessmentDetermination(unittest.TestCase):
    """Tests for overall assessment determination."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.comparator = Comparator()

    def test_passed_when_improved(self) -> None:
        """Test that assessment is 'passed' when scores improve."""
        assessment = self.comparator._determine_assessment(
            aggregate_delta=0.1,
            severe_regressions=[],
            category_deltas={"refusal_behavior": 0.1},
        )
        self.assertEqual(assessment, "passed")

    def test_passed_when_stable(self) -> None:
        """Test that assessment is 'passed' when scores are stable."""
        assessment = self.comparator._determine_assessment(
            aggregate_delta=0.0,
            severe_regressions=[],
            category_deltas={"refusal_behavior": 0.0},
        )
        self.assertEqual(assessment, "passed")

    def test_warning_with_minor_regression(self) -> None:
        """Test that assessment is 'warning' with minor regression."""
        assessment = self.comparator._determine_assessment(
            aggregate_delta=-0.03,  # Minor decrease
            severe_regressions=[],
            category_deltas={"refusal_behavior": -0.03},
        )
        self.assertEqual(assessment, "warning")

    def test_failed_with_severe_regression(self) -> None:
        """Test that assessment is 'failed' with severe regression."""
        assessment = self.comparator._determine_assessment(
            aggregate_delta=-0.1,
            severe_regressions=["test-1"],
            category_deltas={"refusal_behavior": -0.1},
        )
        self.assertEqual(assessment, "failed")

    def test_failed_with_significant_decrease(self) -> None:
        """Test that assessment is 'failed' with significant aggregate decrease."""
        assessment = self.comparator._determine_assessment(
            aggregate_delta=-0.1,  # Exceeds SIGNIFICANT_DECREASE_THRESHOLD
            severe_regressions=[],
            category_deltas={"refusal_behavior": -0.1},
        )
        self.assertEqual(assessment, "failed")


class TestLoadAndSaveBenchmarkResult(unittest.TestCase):
    """Tests for loading and saving benchmark results."""

    def test_save_and_load_benchmark_result(self) -> None:
        """Test saving and loading a benchmark result."""
        original = create_benchmark_result(
            model_identifier="test-model",
            category_scores={"refusal_behavior": 0.9},
            individual_results=[
                create_scoring_result("test-1", "refusal_behavior", 0.9, True),
            ],
            aggregate_score=0.9,
            overall_passed=True,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            save_benchmark_result(original, path)
            loaded = load_benchmark_result(path)

            self.assertEqual(original.model_identifier, loaded.model_identifier)
            self.assertEqual(original.aggregate_score, loaded.aggregate_score)
            self.assertEqual(original.overall_passed, loaded.overall_passed)
            self.assertEqual(
                len(original.individual_results),
                len(loaded.individual_results),
            )
        finally:
            Path(path).unlink()

    def test_load_nonexistent_file(self) -> None:
        """Test that loading nonexistent file raises error."""
        with self.assertRaises(FileNotFoundError):
            load_benchmark_result("/nonexistent/file.json")


class TestLoadAndCompare(unittest.TestCase):
    """Tests for the load_and_compare convenience method."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.comparator = Comparator()

    def test_load_and_compare(self) -> None:
        """Test loading and comparing from files."""
        baseline = create_benchmark_result(
            model_identifier="baseline",
            category_scores={"refusal_behavior": 0.8},
            individual_results=[
                create_scoring_result("test-1", "refusal_behavior", 0.8, True),
            ],
            aggregate_score=0.8,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="comparison",
            category_scores={"refusal_behavior": 0.9},
            individual_results=[
                create_scoring_result("test-1", "refusal_behavior", 0.9, True),
            ],
            aggregate_score=0.9,
            overall_passed=True,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            baseline_path = f.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            comparison_path = f.name

        try:
            save_benchmark_result(baseline, baseline_path)
            save_benchmark_result(comparison, comparison_path)

            result = self.comparator.load_and_compare(
                baseline_path, comparison_path
            )

            self.assertIsInstance(result, ComparisonResult)
            self.assertGreater(result.aggregate_delta, 0)
        finally:
            Path(baseline_path).unlink()
            Path(comparison_path).unlink()


class TestComparisonResultSerialization(unittest.TestCase):
    """Tests for ComparisonResult serialization."""

    def test_to_dict(self) -> None:
        """Test converting ComparisonResult to dictionary."""
        baseline = create_benchmark_result(
            model_identifier="baseline",
            category_scores={"refusal_behavior": 0.8},
            individual_results=[],
            aggregate_score=0.8,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="comparison",
            category_scores={"refusal_behavior": 0.9},
            individual_results=[],
            aggregate_score=0.9,
            overall_passed=True,
        )

        result = ComparisonResult(
            baseline_result=baseline,
            comparison_result=comparison,
            category_deltas={"refusal_behavior": 0.1},
            aggregate_delta=0.1,
            regressions=[],
            improvements=[{"prompt_id": "test-1", "delta": 0.1}],
            severe_regressions=[],
            overall_assessment="passed",
        )

        data = comparison_result_to_dict(result)

        self.assertIn("baseline_result", data)
        self.assertIn("comparison_result", data)
        self.assertEqual(data["aggregate_delta"], 0.1)
        self.assertEqual(data["overall_assessment"], "passed")
        self.assertEqual(len(data["improvements"]), 1)

    def test_from_dict(self) -> None:
        """Test creating ComparisonResult from dictionary."""
        baseline_data = benchmark_result_to_dict(
            create_benchmark_result(
                model_identifier="baseline",
                category_scores={"refusal_behavior": 0.8},
                individual_results=[],
                aggregate_score=0.8,
                overall_passed=True,
            )
        )

        comparison_data = benchmark_result_to_dict(
            create_benchmark_result(
                model_identifier="comparison",
                category_scores={"refusal_behavior": 0.9},
                individual_results=[],
                aggregate_score=0.9,
                overall_passed=True,
            )
        )

        data = {
            "baseline_result": baseline_data,
            "comparison_result": comparison_data,
            "category_deltas": {"refusal_behavior": 0.1},
            "aggregate_delta": 0.1,
            "regressions": [],
            "improvements": [{"prompt_id": "test-1", "delta": 0.1}],
            "severe_regressions": [],
            "overall_assessment": "passed",
        }

        result = dict_to_comparison_result(data)

        self.assertIsInstance(result, ComparisonResult)
        self.assertEqual(result.aggregate_delta, 0.1)
        self.assertEqual(result.overall_assessment, "passed")

    def test_round_trip_serialization(self) -> None:
        """Test round-trip serialization."""
        baseline = create_benchmark_result(
            model_identifier="baseline",
            category_scores={"refusal_behavior": 0.8},
            individual_results=[
                create_scoring_result("test-1", "refusal_behavior", 0.8, True),
            ],
            aggregate_score=0.8,
            overall_passed=True,
        )

        comparison = create_benchmark_result(
            model_identifier="comparison",
            category_scores={"refusal_behavior": 0.9},
            individual_results=[
                create_scoring_result("test-1", "refusal_behavior", 0.9, True),
            ],
            aggregate_score=0.9,
            overall_passed=True,
        )

        original = ComparisonResult(
            baseline_result=baseline,
            comparison_result=comparison,
            category_deltas={"refusal_behavior": 0.1},
            aggregate_delta=0.1,
            regressions=[],
            improvements=[{"prompt_id": "test-1", "delta": 0.1}],
            severe_regressions=[],
            overall_assessment="passed",
        )

        data = comparison_result_to_dict(original)
        restored = dict_to_comparison_result(data)

        self.assertEqual(original.aggregate_delta, restored.aggregate_delta)
        self.assertEqual(
            original.overall_assessment, restored.overall_assessment
        )
        self.assertEqual(
            len(original.improvements), len(restored.improvements)
        )


class TestStatisticalSignificance(unittest.TestCase):
    """Tests for statistical significance helper."""

    def test_significant_change(self) -> None:
        """Test that large changes are significant."""
        self.assertTrue(is_statistically_significant(0.1))
        self.assertTrue(is_statistically_significant(-0.1))

    def test_insignificant_change(self) -> None:
        """Test that small changes are not significant."""
        self.assertFalse(is_statistically_significant(0.01))
        self.assertFalse(is_statistically_significant(-0.01))

    def test_custom_threshold(self) -> None:
        """Test with custom threshold."""
        self.assertTrue(is_statistically_significant(0.03, threshold=0.02))
        self.assertFalse(is_statistically_significant(0.01, threshold=0.02))


if __name__ == "__main__":
    unittest.main()
