"""
calibration/dawid_skene.py — Dawid–Skene EM de-biasing for the LLM Judge.
OWNER: Chief Engineer.

PURPOSE: the judge has a documented bias toward elaborated-over-terse responses
(verbose users score higher for the same underlying behaviour). This module
estimates a per-dimension bias from the dual-annotation gold set so MAE can be
reported corrected alongside raw. The OUTPUT is a calibration-reporting number —
it is NOT wired into any live score or DimensionScore value (R2; non-negotiable
#10: self-ratings/annotations never used raw to move a behavioural score).

DATA-GATED (v3/v3.1 addendum #3): the full Dawid–Skene EM estimates a per-rater
confusion matrix + latent true label, which requires ≥2 annotators per chat per
dimension. The current gold set is single-human-annotation, so that estimator
cannot run. This module raises DataGatedError until the dual-annotation corpus
exists. Building the interface now and raising the gate is correct: silently
skipping (or fabricating a bias from single annotations) would produce misleading
calibration numbers. The placeholder bias below is a per-dimension annotator
spread, NOT the EM confusion-matrix estimate — it activates only once the gate
passes, and the real EM replaces it when the data lands.
"""

from __future__ import annotations

from collections import defaultdict

#: A dimension needs at least this many multi-annotated chats before any bias
#: estimate is reported for it. Below this, the dimension is DATA_GATED.
MIN_MULTI_ANNOTATED_CHATS = 3

#: A chat counts toward a dimension's multi-annotation only with at least this
#: many distinct annotators.
MIN_ANNOTATORS_PER_CHAT = 2


class DataGatedError(RuntimeError):
    """Raised when no dimension meets the dual-annotation requirement.

    Load-bearing: never caught-and-defaulted into a fabricated bias. The absence
    of dual annotation is reported, not papered over (#3 / #10)."""


def run_dawid_skene(annotations: list[dict]) -> dict:
    """Estimate per-dimension judge bias from dual-annotated gold data.

    annotations: list of ``{chat_id, dimension, annotator_id, score}``.
    Returns ``{dimension: {"bias": float | None, "n_annotators": int,
    "n_multi_annotated": int, "status": "OK" | "DATA_GATED"}}``.

    Raises DataGatedError if NO dimension has ≥ MIN_ANNOTATORS_PER_CHAT annotators
    on ≥ MIN_MULTI_ANNOTATED_CHATS chats. The returned bias is calibration-only
    and NEVER conditions a DimensionScore (#2, #10).
    """
    by_dim_chat: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in annotations:
        by_dim_chat[row["dimension"]][row["chat_id"]].append(
            (row["annotator_id"], row["score"])
        )

    results: dict[str, dict] = {}
    any_valid = False
    for dim, chats in by_dim_chat.items():
        # distinct annotators per chat (a rater annotating twice is still one)
        multi = {
            cid: anns
            for cid, anns in chats.items()
            if len({a for a, _ in anns}) >= MIN_ANNOTATORS_PER_CHAT
        }
        n_multi = len(multi)
        max_annotators = max(
            (len({a for a, _ in anns}) for anns in chats.values()), default=0
        )
        if n_multi < MIN_MULTI_ANNOTATED_CHATS:
            results[dim] = {
                "bias": None,
                "n_annotators": max_annotators,
                "n_multi_annotated": n_multi,
                "status": "DATA_GATED",
            }
            continue

        any_valid = True
        # Placeholder estimate (the real EM confusion-matrix estimate lands with
        # the data): per-dimension mean inter-annotator spread on dual-annotated
        # chats. Reported as the bias magnitude until the EM replaces it.
        spreads = [
            max(s for _, s in anns) - min(s for _, s in anns) for anns in multi.values()
        ]
        results[dim] = {
            "bias": sum(spreads) / len(spreads) if spreads else None,
            "n_annotators": max_annotators,
            "n_multi_annotated": n_multi,
            "status": "OK",
        }

    if not any_valid:
        raise DataGatedError(
            f"Dawid–Skene requires ≥{MIN_ANNOTATORS_PER_CHAT} annotators on "
            f"≥{MIN_MULTI_ANNOTATED_CHATS} chats per dimension. The current gold "
            "set is single-annotation. This gate is load-bearing — do not "
            "fabricate bias estimates."
        )
    return results
