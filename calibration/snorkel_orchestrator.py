"""
calibration/snorkel_orchestrator.py — Phase 4 infrastructure: Snorkel orchestration.
OWNER: Chief Engineer.

Orchestrates weak labeling via deterministic LFs on a corpus of chats.
Designed to run on gold now (POC), scales to unlabeled corpus later.

Usage:
  POC (gold): orchestrator.run(gold_chats, mode="poc")
  Production (unlabeled): orchestrator.run(raw_chats, mode="production")
"""

import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

from contracts.schemas import CanonicalSession
from src.snorkel.labeling_functions import DETERMINISTIC_LFS, score_deterministic_neurons
from calibration.gold_loader import load_gold_corpus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WeakLabel:
    """One weak label output."""
    chat_id: str
    neuron_id: str
    score: float  # [0.0, 1.0]
    confidence: float  # distance from 0.5


class SnorkelOrchestrator:
    """
    Orchestrates weak labeling via deterministic LFs.

    Runs the 9 LFs on a corpus of chats, denoises outputs via aggregation,
    and produces weak labels suitable for SetFit training.
    """

    def __init__(self, gold_chats: List[Any] = None, judge_scores: Dict = None):
        """
        Args:
            gold_chats: list of GoldChat objects (for POC validation)
            judge_scores: dict {chat_id: {neuron_id: score}} (judge ground truth)
        """
        self.gold_chats = gold_chats or []
        self.judge_scores = judge_scores or {}
        self.lf_outputs = None
        self.weak_labels = None
        self.metrics = {}

    def run(self, chats: List[CanonicalSession], mode: str = "production") -> Tuple[pd.DataFrame, Dict]:
        """
        Run the Snorkel pipeline on a corpus.

        Args:
            chats: list of CanonicalSession objects
            mode: "poc" (validate on gold) or "production" (weak label only)

        Returns:
            (weak_labels_df, metrics_dict)
        """
        logger.info(f"Starting Snorkel orchestration ({mode} mode) on {len(chats)} chats")

        # Step 1: Apply all 9 LFs to each chat
        lf_outputs = self._apply_lfs(chats)
        self.lf_outputs = lf_outputs
        logger.info(f"Applied {len(DETERMINISTIC_LFS)} LFs to {len(chats)} chats")

        # Step 2: Aggregate LF outputs into weak labels
        weak_labels_df = self._aggregate_lf_outputs(chats, lf_outputs)
        self.weak_labels = weak_labels_df
        logger.info(f"Generated {len(weak_labels_df)} weak labels")

        # Step 3: Compute metrics
        self.metrics = self._compute_metrics(weak_labels_df, gold_mode=(mode == "poc"))
        logger.info(f"Metrics: coverage={self.metrics['coverage']:.2%}, "
                   f"mean_confidence={self.metrics['mean_confidence']:.3f}")

        return weak_labels_df, self.metrics

    def _apply_lfs(self, chats: List[CanonicalSession]) -> Dict[str, List[float]]:
        """
        Apply all 9 deterministic LFs to the corpus.

        Returns: {neuron_id: [scores_for_each_chat]}
        """
        lf_outputs = {neuron_id: [] for neuron_id in DETERMINISTIC_LFS.keys()}

        for i, chat in enumerate(chats):
            if i % 10 == 0:
                logger.info(f"  Processing chat {i+1}/{len(chats)}")

            # Score deterministic neurons (returns {neuron_id: score})
            scores = score_deterministic_neurons(chat)

            for neuron_id, score in scores.items():
                lf_outputs[neuron_id].append(score)

        return lf_outputs

    def _aggregate_lf_outputs(
        self, chats: List[CanonicalSession], lf_outputs: Dict[str, List[float]]
    ) -> pd.DataFrame:
        """
        Aggregate LF outputs into weak labels.

        Each LF gives a [0, 1] score per chat. We aggregate by averaging
        (deterministic LFs are independent and reliable).

        Returns: DataFrame with columns [chat_id, neuron_id, weak_label, confidence]
        """
        weak_labels = []

        for chat_idx, chat in enumerate(chats):
            chat_id = chat.session_id

            for neuron_id, scores in lf_outputs.items():
                if chat_idx >= len(scores):
                    continue

                # Average score across this LF
                score = scores[chat_idx]

                # Confidence: distance from 0.5 (higher = more confident)
                confidence = abs(score - 0.5) * 2.0

                weak_labels.append(
                    WeakLabel(
                        chat_id=chat_id,
                        neuron_id=neuron_id,
                        score=score,
                        confidence=confidence,
                    )
                )

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                "chat_id": wl.chat_id,
                "neuron_id": wl.neuron_id,
                "weak_label": wl.score,
                "confidence": wl.confidence,
            }
            for wl in weak_labels
        ])

        return df

    def _compute_metrics(self, weak_labels_df: pd.DataFrame, gold_mode: bool = False) -> Dict:
        """
        Compute metrics on the weak labels.

        If gold_mode=True, compare against judge ground truth (POC validation).
        """
        metrics = {}

        # Coverage: fraction of (chat, neuron) pairs with a label
        metrics["total_pairs"] = len(weak_labels_df)
        metrics["labeled_pairs"] = len(weak_labels_df)  # All deterministic LFs always fire
        metrics["coverage"] = 1.0

        # Confidence: distance from 0.5 (higher = more confident)
        metrics["mean_confidence"] = weak_labels_df["confidence"].mean()
        metrics["median_confidence"] = weak_labels_df["confidence"].median()
        metrics["std_confidence"] = weak_labels_df["confidence"].std()

        # High-confidence labels: > 0.6
        metrics["high_confidence_pairs"] = (weak_labels_df["confidence"] > 0.6).sum()
        metrics["high_confidence_fraction"] = metrics["high_confidence_pairs"] / metrics["total_pairs"]

        # If gold mode, compare weak labels against judge
        if gold_mode and self.judge_scores:
            agreement = self._compare_to_judge(weak_labels_df)
            metrics.update(agreement)

        return metrics

    def _compare_to_judge(self, weak_labels_df: pd.DataFrame) -> Dict:
        """
        Compare weak labels to judge ground truth (POC validation).

        Judge scores are at the dimension level (e.g., "AL": 0.55).
        Neuron scores are at the neuron level (e.g., "AL-01": score).
        Aggregate LF scores to dimension level by taking the mean, then compare.

        Returns: {judge_agreement, judge_agreement_pairs, judge_total_pairs, judge_errors}
        """
        # Aggregate LF outputs to dimension level
        weak_labels_df["dimension"] = weak_labels_df["neuron_id"].str.extract(r"([A-Z]+)")[0]

        matches = 0
        total = 0
        errors = []

        for chat_id in weak_labels_df["chat_id"].unique():
            if chat_id not in self.judge_scores:
                continue

            chat_data = weak_labels_df[weak_labels_df["chat_id"] == chat_id]

            for dimension in chat_data["dimension"].unique():
                if dimension not in self.judge_scores[chat_id]:
                    continue

                judge_score = self.judge_scores[chat_id][dimension]
                if judge_score is None:
                    continue

                # Aggregate LF scores for this dimension
                dim_scores = chat_data[chat_data["dimension"] == dimension]["weak_label"]
                weak_score = dim_scores.mean()

                # Convert to binary: 0 if < 0.5, 1 if >= 0.5
                judge_binary = 1 if judge_score >= 0.5 else 0
                weak_binary = 1 if weak_score >= 0.5 else 0

                if judge_binary == weak_binary:
                    matches += 1
                else:
                    errors.append({
                        "chat_id": chat_id,
                        "dimension": dimension,
                        "weak_score": float(weak_score),
                        "judge_score": float(judge_score),
                        "disagreement": abs(weak_score - judge_score),
                    })

                total += 1

        agreement = matches / total if total > 0 else 0.0

        return {
            "judge_agreement": agreement,
            "judge_agreement_pairs": matches,
            "judge_total_pairs": total,
            "judge_errors": errors,
        }

    def save_weak_labels(self, df: pd.DataFrame, output_path: str):
        """Save weak labels to CSV for SetFit training."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f"Weak labels saved to {output_path}")

    def save_metrics(self, output_path: str):
        """Save metrics to JSON."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.metrics, f, indent=2, default=str)
        logger.info(f"Metrics saved to {output_path}")


