"""
src/trait/reliance_metrics.py — appropriate-reliance metric extractor (v3 P11).
OWNER: Chief Engineer. (Brief §P11; spec V12 / §E1.)

Borrowed-and-validated import (spec V12): the human–AI reliance literature has
validated constructs; SAF imports them. They are VALIDATED in their source field
but only DESIGNED for SAF (spec status, SpecDelta line 313) — not yet validated
here.

  reliance_metrics(session) -> RelianceMetrics
    weight_of_advice:     float | None   # continuous shift toward AI advice (PROXY)
    switch_fraction:      float | None   # answer-adoption rate over engaged episodes
    appropriate_reliance: AppropriateReliance | None   # ALWAYS None on a raw chat
    derivable:            bool
    note:                 str

── What is and isn't derivable from a raw transcript ────────────────────────
* `switch_fraction` and `weight_of_advice` are derivable as BEHAVIORAL PROXIES
  from the intent tags (ACCEPT_FLAT = adopted the AI's output, OVERRIDE = held /
  changed it, VERIFY = checked it).
* `weight_of_advice` is a labeled proxy, NOT the numeric judge-advisor WoA
  (|final−initial| / |advice−initial|). That formula needs a (human initial
  estimate, AI advice, human final estimate) triple on a common scale, which a
  raw chat does not contain (decision STOP-A, approved 2026-06-19: emit the
  documented proxy). True WoA is reserved for the judge-advisor tasklet design.
* `appropriate_reliance` (over-/under-reliance) requires knowing whether the AI's
  advice was actually CORRECT — ground truth that is structurally absent from any
  raw transcript. It is therefore ALWAYS None here, with `derivable` reflecting
  only the behavioral metrics (spec §P11; SpecDelta §E2 point 1).

── Definitions (documented so the proxy is auditable) ───────────────────────
Over engaged advice episodes (an AI turn followed by a human turn tagged
ACCEPT_FLAT, OVERRIDE, or VERIFY):
    A = #ACCEPT_FLAT (adopt)   H = #OVERRIDE (hold)   V = #VERIFY   E = #engaged
    weight_of_advice = A / (A + H)   if A + H > 0 else None   (adopt vs hold lean)
    switch_fraction  = A / E         if E > 0     else None   (adoption rate)
The two differ by denominator (WoA excludes pure-verify episodes; switch includes
them) so they are not the same number.

── Standing rule preserved ──────────────────────────────────────────────────
The self-rating widget feeds ONLY the metacognitive calibration gap, never these
behavioral scores. This extractor reads behaviour (tags), never self-ratings.

── Neuron wiring (brief §P11 → DISCREPANCY D-021, OPEN) ──────────────────────
The proposed feed of the behavioral reliance signal into EC is surfaced for human
review (D-021), NOT wired. Proposed target: EC-11 (calibrated asymmetric
skepticism) — the on-construct, currently-unfed neuron — explicitly NOT EC-01, to
avoid double-counting the P5 graesser→EC-01 edge and evidence.py verification.
appropriate_reliance, when it later becomes derivable, feeds the calibration gap,
not a behavioral neuron score.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from contracts.schemas import CanonicalSession, IntentTag
from src.trait.tagger import tag_turns

#: intent tags that mark a human turn as a reliance response to AI advice
_ADOPT = IntentTag.ACCEPT_FLAT
_HOLD = IntentTag.OVERRIDE
_VERIFY = IntentTag.VERIFY
_ENGAGED = frozenset({_ADOPT, _HOLD, _VERIFY})

#: proposed EC target for the behavioral reliance signal — REVIEW ONLY (D-021),
#: NOT wired. EC-11 = calibrated asymmetric skepticism (the appropriate-reliance
#: construct). EC-01 is deliberately excluded (P5 graesser→EC-01 already lands
#: there; reusing it would double-count verification behaviour).
PROPOSED_EC_TARGET = ("EC-11",)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AppropriateReliance(_Frozen):
    """Two-dimensional appropriate-reliance construct (over-/under-reliance).
    Only constructible when AI-advice correctness ground truth exists."""

    over: float = Field(ge=0.0, le=1.0)
    under: float = Field(ge=0.0, le=1.0)


class RelianceMetrics(_Frozen):
    weight_of_advice: float | None = Field(default=None, ge=0.0, le=1.0)
    switch_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    appropriate_reliance: AppropriateReliance | None = None
    derivable: bool = False
    note: str = ""
    #: audit counts (absent ≠ zero: the denominators behind the proxies)
    n_engaged_episodes: int = Field(ge=0, default=0)
    n_adopt: int = Field(ge=0, default=0)
    n_hold: int = Field(ge=0, default=0)
    n_verify: int = Field(ge=0, default=0)


_GROUND_TRUTH_NOTE = (
    "appropriate_reliance (over-/under-reliance) requires ground-truth correctness "
    "of the AI's advice, which a raw transcript does not contain; it needs the "
    "judge-advisor tasklet design (spec V12/E1)."
)


def reliance_metrics(session: CanonicalSession) -> RelianceMetrics:
    """Behavioral reliance proxies from the transcript; appropriate_reliance gated.

    Deterministic: derives from the intent tags only (no judge, no self-ratings).
    """
    tags_by_turn = {tt.turn_index: set(tt.tags) for tt in tag_turns(session)}
    roles = {t.index: t.role for t in session.turns}

    adopt = hold = verify = engaged = 0
    for turn in session.turns:
        if turn.role != "human":
            continue
        # an advice episode: a human turn that directly follows an AI turn
        if roles.get(turn.index - 1) != "ai":
            continue
        tt = tags_by_turn.get(turn.index, set())
        if not (tt & _ENGAGED):
            continue
        engaged += 1
        if _ADOPT in tt:
            adopt += 1
        if _HOLD in tt:
            hold += 1
        if _VERIFY in tt:
            verify += 1

    if engaged == 0:
        return RelianceMetrics(
            weight_of_advice=None,
            switch_fraction=None,
            appropriate_reliance=None,
            derivable=False,
            note=(
                "no AI-advice episodes the human engaged with (adopt/override/verify); "
                "reliance is not observable in this transcript. " + _GROUND_TRUTH_NOTE
            ),
        )

    woa = round(adopt / (adopt + hold), 6) if (adopt + hold) > 0 else None
    switch = round(adopt / engaged, 6)
    return RelianceMetrics(
        weight_of_advice=woa,
        switch_fraction=switch,
        appropriate_reliance=None,
        derivable=True,
        note=(
            "weight_of_advice and switch_fraction are behavioral PROXIES from "
            "adopt/override/verify intent tags, not the numeric judge-advisor WoA. "
            + _GROUND_TRUTH_NOTE
        ),
        n_engaged_episodes=engaged,
        n_adopt=adopt,
        n_hold=hold,
        n_verify=verify,
    )
