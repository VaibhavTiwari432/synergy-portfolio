"""v3 P11 — appropriate-reliance metric extractor (brief §P11; spec V12 / §E1).
OWNER: Chief Engineer.

Acceptance (spec §P11): on a fixture where the human revises toward AI advice,
weight_of_advice and switch_fraction are computed; appropriate_reliance returns
None with a note when correctness ground truth is absent.

Design decisions in force (approved 2026-06-19): weight_of_advice is a labeled
behavioral PROXY (STOP-A); EC wiring is gated on review (D-021 — NOT wired).
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, PartnerModel, Turn
from src.trait.reliance_metrics import (
    EC_EVIDENCE_TARGET,
    RelianceMetrics,
    reliance_evidence_rows,
    reliance_metrics,
)


def _session(human_after_ai: list[str], *, seed: str = "let's build a parser") -> CanonicalSession:
    """Build an alternating session; each string is a human turn that FOLLOWS an
    AI turn (a candidate advice episode). A leading seed human turn (index 0) has
    no preceding AI and is never an episode."""
    turns: list[Turn] = [Turn(index=0, role="human", text=seed)]
    for h in human_after_ai:
        turns.append(Turn(index=len(turns), role="ai", text="a substantive assistant reply with a claim."))
        turns.append(Turn(index=len(turns), role="human", text=h))
    # close with a trailing AI turn so the shape is natural (optional)
    turns.append(Turn(index=len(turns), role="ai", text="ok."))
    return CanonicalSession(
        session_id="rl-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


# ── acceptance: revision-toward-AI fixture computes WoA + switch ────────────


def test_revision_toward_ai_computes_woa_and_switch():
    # two adopt episodes (ACCEPT_FLAT) → strong lean toward AI
    r = reliance_metrics(_session(["sounds good", "perfect"]))
    assert r.derivable is True
    assert r.weight_of_advice == 1.0      # adopt / (adopt + hold) = 2/2
    assert r.switch_fraction == 1.0       # adopt / engaged = 2/2
    assert r.n_adopt == 2 and r.n_hold == 0 and r.n_engaged_episodes == 2


def test_mixed_adopt_hold_verify_proxies_are_distinct():
    r = reliance_metrics(_session([
        "sounds good",                       # ACCEPT_FLAT → adopt
        "no, use recursion instead",         # OVERRIDE   → hold
        "are you sure that's correct?",      # VERIFY     → verify
    ]))
    assert r.n_adopt == 1 and r.n_hold == 1 and r.n_verify == 1
    assert r.n_engaged_episodes == 3
    assert r.weight_of_advice == 0.5        # 1 / (1 + 1) — verify excluded
    assert round(r.switch_fraction, 3) == 0.333  # 1 / 3 — verify included
    # the two proxies differ by denominator → not the same number
    assert r.weight_of_advice != r.switch_fraction


# ── appropriate_reliance is data-gated (no ground truth in a raw chat) ──────


def test_appropriate_reliance_is_always_none_with_ground_truth_note():
    r = reliance_metrics(_session(["sounds good"]))
    assert r.appropriate_reliance is None
    assert "ground-truth correctness" in r.note
    assert "judge-advisor" in r.note


# ── no engaged advice episodes → not derivable, proxies None ────────────────


def test_no_engaged_episodes_is_not_derivable():
    # pure information-seeking turns: EXTRACT, not adopt/override/verify
    r = reliance_metrics(_session(["what is a parser?", "how does recursion work?"]))
    assert r.derivable is False
    assert r.weight_of_advice is None and r.switch_fraction is None
    assert r.appropriate_reliance is None
    assert r.n_engaged_episodes == 0
    assert "not observable" in r.note


def test_all_hold_means_zero_woa():
    r = reliance_metrics(_session([
        "no, use a different approach instead",
        "ignore that, do it the other way",
    ]))
    assert r.n_hold == 2 and r.n_adopt == 0
    assert r.weight_of_advice == 0.0   # held every time → no lean toward AI
    assert r.switch_fraction == 0.0


def test_self_ratings_never_consulted():
    # the extractor reads tags only; a session metadata self-rating must not move
    # any behavioral number (standing rule: self-rating → calibration gap only)
    base = reliance_metrics(_session(["sounds good"]))
    s = _session(["sounds good"])
    s = s.model_copy(update={"metadata": {"self_rating": 5, "confidence": 0.99}})
    rated = reliance_metrics(s)
    assert rated == base


def test_deterministic():
    s = _session(["sounds good", "no, use recursion instead"])
    assert reliance_metrics(s) == reliance_metrics(s)
    assert isinstance(reliance_metrics(s), RelianceMetrics)


# ── EC wiring (D-021 approved): EC-11 evidence rows, EC-01 excluded ─────────


def test_ec_evidence_target_is_freeze_safe_and_not_ec01():
    import yaml
    from pathlib import Path

    existing = {
        n["id"]
        for n in yaml.safe_load(
            Path("contracts/contract_table.yaml").read_text(encoding="utf-8")
        )["neurons"]
    }
    assert set(EC_EVIDENCE_TARGET) <= existing          # adds zero neurons (#1)
    assert all(nid.startswith("EC-") for nid in EC_EVIDENCE_TARGET)
    # EC-01 is deliberately excluded — P5 graesser→EC-01 already lands there;
    # reusing it would double-count verification behaviour.
    assert "EC-01" not in EC_EVIDENCE_TARGET


def test_evidence_rows_feed_ec11_only_when_derivable():
    derivable = reliance_metrics(_session([
        "sounds good", "no, use recursion instead", "are you sure that's correct?",
    ]))
    rows = reliance_evidence_rows(derivable)
    assert {r["neuron_code"] for r in rows} == {"EC-11"}
    assert {r["feature"] for r in rows} == {"weight_of_advice", "switch_fraction"}
    assert all(r["source"] == "reliance_v1" and r["scope"] == "session" for r in rows)
    assert "EC-01" not in {r["neuron_code"] for r in rows}

    # not derivable → no fabricated rows
    not_derivable = reliance_metrics(_session(["what is a parser?"]))
    assert reliance_evidence_rows(not_derivable) == []


def test_pipeline_surfaces_reliance_as_evidence_only():
    import json
    from contracts.schemas import Dimension
    from src.api.pipeline import score_session_with_artifacts
    from src.trait.judge.client import JudgeClient

    entry = {"score": 0.5, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None
    judge = JudgeClient(
        generate=lambda s, u: json.dumps(data), fallback=None, sleep=lambda _: None
    )
    run = score_session_with_artifacts(
        _session(["sounds good", "no, use recursion instead"]), judge=judge
    )

    assert set(run.reliance) == {"metrics", "ec_evidence"}
    ev_codes = {r["neuron_code"] for r in run.reliance["ec_evidence"]}
    assert ev_codes == {"EC-11"}
    # EVIDENCE only: EC-11 (llm_judge) is not a deterministic firing, and EC's
    # judge score is untouched (no multiplier; #2)
    assert ev_codes & {r["neuron_code"] for r in run.neuron_firings} == set()
    assert run.raw_profile[Dimension.EC].value == 0.5
