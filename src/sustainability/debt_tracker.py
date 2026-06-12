"""
src/sustainability/debt_tracker.py — Ŝ_human, the embedded estimator.
OWNER: Chief Engineer. (Brief §3.9 + §7 — read §7 before touching this.)

Resolved formula (both v1 bugs fixed):

    Ŝ_human = (r_auto − r_steer) × T_steered_out

- Bug 1 (unobservable counterfactual) is solved by the within-conversation
  baseline: A-turns ("continue/ok/go on") expose the model's intrinsic
  autonomous redundancy r_auto. No counterfactual double-run.
- Bug 2 (κ double-counts ability) is solved by dropping κ entirely. Any future
  credibility weighting is a separate normative parameter via ADR.
- Cache multiplier: linear (1.0) first.

Redundancy here is the LINEAR-FIRST implementation: lexical 4-gram overlap of
an AI turn against previously established AI content. The semantic
(sentence-transformers cosine) upgrade swaps in behind redundancy_of() without
changing this module's contract. Degenerate partitions (no A-turns or no
S-turns) → value None, NOT_APPLICABLE — the estimator declines rather than
fabricates (non-negotiable #12). Falsifiability: must correlate with the 48h
probe at r > 0.3 or be revised (contracts/probe_schema.yaml).
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, Rung, ScoreStatus, SHumanHat

#: autopilot continuations — the A-turn vocabulary (whole-turn match)
_A_TURN_RE = re.compile(
    r"^\s*(ok(ay)?|yes|yeah|sure|continue|go on|next|more|proceed|keep going|"
    r"sounds good|thanks?|great|cool|hmm+|got it|nice|do it|please continue)"
    r"[\s.!,]*$",
    re.IGNORECASE,
)

#: minimum tokens for a human turn to be a steering turn candidate regardless
#: of phrasing (anything substantive that is not an autopilot phrase steers)
_NGRAM = 4


def is_a_turn(text: str) -> bool:
    """A-turn: a bare continuation with no constraint, correction, or stop rule."""
    return bool(_A_TURN_RE.match(text.strip()))


def _ngrams(text: str, n: int = _NGRAM) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def _token_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def redundancy_of(text: str, established: set[tuple[str, ...]]) -> float | None:
    """Fraction of this turn's 4-grams already present in established content.
    None when the turn is too short to carry any 4-gram (no evidence)."""
    grams = _ngrams(text)
    if not grams:
        return None
    return len(grams & established) / len(grams)


def s_human_hat(session: CanonicalSession) -> SHumanHat:
    """Compute Ŝ_human from the A/S partition of human turns.

    Each AI turn is attributed to the regime of the human turn that elicited
    it (the closest preceding human turn). Redundancy is measured against the
    AI content established BEFORE that turn — order matters, the log keeps it.
    """
    established: set[tuple[str, ...]] = set()
    current_regime: str | None = None  # "auto" | "steer"

    auto_redundancies: list[float] = []
    steer_redundancies: list[float] = []
    steered_tokens = 0

    for turn in session.turns:
        if turn.role == "human":
            current_regime = "auto" if is_a_turn(turn.text) else "steer"
            continue
        # AI turn: attribute to the eliciting regime
        if current_regime is None:
            continue  # AI opened the session; no human elicitation to attribute
        r = redundancy_of(turn.text, established)
        if r is not None:
            if current_regime == "auto":
                auto_redundancies.append(r)
            else:
                steer_redundancies.append(r)
        if current_regime == "steer":
            steered_tokens += _token_count(turn.text)
        established |= _ngrams(turn.text)

    if not auto_redundancies or not steer_redundancies:
        return SHumanHat(
            value=None,
            r_auto=(sum(auto_redundancies) / len(auto_redundancies)) if auto_redundancies else None,
            r_steer=(sum(steer_redundancies) / len(steer_redundancies)) if steer_redundancies else None,
            t_steered_out=float(steered_tokens) if steer_redundancies else None,
            status=ScoreStatus.NOT_APPLICABLE,
            rung=Rung.DESIGNED,
        )

    r_auto = sum(auto_redundancies) / len(auto_redundancies)
    r_steer = sum(steer_redundancies) / len(steer_redundancies)
    value = (r_auto - r_steer) * steered_tokens  # cache multiplier linear (×1.0)

    return SHumanHat(
        value=value,
        r_auto=r_auto,
        r_steer=r_steer,
        t_steered_out=float(steered_tokens),
        cache_multiplier=1.0,
        status=ScoreStatus.OK,
        rung=Rung.MEASURABLE,
    )
