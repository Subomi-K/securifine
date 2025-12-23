"""Reporter module for SecuriFine.

This module provides report generation in various formats (JSON, Markdown, HTML)
from comparison results.
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List

from securifine.core.comparator import ComparisonResult, comparison_result_to_dict
from securifine import __version__


class Reporter(ABC):
    """Abstract base class for report generators.

    All reporter implementations must implement the generate method
    to produce formatted output from a ComparisonResult.
    """

    @abstractmethod
    def generate(self, comparison: ComparisonResult) -> str:
        """Generate a report from a comparison result.

        Args:
            comparison: The comparison result to report on.

        Returns:
            The formatted report as a string.
        """
        pass


class JSONReporter(Reporter):
    """Generates JSON-formatted reports."""

    def __init__(self, indent: int = 2) -> None:
        """Initialize the JSON reporter.

        Args:
            indent: Number of spaces for JSON indentation.
        """
        self.indent = indent

    def generate(self, comparison: ComparisonResult) -> str:
        """Generate a JSON report.

        Args:
            comparison: The comparison result to report on.

        Returns:
            Pretty-printed JSON string.
        """
        data = comparison_result_to_dict(comparison)

        # Add metadata
        data["_metadata"] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool_version": __version__,
            "format": "json",
        }

        return json.dumps(data, indent=self.indent)


class MarkdownReporter(Reporter):
    """Generates Markdown-formatted reports."""

    def generate(self, comparison: ComparisonResult) -> str:
        """Generate a Markdown report.

        Args:
            comparison: The comparison result to report on.

        Returns:
            Markdown-formatted string.
        """
        lines: List[str] = []

        # Title
        lines.append("# SecuriFine Safety Comparison Report")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(self._generate_summary(comparison))
        lines.append("")

        # Overall Scores
        lines.append("## Overall Score Comparison")
        lines.append("")
        lines.append(self._generate_score_comparison(comparison))
        lines.append("")

        # Category Breakdown
        lines.append("## Per-Category Breakdown")
        lines.append("")
        lines.append(self._generate_category_table(comparison))
        lines.append("")

        # Regressions
        if comparison.regressions:
            lines.append("## Significant Regressions")
            lines.append("")
            lines.append(self._generate_regressions(comparison))
            lines.append("")

        # Severe Regressions Warning
        if comparison.severe_regressions:
            lines.append("## Severe Regressions (Critical)")
            lines.append("")
            lines.append(self._generate_severe_regressions(comparison))
            lines.append("")

        # Improvements
        if comparison.improvements:
            lines.append("## Improvements")
            lines.append("")
            lines.append(self._generate_improvements(comparison))
            lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")
        lines.append(self._generate_recommendations(comparison))
        lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(self._generate_footer())

        return "\n".join(lines)

    def _generate_summary(self, comparison: ComparisonResult) -> str:
        """Generate the executive summary section."""
        baseline = comparison.baseline_result
        comp = comparison.comparison_result
        assessment = comparison.overall_assessment.upper()

        status_text = {
            "PASSED": "The fine-tuned model maintains acceptable safety alignment.",
            "WARNING": "The fine-tuned model shows minor safety regressions that should be reviewed.",
            "FAILED": "The fine-tuned model shows significant safety degradation requiring remediation.",
        }

        lines = [
            f"**Status: {assessment}**",
            "",
            status_text.get(assessment, ""),
            "",
            f"- **Baseline Model:** {baseline.model_identifier}",
            f"- **Comparison Model:** {comp.model_identifier}",
            f"- **Baseline Evaluation:** {baseline.timestamp}",
            f"- **Comparison Evaluation:** {comp.timestamp}",
        ]

        return "\n".join(lines)

    def _generate_score_comparison(self, comparison: ComparisonResult) -> str:
        """Generate the score comparison section."""
        baseline = comparison.baseline_result
        comp = comparison.comparison_result
        delta = comparison.aggregate_delta

        delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"

        lines = [
            "| Metric | Baseline | Comparison | Delta |",
            "|--------|----------|------------|-------|",
            f"| Aggregate Score | {baseline.aggregate_score:.3f} | {comp.aggregate_score:.3f} | {delta_str} |",
            f"| Overall Passed | {baseline.overall_passed} | {comp.overall_passed} | - |",
        ]

        return "\n".join(lines)

    def _generate_category_table(self, comparison: ComparisonResult) -> str:
        """Generate the category breakdown table."""
        baseline = comparison.baseline_result
        comp = comparison.comparison_result

        lines = [
            "| Category | Baseline | Comparison | Delta | Status |",
            "|----------|----------|------------|-------|--------|",
        ]

        for category in sorted(comparison.category_deltas.keys()):
            b_score = baseline.category_scores.get(category, 0.0)
            c_score = comp.category_scores.get(category, 0.0)
            delta = comparison.category_deltas[category]
            delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"

            b_passed = baseline.category_passed.get(category, False)
            c_passed = comp.category_passed.get(category, False)

            if c_passed and b_passed:
                status = "Passing"
            elif c_passed and not b_passed:
                status = "Improved"
            elif not c_passed and b_passed:
                status = "Regressed"
            else:
                status = "Failing"

            lines.append(
                f"| {category} | {b_score:.3f} | {c_score:.3f} | {delta_str} | {status} |"
            )

        return "\n".join(lines)

    def _generate_regressions(self, comparison: ComparisonResult) -> str:
        """Generate the regressions section."""
        lines = []

        # Show top 10 regressions
        for i, reg in enumerate(comparison.regressions[:10]):
            lines.append(f"### {i + 1}. {reg['prompt_id']}")
            lines.append("")
            lines.append(f"- **Category:** {reg['category']}")
            lines.append(f"- **Baseline Score:** {reg['baseline_score']:.3f}")
            lines.append(f"- **Comparison Score:** {reg['comparison_score']:.3f}")
            lines.append(f"- **Delta:** {reg['delta']:.3f}")

            if reg.get("failure_reasons"):
                lines.append("- **Failure Reasons:**")
                for reason in reg["failure_reasons"]:
                    lines.append(f"  - {reason}")

            lines.append("")

        if len(comparison.regressions) > 10:
            lines.append(
                f"*... and {len(comparison.regressions) - 10} more regressions.*"
            )

        return "\n".join(lines)

    def _generate_severe_regressions(self, comparison: ComparisonResult) -> str:
        """Generate the severe regressions warning section."""
        lines = [
            "The following prompts showed critical safety degradation:",
            "",
        ]

        for prompt_id in comparison.severe_regressions:
            lines.append(f"- `{prompt_id}`")

        lines.append("")
        lines.append(
            "These regressions require immediate attention before deploying "
            "the fine-tuned model."
        )

        return "\n".join(lines)

    def _generate_improvements(self, comparison: ComparisonResult) -> str:
        """Generate the improvements section."""
        lines = []

        # Show top 5 improvements
        for i, imp in enumerate(comparison.improvements[:5]):
            lines.append(
                f"- **{imp['prompt_id']}** ({imp['category']}): "
                f"{imp['baseline_score']:.3f} -> {imp['comparison_score']:.3f} "
                f"(+{imp['delta']:.3f})"
            )

        if len(comparison.improvements) > 5:
            lines.append(
                f"- *... and {len(comparison.improvements) - 5} more improvements.*"
            )

        return "\n".join(lines)

    def _generate_recommendations(self, comparison: ComparisonResult) -> str:
        """Generate recommendations based on the comparison results."""
        lines = []

        assessment = comparison.overall_assessment

        if assessment == "passed":
            lines.append(
                "The fine-tuned model appears to maintain acceptable safety alignment. "
                "However, consider the following:"
            )
            lines.append("")
            lines.append("1. Continue monitoring safety metrics in production.")
            lines.append("2. Periodically re-run evaluations as the model is used.")
            lines.append(
                "3. Consider additional red-team testing for high-stakes deployments."
            )

        elif assessment == "warning":
            lines.append(
                "The fine-tuned model shows some concerning changes. Recommended actions:"
            )
            lines.append("")
            lines.append("1. Review the specific regressions identified above.")
            lines.append(
                "2. Consider adjusting fine-tuning data or parameters to address regressions."
            )
            lines.append("3. Run additional targeted testing on regression categories.")
            lines.append(
                "4. Evaluate whether the regressions are acceptable for your use case."
            )

        else:  # failed
            lines.append(
                "The fine-tuned model shows significant safety degradation. "
                "Recommended actions:"
            )
            lines.append("")
            lines.append(
                "1. Do not deploy this model without addressing the identified issues."
            )
            lines.append("2. Review training data for content that may cause degradation.")
            lines.append(
                "3. Consider using safety-focused fine-tuning techniques (e.g., RLHF)."
            )
            lines.append("4. Reduce the extent of fine-tuning or use regularization.")
            lines.append("5. Consult with safety experts before proceeding.")

        return "\n".join(lines)

    def _generate_footer(self) -> str:
        """Generate the report footer."""
        timestamp = datetime.now(timezone.utc).isoformat()
        return f"*Generated by SecuriFine v{__version__} at {timestamp}*"


class HTMLReporter(Reporter):
    """Generates HTML-formatted reports with monochrome styling."""

    def generate(self, comparison: ComparisonResult) -> str:
        """Generate an HTML report.

        Args:
            comparison: The comparison result to report on.

        Returns:
            HTML-formatted string.
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SecuriFine Safety Comparison Report</title>
    {self._generate_styles()}
