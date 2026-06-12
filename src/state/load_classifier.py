"""
src/state/load_classifier.py — per-turn cognitive-load proxy (INTERFACES.md §2.1).
Leaf module: imports ONLY from contracts/. Deterministic.

One LoadLabel per HUMAN turn: LOW_LOAD / HIGH_ICL / HIGH_ECL / FATIGUE, from
prompt-length trajectory, vocab-complexity delta, and fragmentation — all
RELATIVE to the session's own baseline, never absolute thresholds
(non-negotiable #11). Sessions with fewer than 3 human turns have no usable
baseline; every turn reads LOW_LOAD (the weakest claim, not a fabricated one).

Label intuition:
- HIGH_ICL  — productive intrinsic load: unusually long/complex prompt for
  this user (deep engagement with hard material)
- HIGH_ECL  — extraneous load: fragmented, confused, repair-heavy prompting
- FATIGUE   — late-session effort collapse: shrinking prompts + fragmentation
- LOW_LOAD  — within this session's normal band
Priority: FATIGUE > HIGH_ECL > HIGH_ICL > LOW_LOAD.
"""

from __future__ import annotations

import re
from statistics import mean, pstdev

from contracts.schemas import CanonicalSession, LoadLabel

#: relative deviation threshold in session-σ units (≈ the spec's ~1.5 SD,
#: applied to within-session variation)
Z_THRESHOLD = 1.5

_CONFUSION_RE = re.compile(
    r"\bi('?m| am) (confused|lost|not sure i understand)\b|\bi don'?t (understand|get it)\b"
    r"|\bwhat do you mean\b|\bhuh\b|\?\?+|\bwait[,. ]|\bthis (isn'?t|is not) working\b",
    re.IGNORECASE,
)


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text)


def _vocab_complexity(text: str) -> float:
    words = _words(text)
    return mean(len(w) for w in words) if words else 0.0


def _fragmentation(text: str) -> float:
    """Share of fragment sentences (<4 words) + confusion markers."""
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]
    if not sentences:
        return 0.0
    fragments = sum(1 for s in sentences if len(_words(s)) < 4)
    score = fragments / len(sentences)
    if _CONFUSION_RE.search(text):
        score += 0.5
    return min(1.0, score)


def _z(value: float, baseline: list[float]) -> float:
    sd = pstdev(baseline)
    if sd == 0:
        return 0.0
    return (value - mean(baseline)) / sd


def classify_load(session: CanonicalSession) -> list[LoadLabel]:
    human_texts = [t.text for t in session.turns if t.role == "human"]
    n = len(human_texts)
    if n < 3:
        return [LoadLabel.LOW_LOAD] * n  # no within-session baseline yet

    lengths = [float(len(_words(t))) for t in human_texts]
    complexities = [_vocab_complexity(t) for t in human_texts]
    fragmentations = [_fragmentation(t) for t in human_texts]

    labels: list[LoadLabel] = []
    for i, text in enumerate(human_texts):
        length_z = _z(lengths[i], lengths)
        complexity_z = _z(complexities[i], complexities)
        fragmentation_z = _z(fragmentations[i], fragmentations)
        late = i >= n / 2

        if late and length_z < -Z_THRESHOLD and fragmentation_z > 0:
            labels.append(LoadLabel.FATIGUE)
        elif fragmentation_z > Z_THRESHOLD or _CONFUSION_RE.search(text):
            labels.append(LoadLabel.HIGH_ECL)
        elif length_z > Z_THRESHOLD or complexity_z > Z_THRESHOLD:
            labels.append(LoadLabel.HIGH_ICL)
        else:
            labels.append(LoadLabel.LOW_LOAD)
    return labels