def run_poc_on_gold() -> Dict:
    """
    POC: Run Snorkel on the 26 gold chats, validate against judge labels.

    Returns: metrics dict
    """
    logger.info("Loading gold corpus...")
    gold_corpus = load_gold_corpus()
    chats = [gc.session for gc in gold_corpus]

    # Build judge_scores dict from gold targets
    judge_scores = {}
    for gc in gold_corpus:
        judge_scores[gc.session.session_id] = {
            dim.value: gc.targets[dim] for dim in gc.targets if gc.targets[dim] is not None
        }

    logger.info(f"Loaded {len(chats)} gold chats")

    # Run orchestrator
    orch = SnorkelOrchestrator(gold_chats=gold_corpus, judge_scores=judge_scores)
    weak_labels, metrics = orch.run(chats, mode="poc")

    # Save outputs
    output_dir = "calibration/snorkel_output_poc"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    orch.save_weak_labels(weak_labels, f"{output_dir}/weak_labels.csv")
    orch.save_metrics(f"{output_dir}/metrics.json")

    return metrics


if __name__ == "__main__":
    metrics = run_poc_on_gold()

    print("\n" + "=" * 60)
    print("✅ SNORKEL POC COMPLETE")
    print("=" * 60)
    print(f"Coverage: {metrics.get('coverage', 'N/A'):.2%}")
    print(f"Mean confidence: {metrics.get('mean_confidence', 'N/A'):.3f}")
    print(f"High-confidence pairs: {metrics.get('high_confidence_fraction', 'N/A'):.2%}")
    if "judge_agreement" in metrics:
        print(f"Judge agreement: {metrics.get('judge_agreement', 'N/A'):.2%}")
        print(f"  ({metrics['judge_agreement_pairs']}/{metrics['judge_total_pairs']} pairs)")
    print(f"Output: calibration/snorkel_output_poc/")
