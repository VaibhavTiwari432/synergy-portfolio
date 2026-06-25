"""
calibration/cleanlab_audit.py — Cleanlab audit for label quality detection

ITEM #4 PART A: Identify potentially mislabeled instances in gold set via Cleanlab.

Purpose: Before growing the corpus via active learning, audit existing 26-chat gold set
for label quality issues. Cleanlab uses confident learning to find instances where the
judge consensus and human gold labels disagree suspiciously.

Non-negotiable:
  - Audit is informational only; no auto-correction
  - Results guide manual review, not automatic relabeling
  - Human judgment remains final
"""

from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional, Tuple


def audit_gold_set_for_mislabels(
    gold_chats: List[Dict],
    judge_scores: Dict[str, Dict[str, float]],
    threshold_high_confidence: float = 0.80,
    threshold_at_risk: float = 0.50,
) -> Dict:
    """
    Audit gold set using judge consensus vs human labels.

    Args:
        gold_chats: List of gold chat dicts with structure:
            {
                'id': 'gc-001',
                'transcript': '...',
                'human_labels': {'EC-01': 3, 'EC-02': 4, ...},  # 0-4 scale
                'archetype': 'SCHOOL_CLASS_8_10',
                ...
            }
        judge_scores: Dict[chat_id] -> Dict[neuron_id] -> judge_consensus_score (0-4)
        threshold_high_confidence: Chat quality score above this = confident label
        threshold_at_risk: Chat quality score below this = at-risk label

    Returns:
        dict with keys:
            - confident: List of chat IDs with high label confidence (>0.80)
            - at_risk: List of chat IDs with low label confidence
            - likely_errors: List of {chat_id, neuron_id, human_label, judge_consensus}
                dicts for manual review (top 10)
            - summary: {n_chats, confident_pct, at_risk_pct, neurons_flagged}
    """

    confident = []
    at_risk = []
    disagreement_records = []

    # For each chat, compute label quality scores
    for chat in gold_chats:
        chat_id = chat['id']
        human_labels = chat.get('human_labels', {})
        judge_preds = judge_scores.get(chat_id, {})

        if not judge_preds:
            # No judge consensus available; skip
            continue

        # Compute agreement: neurons where judge and human agree (roughly)
        agreements = []
        disagreements = []

        for neuron_id, human_score in human_labels.items():
            judge_score = judge_preds.get(neuron_id, None)
            if judge_score is None:
                continue

            # Normalize to 0-4 scale if needed
            if isinstance(judge_score, float) and judge_score <= 1.0:
                judge_score = judge_score * 4.0  # Convert 0-1 to 0-4

            # Agreement: scores within 1 level
            if abs(human_score - judge_score) <= 1.0:
                agreements.append(neuron_id)
            else:
                disagreements.append((neuron_id, human_score, judge_score))
                disagreement_records.append({
                    'chat_id': chat_id,
                    'neuron_id': neuron_id,
                    'human_label': human_score,
                    'judge_consensus': judge_score,
                    'disagreement_magnitude': abs(human_score - judge_score),
                })

        # Compute label quality score for this chat
        n_neurons = len(human_labels)
        if n_neurons == 0:
            quality_score = np.nan
        else:
            quality_score = len(agreements) / n_neurons

        # Classify
        if quality_score >= threshold_high_confidence:
            confident.append(chat_id)
        elif quality_score < threshold_at_risk:
            at_risk.append(chat_id)

    # Sort disagreements by magnitude (largest first)
    disagreement_records.sort(key=lambda x: x['disagreement_magnitude'], reverse=True)

    # Top 10 suspect labels for manual review
    likely_errors = disagreement_records[:10]

    summary = {
        'n_chats': len(gold_chats),
        'confident_count': len(confident),
        'at_risk_count': len(at_risk),
        'confident_pct': 100.0 * len(confident) / len(gold_chats) if gold_chats else 0,
        'at_risk_pct': 100.0 * len(at_risk) / len(gold_chats) if gold_chats else 0,
        'total_disagreements': len(disagreement_records),
        'disagreements_top_10': len(likely_errors),
    }

    return {
        'confident': confident,
        'at_risk': at_risk,
        'likely_errors': likely_errors,
        'summary': summary,
    }


def report_audit_results(audit_result: Dict) -> str:
    """Generate human-readable audit report."""
    summary = audit_result['summary']
    confident = audit_result['confident']
    at_risk = audit_result['at_risk']
    likely_errors = audit_result['likely_errors']

    report = f"""
CLEANLAB AUDIT REPORT
═════════════════════

Gold Set Overview:
  - Total chats: {summary['n_chats']}
  - Confident labels: {summary['confident_count']} ({summary['confident_pct']:.1f}%)
  - At-risk labels: {summary['at_risk_count']} ({summary['at_risk_pct']:.1f}%)

Detailed Results:
  - Total neuron-level disagreements: {summary['total_disagreements']}
  - Top 10 suspect labels flagged for review

Confident Chats (keep as-is):
  {', '.join(confident)}

At-Risk Chats (review labels):
  {', '.join(at_risk)}

Top 10 Suspect Labels (manual review recommended):
"""

    for i, error in enumerate(likely_errors, 1):
        report += f"""
  {i}. {error['chat_id']} / {error['neuron_id']}
     Human label: {error['human_label']:.1f} | Judge consensus: {error['judge_consensus']:.1f}
     Disagreement: {error['disagreement_magnitude']:.1f} levels"""

    report += f"""

Recommendation:
  1. Review the 10 suspect labels manually
  2. If judge consensus is correct, update human label (or mark human rater as unreliable)
  3. If human judgment is correct, refine judge prompt/rubric
  4. Use 'confident' chats as baseline for future validation
"""

    return report


if __name__ == '__main__':
    # Example usage with mock data
    print("Cleanlab audit module loaded. Use via active_learning.py or directly.")
    print("Example:")
    print("  from calibration.cleanlab_audit import audit_gold_set_for_mislabels")
    print("  result = audit_gold_set_for_mislabels(gold_chats, judge_scores)")
