"""
calibration/snorkel_metrics.py — Metrics and reporting for Snorkel weak labels.
OWNER: Chief Engineer.

Generates human-readable reports and visualizations from Snorkel output.
"""

import pandas as pd
import json
import logging
from typing import Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class SnorkelMetricsReporter:
    """Generate metrics reports and analysis from Snorkel output."""

    def __init__(self, weak_labels_df: pd.DataFrame, metrics_dict: Dict):
        """
        Args:
            weak_labels_df: DataFrame with columns [chat_id, neuron_id, weak_label, confidence]
            metrics_dict: metrics dict from orchestrator
        """
        self.df = weak_labels_df
        self.metrics = metrics_dict

    def summary_report(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            "SNORKEL METRICS REPORT",
            "=" * 60,
            f"Total (chat, neuron) pairs: {self.metrics['total_pairs']:,}",
            f"Labeled pairs: {self.metrics['labeled_pairs']:,}",
            f"Coverage: {self.metrics['coverage']:.2%}",
            "",
            "CONFIDENCE",
            f"  Mean: {self.metrics['mean_confidence']:.3f}",
            f"  Median: {self.metrics['median_confidence']:.3f}",
            f"  Std Dev: {self.metrics.get('std_confidence', 'N/A'):.3f}",
            f"  High-confidence (>0.6): {self.metrics.get('high_confidence_fraction', 0):.2%}",
        ]

        if "judge_agreement" in self.metrics:
            lines.extend([
                "",
                "JUDGE AGREEMENT (POC VALIDATION)",
                f"  Agreement: {self.metrics['judge_agreement']:.2%}",
                f"  Matches: {self.metrics['judge_agreement_pairs']}/{self.metrics['judge_total_pairs']}",
            ])

            if self.metrics.get("judge_errors"):
                lines.append(f"  Errors: {len(self.metrics['judge_errors'])}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def neuron_summary(self) -> pd.DataFrame:
        """Summary stats per neuron."""
        summary = self.df.groupby("neuron_id").agg({
            "weak_label": ["mean", "std", "min", "max"],
            "confidence": ["mean", "median"],
        }).round(3)

        summary.columns = ["_".join(col).strip() for col in summary.columns]
        return summary.sort_values("weak_label_mean", ascending=False)

    def confidence_distribution_summary(self) -> Dict:
        """Confidence distribution stats."""
        bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        counts, _ = pd.cut(self.df["confidence"], bins=bins, right=False, retbins=True)
        return {
            "0.0-0.2": int((counts == pd.Interval(0, 0.2, closed="left")).sum()),
            "0.2-0.4": int((counts == pd.Interval(0.2, 0.4, closed="left")).sum()),
            "0.4-0.6": int((counts == pd.Interval(0.4, 0.6, closed="left")).sum()),
            "0.6-0.8": int((counts == pd.Interval(0.6, 0.8, closed="left")).sum()),
            "0.8-1.0": int((counts == pd.Interval(0.8, 1.0, closed="left")).sum()),
        }

    def error_analysis(self) -> pd.DataFrame:
        """For POC: return disagreements with judge."""
        if "judge_errors" not in self.metrics or not self.metrics["judge_errors"]:
            return pd.DataFrame()

        errors = pd.DataFrame(self.metrics["judge_errors"])
        errors["disagreement"] = errors["disagreement"].round(3)
        return errors.sort_values("disagreement", ascending=False)

    def save_report(self, output_path: str):
        """Save full text report."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(self.summary_report())
            f.write("\n\n")
            f.write("PER-NEURON SUMMARY\n")
            f.write(self.neuron_summary().to_string())

            if "judge_agreement" in self.metrics and self.metrics["judge_errors"]:
                f.write("\n\nERROR ANALYSIS (Disagreements with Judge)\n")
                f.write(self.error_analysis().to_string())

        logger.info(f"Report saved to {output_path}")


def generate_full_report(
    weak_labels_csv: str,
    metrics_json: str,
    output_dir: str = "calibration/snorkel_reports"
):
    """
    Generate a complete metrics report from Snorkel output files.

    Args:
        weak_labels_csv: path to weak_labels.csv
        metrics_json: path to metrics.json
        output_dir: where to save the report
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Load outputs
    weak_labels_df = pd.read_csv(weak_labels_csv)
    with open(metrics_json) as f:
        metrics = json.load(f)

    # Generate report
    reporter = SnorkelMetricsReporter(weak_labels_df, metrics)

    # Print to console
    print(reporter.summary_report())

    # Save to file
    reporter.save_report(f"{output_dir}/snorkel_report.txt")

    # Save per-neuron summary
    neuron_summary = reporter.neuron_summary()
    neuron_summary.to_csv(f"{output_dir}/neuron_summary.csv")
    logger.info(f"Neuron summary saved to {output_dir}/neuron_summary.csv")

    # Save confidence distribution
    conf_dist = reporter.confidence_distribution_summary()
    with open(f"{output_dir}/confidence_distribution.json", "w") as f:
        json.dump(conf_dist, f, indent=2)
    logger.info(f"Confidence distribution saved to {output_dir}/confidence_distribution.json")

    # Save error analysis if available
    if "judge_errors" in metrics and metrics["judge_errors"]:
        errors_df = reporter.error_analysis()
        errors_df.to_csv(f"{output_dir}/judge_errors.csv", index=False)
        logger.info(f"Judge errors saved to {output_dir}/judge_errors.csv")


if __name__ == "__main__":
    # Example: generate report from POC output
    generate_full_report(
        weak_labels_csv="calibration/snorkel_output_poc/weak_labels.csv",
        metrics_json="calibration/snorkel_output_poc/metrics.json",
        output_dir="calibration/snorkel_reports_poc"
    )
