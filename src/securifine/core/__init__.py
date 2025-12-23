"""Core modules for SecuriFine evaluation and comparison."""

from securifine.core.evaluator import (
    ModelQueryError,
    ModelInterface,
    HTTPModelInterface,
    OfflineModelInterface,
    Evaluator,
)

from securifine.core.comparator import (
    ComparisonResult,
    Comparator,
    load_benchmark_result,
    save_benchmark_result,
    comparison_result_to_dict,
    dict_to_comparison_result,
    is_statistically_significant,
)

from securifine.core.reporter import (
    Reporter,
    JSONReporter,
    MarkdownReporter,
    HTMLReporter,
    get_reporter,
)

__all__ = [
    # evaluator
    "ModelQueryError",
    "ModelInterface",
    "HTTPModelInterface",
    "OfflineModelInterface",
    "Evaluator",
    # comparator
    "ComparisonResult",
    "Comparator",
    "load_benchmark_result",
    "save_benchmark_result",
    "comparison_result_to_dict",
    "dict_to_comparison_result",
    "is_statistically_significant",
    # reporter
    "Reporter",
    "JSONReporter",
    "MarkdownReporter",
    "HTMLReporter",
    "get_reporter",
]