</head>
<body>
    <div class="container">
        {self._generate_header()}
        {self._generate_summary_section(comparison)}
        {self._generate_scores_section(comparison)}
        {self._generate_categories_section(comparison)}
        {self._generate_regressions_section(comparison)}
        {self._generate_improvements_section(comparison)}
        {self._generate_recommendations_section(comparison)}
        {self._generate_footer_section()}
    </div>
</body>
</html>"""

    def _generate_styles(self) -> str:
        """Generate inline CSS styles (monochrome design)."""
        return """<style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #fff;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem;
        }

        h1, h2, h3 {
            color: #000;
            margin-bottom: 1rem;
        }

        h1 {
            font-size: 2rem;
            border-bottom: 2px solid #000;
            padding-bottom: 0.5rem;
            margin-bottom: 2rem;
        }

        h2 {
            font-size: 1.5rem;
            border-bottom: 1px solid #ccc;
            padding-bottom: 0.3rem;
            margin-top: 2rem;
        }

        h3 {
            font-size: 1.1rem;
            color: #333;
        }

        p {
            margin-bottom: 1rem;
        }

        .summary-box {
            border: 2px solid #000;
            padding: 1.5rem;
            margin: 1rem 0;
            background-color: #f9f9f9;
        }

        .status {
            font-size: 1.3rem;
            font-weight: bold;
            margin-bottom: 1rem;
        }

        .status-passed {
            color: #333;
            border-left: 4px solid #666;
            padding-left: 1rem;
        }

        .status-warning {
            color: #333;
            border-left: 4px solid #999;
            padding-left: 1rem;
        }

        .status-failed {
            color: #000;
            border-left: 4px solid #000;
            padding-left: 1rem;
        }

        .meta-info {
            color: #666;
            font-size: 0.9rem;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }

        th, td {
            padding: 0.75rem;
            text-align: left;
            border: 1px solid #ccc;
        }

        th {
            background-color: #eee;
            font-weight: 600;
            color: #000;
        }

        tr:nth-child(even) {
            background-color: #f9f9f9;
        }

        .delta-positive {
            color: #333;
        }

        .delta-negative {
            color: #000;
            font-weight: bold;
        }

        .regression-item {
            border: 1px solid #ccc;
            padding: 1rem;
            margin: 0.5rem 0;
            background-color: #fafafa;
        }

        .severe {
            border-color: #000;
            border-width: 2px;
        }

        .improvement-item {
            padding: 0.5rem 0;
            border-bottom: 1px solid #eee;
        }

        .recommendations {
            background-color: #f5f5f5;
            padding: 1.5rem;
            border: 1px solid #ccc;
        }

        .recommendations ol {
            margin-left: 1.5rem;
        }

        .recommendations li {
            margin-bottom: 0.5rem;
        }

        .footer {
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid #ccc;
            color: #666;
            font-size: 0.85rem;
            text-align: center;
        }

        code {
            background-color: #eee;
            padding: 0.2rem 0.4rem;
            font-family: "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.9em;
        }

        ul {
            margin-left: 1.5rem;
            margin-bottom: 1rem;
        }

        li {
            margin-bottom: 0.3rem;
        }

        @media (max-width: 600px) {
            .container {
                padding: 1rem;
            }

            h1 {
                font-size: 1.5rem;
            }

            table {
                font-size: 0.9rem;
            }

            th, td {
                padding: 0.5rem;
            }
        }
    </style>"""

    def _generate_header(self) -> str:
        """Generate the report header."""
        return "<h1>SecuriFine Safety Comparison Report</h1>"

    def _generate_summary_section(self, comparison: ComparisonResult) -> str:
        """Generate the executive summary section."""
        baseline = comparison.baseline_result
        comp = comparison.comparison_result
        assessment = comparison.overall_assessment

        status_class = f"status-{assessment}"
        status_text = {
            "passed": "PASSED - The fine-tuned model maintains acceptable safety alignment.",
            "warning": "WARNING - The fine-tuned model shows minor safety regressions.",
            "failed": "FAILED - The fine-tuned model shows significant safety degradation.",
        }

        return f"""
        <h2>Executive Summary</h2>
        <div class="summary-box">
            <div class="status {status_class}">{status_text.get(assessment, assessment.upper())}</div>
            <div class="meta-info">
                <p><strong>Baseline Model:</strong> {self._escape(baseline.model_identifier)}</p>
                <p><strong>Comparison Model:</strong> {self._escape(comp.model_identifier)}</p>
                <p><strong>Baseline Evaluation:</strong> {baseline.timestamp}</p>
                <p><strong>Comparison Evaluation:</strong> {comp.timestamp}</p>
            </div>
        </div>"""

    def _generate_scores_section(self, comparison: ComparisonResult) -> str:
        """Generate the overall scores section."""
        baseline = comparison.baseline_result
        comp = comparison.comparison_result
        delta = comparison.aggregate_delta

        delta_class = "delta-positive" if delta >= 0 else "delta-negative"
        delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"

        return f"""
        <h2>Overall Score Comparison</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Baseline</th>
                    <th>Comparison</th>
                    <th>Delta</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Aggregate Score</td>
                    <td>{baseline.aggregate_score:.3f}</td>
                    <td>{comp.aggregate_score:.3f}</td>
                    <td class="{delta_class}">{delta_str}</td>
                </tr>
                <tr>
                    <td>Overall Passed</td>
                    <td>{baseline.overall_passed}</td>
                    <td>{comp.overall_passed}</td>
                    <td>-</td>
                </tr>
            </tbody>
        </table>"""

    def _generate_categories_section(self, comparison: ComparisonResult) -> str:
        """Generate the category breakdown section."""
        baseline = comparison.baseline_result
        comp = comparison.comparison_result

        rows = []
        for category in sorted(comparison.category_deltas.keys()):
            b_score = baseline.category_scores.get(category, 0.0)
            c_score = comp.category_scores.get(category, 0.0)
            delta = comparison.category_deltas[category]

            delta_class = "delta-positive" if delta >= 0 else "delta-negative"
            delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"

            b_passed = baseline.category_passed.get(category, False)
            c_passed = comp.category_passed.get(category, False)

            if c_passed and b_passed:
                status = "Passing"
            elif c_passed and not b_passed:
                status = "Improved"
            elif not c_passed and b_passed:
                status = "Regressed"
            else:
                status = "Failing"

            rows.append(f"""
                <tr>
                    <td>{self._escape(category)}</td>
                    <td>{b_score:.3f}</td>
                    <td>{c_score:.3f}</td>
                    <td class="{delta_class}">{delta_str}</td>
                    <td>{status}</td>
                </tr>""")

        return f"""
        <h2>Per-Category Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Baseline</th>
                    <th>Comparison</th>
                    <th>Delta</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>"""

    def _generate_regressions_section(self, comparison: ComparisonResult) -> str:
        """Generate the regressions section."""
        if not comparison.regressions:
            return ""

        items = []
        for reg in comparison.regressions[:10]:
            is_severe = reg["prompt_id"] in comparison.severe_regressions
            severe_class = " severe" if is_severe else ""
            severe_label = " (SEVERE)" if is_severe else ""

            failure_html = ""
            if reg.get("failure_reasons"):
                reasons = "".join(
                    f"<li>{self._escape(r)}</li>" for r in reg["failure_reasons"]
                )
                failure_html = f"<p><strong>Failure Reasons:</strong></p><ul>{reasons}</ul>"

            items.append(f"""
                <div class="regression-item{severe_class}">
                    <h3>{self._escape(reg['prompt_id'])}{severe_label}</h3>
                    <p><strong>Category:</strong> {self._escape(reg['category'])}</p>
                    <p><strong>Score:</strong> {reg['baseline_score']:.3f} &rarr; {reg['comparison_score']:.3f} ({reg['delta']:.3f})</p>
                    {failure_html}
                </div>""")

        more = ""
        if len(comparison.regressions) > 10:
            more = f"<p><em>... and {len(comparison.regressions) - 10} more regressions.</em></p>"

        severe_warning = ""
        if comparison.severe_regressions:
            severe_list = ", ".join(
                f"<code>{self._escape(p)}</code>" for p in comparison.severe_regressions
            )
            severe_warning = f"""
                <div class="summary-box severe">
                    <h3>Severe Regressions Detected</h3>
                    <p>The following prompts require immediate attention: {severe_list}</p>
                </div>"""

        return f"""
        <h2>Significant Regressions</h2>
        {severe_warning}
        {"".join(items)}
        {more}"""

    def _generate_improvements_section(self, comparison: ComparisonResult) -> str:
        """Generate the improvements section."""
        if not comparison.improvements:
            return ""

        items = []
        for imp in comparison.improvements[:5]:
            items.append(f"""
                <div class="improvement-item">
                    <strong>{self._escape(imp['prompt_id'])}</strong> ({self._escape(imp['category'])}):
                    {imp['baseline_score']:.3f} &rarr; {imp['comparison_score']:.3f}
                    <span class="delta-positive">(+{imp['delta']:.3f})</span>
                </div>""")

        more = ""
        if len(comparison.improvements) > 5:
            more = f"<p><em>... and {len(comparison.improvements) - 5} more improvements.</em></p>"

        return f"""
        <h2>Improvements</h2>
        {"".join(items)}
        {more}"""

    def _generate_recommendations_section(self, comparison: ComparisonResult) -> str:
        """Generate the recommendations section."""
        assessment = comparison.overall_assessment

        if assessment == "passed":
            content = """
                <p>The fine-tuned model appears to maintain acceptable safety alignment.
                However, consider the following:</p>
                <ol>
                    <li>Continue monitoring safety metrics in production.</li>
                    <li>Periodically re-run evaluations as the model is used.</li>
                    <li>Consider additional red-team testing for high-stakes deployments.</li>
                </ol>"""
        elif assessment == "warning":
            content = """
                <p>The fine-tuned model shows some concerning changes. Recommended actions:</p>
                <ol>
                    <li>Review the specific regressions identified above.</li>
                    <li>Consider adjusting fine-tuning data or parameters to address regressions.</li>
                    <li>Run additional targeted testing on regression categories.</li>
                    <li>Evaluate whether the regressions are acceptable for your use case.</li>
                </ol>"""
        else:
            content = """
                <p>The fine-tuned model shows significant safety degradation.
                Recommended actions:</p>
                <ol>
                    <li>Do not deploy this model without addressing the identified issues.</li>
                    <li>Review training data for content that may cause degradation.</li>
                    <li>Consider using safety-focused fine-tuning techniques (e.g., RLHF).</li>
                    <li>Reduce the extent of fine-tuning or use regularization.</li>
                    <li>Consult with safety experts before proceeding.</li>
                </ol>"""

        return f"""
        <h2>Recommendations</h2>
        <div class="recommendations">
            {content}
        </div>"""

    def _generate_footer_section(self) -> str:
        """Generate the report footer."""
        timestamp = datetime.now(timezone.utc).isoformat()
        return f"""
        <div class="footer">
            Generated by SecuriFine v{__version__} at {timestamp}
        </div>"""

    def _escape(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )


def get_reporter(format: str) -> Reporter:
    """Get a reporter instance for the specified format.

    Args:
        format: The output format ("json", "md", or "html").

    Returns:
        A Reporter instance for the specified format.

    Raises:
        ValueError: If the format is not recognized.
    """
    reporters = {
        "json": JSONReporter,
        "md": MarkdownReporter,
        "markdown": MarkdownReporter,
        "html": HTMLReporter,
    }

    format_lower = format.lower()
    if format_lower not in reporters:
        valid_formats = ", ".join(sorted(set(reporters.keys())))
        raise ValueError(
            f"Unknown report format '{format}'. Valid formats: {valid_formats}"
        )

    return reporters[format_lower]()
