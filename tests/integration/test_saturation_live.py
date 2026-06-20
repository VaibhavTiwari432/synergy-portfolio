"""v3 P1 live gate — saturation fires on a REAL gold chat. OWNER: Chief Engineer.

This is the gate that proves the saturation path is live, not just unit-correct.
It runs a real gold transcript (gc-001, chatgpt → no judge-family conflict, 9
human turns → n_eff clause genuinely met by the data) through the full scoring
pipeline. The judge is non-deterministic, so its per-dimension scores are
injected (the standing test convention) — but the SESSION, the turn count, the
n_eff, and the flag set are all real, derived from the transcript and pipeline.

It asserts CS saturates with Censored(direction="high", bound=tau_CS) once all
four clauses hold, and — on the same real chat — that EC does NOT saturate even
at a maximal score, because EC carries the standing low-calibration flag (#19).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.schemas import Censored, Dimension, ScoreStatus
from src.aggregate.saturation import TAU_CEILING
from src.api.pipeline import score_session_with_artifacts
from src.ingestion.canonical import ingest
from src.trait.judge.client import JudgeClient

GOLD = Path(__file__).resolve().parents[2] / "data" / "gold" / "chats" / "gc-001.json"


def _ceiling_judge() -> JudgeClient:
    """A judge that returns a near-ceiling CS score and a maximal EC score.

    CS clears every clause (score ≥ tau, high confidence); EC is maximal too but
    must be blocked by its standing flag. Everything else sits mid-scale.
    """
    entry = {"score": 0.5, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["CS"] = {"score": 0.97, "confidence": 0.92, "evidence_turns": [0], "tom_tag": None}
    data["EC"] = {"score": 0.99, "confidence": 0.99, "evidence_turns": [0], "tom_tag": None}
    data["ES"]["score"] = None  # ES has no events here (real-world common)
    payload = json.dumps(data)
    return JudgeClient(generate=lambda s, u: payload, fallback=None, sleep=lambda _: None)


@pytest.fixture(scope="module")
def gold_session():
    raw = json.loads(GOLD.read_text(encoding="utf-8"))
    return ingest(raw), raw


def test_cs_saturates_on_real_gold_chat(gold_session):
    session, raw = gold_session
    n_human = sum(1 for t in raw["turns"] if t["role"] == "user")
    assert n_human == 9  # real n_eff, comfortably ≥ SATURATION_MIN_NEFF (5)

    run = score_session_with_artifacts(session, judge=_ceiling_judge())

    # the judge family did not conflict (chatgpt partner, google judge)
    assert run.judge_run["judge_family_conflict"] is False

    # CS hit all four clauses → emitted as a censored ceiling, never a point value
    cs = run.raw_profile[Dimension.CS]
    assert cs.status == ScoreStatus.MEASUREMENT_SATURATED
    assert cs.value is None
    assert cs.censored == Censored(direction="high", bound=TAU_CEILING[Dimension.CS])
    assert cs.censored.bound == 0.93
    assert cs.n_eff == float(n_human)  # the n_eff clause was met by the real chat
    assert cs.flags == []  # no standing flag stood in the way


def test_ec_does_not_saturate_despite_max_score(gold_session):
    # same real chat, EC scored 0.99 — but EC carries the standing low-calibration
    # flag (#19), so the conjunctive guard blocks it. Correct behavior, not a bug.
    session, _ = gold_session
    run = score_session_with_artifacts(session, judge=_ceiling_judge())

    ec = run.raw_profile[Dimension.EC]
    assert "ec_low_calibration_confidence" in ec.flags
    assert ec.status != ScoreStatus.MEASUREMENT_SATURATED
    assert ec.censored is None
