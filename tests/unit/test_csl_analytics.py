"""Phase 2.5 acceptance — Tier-1 analytics (flow / bottleneck / orchestration).

Acceptance (v3.2 §2.5): flow returns a transition graph, not a score; bottleneck
refuses to flag a level when task-context marks the delegation appropriate;
orchestration_efficiency raises/refuses if called without a quality argument.
"""

from __future__ import annotations

import pytest

from contracts.schemas import (
    CanonicalSession,
    ConfidenceInterval,
    PartnerModel,
    Rung,
    ScoreStatus,
    Turn,
)
from csl.analytics import (
    BottleneckReport,
    FlowGraph,
    bottleneck,
    cognitive_flow,
    orchestration_efficiency,
)
from csl.ownership import OwnershipResult


def _session(*pairs: tuple[str, str]) -> CanonicalSession:
    turns = [Turn(index=i, role=r, text=t) for i, (r, t) in enumerate(pairs)]
    return CanonicalSession(
        session_id="an-test", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def _ok(level, human_pct):
    return OwnershipResult(
        level=level, label=f"{level}-l", status=ScoreStatus.OK,
        human_pct=human_pct, ai_pct=round(1 - human_pct, 6),
        ci=ConfidenceInterval(low=max(0.0, human_pct - 0.1), high=min(1.0, human_pct + 0.1)),
        n_eff=3.0, pi_s=1.0, censored=None, rung=Rung.DESIGNED,
        method_version="t", flags=(),
    )


# ── cognitive_flow ─────────────────────────────────────────────────────────────


def test_flow_returns_graph_not_score():
    session = _session(
        ("human", "Can you verify this is correct? I checked the docs."),
        ("ai", "..."),
        ("human", "No, that's wrong, fix it. Instead, consider the context here."),
        ("ai", "..."),
    )
    graph = cognitive_flow(session)

    assert isinstance(graph, FlowGraph)
    # structure, not a scalar
    assert hasattr(graph, "nodes") and hasattr(graph, "edges")
    assert not hasattr(graph, "score")
    assert isinstance(graph.nodes, tuple)
    assert isinstance(graph.edges, tuple)


def test_flow_edges_are_counted_transitions():
    session = _session(
        ("human", "verify this please, I checked it"),
        ("ai", "ok"),
        ("human", "no that's wrong, override that"),
    )
    graph = cognitive_flow(session)
    # at least one transition between consecutive tagged human turns
    assert graph.edges
    for e in graph.edges:
        assert e.from_move in graph.nodes
        assert e.to_move in graph.nodes
        assert e.count >= 1


def test_flow_untagged_turns_contribute_nothing():
    # bare chit-chat that produces ACCEPT_FLAT-only / minimal tags still yields a
    # graph object (possibly empty edges); never raises, never a score.
    graph = cognitive_flow(_session(("human", "ok"), ("ai", "sure")))
    assert isinstance(graph, FlowGraph)


def test_flow_is_deterministic():
    session = _session(
        ("human", "verify this, I tested it"),
        ("ai", "x"),
        ("human", "wrong, fix it; consider my context"),
    )
    assert cognitive_flow(session) == cognitive_flow(session)


# ── bottleneck ─────────────────────────────────────────────────────────────────


def _history(human_pct_by_level, n=3):
    return [{lvl: _ok(lvl, pct) for lvl, pct in human_pct_by_level.items()} for _ in range(n)]


def test_bottleneck_refuses_to_flag_appropriate_delegation():
    # C1 consistently low ownership, but task-context says delegation is appropriate.
    history = _history({"C1": 0.1})
    report = bottleneck(history, delegation_policy={"C1": "appropriate"})

    assert isinstance(report, BottleneckReport)
    assert "C1" not in report.flagged_levels
    c1 = next(l for l in report.levels if l.level == "C1")
    assert c1.verdict == "appropriate_delegation"
    assert c1.flagged is False


def test_bottleneck_refuses_to_flag_without_policy():
    # low ownership but no policy → indeterminate, refused (not a deficiency claim).
    report = bottleneck(_history({"C4": 0.1}))
    c4 = next(l for l in report.levels if l.level == "C4")
    assert c4.verdict == "indeterminate"
    assert c4.flagged is False
    assert report.flagged_levels == ()


def test_bottleneck_flags_only_human_required_low_level():
    report = bottleneck(_history({"C4": 0.1}), delegation_policy={"C4": "human_required"})
    c4 = next(l for l in report.levels if l.level == "C4")
    assert c4.verdict == "bottleneck"
    assert c4.flagged is True
    assert "C4" in report.flagged_levels


def test_bottleneck_does_not_flag_adequate_ownership():
    report = bottleneck(_history({"C4": 0.8}), delegation_policy={"C4": "human_required"})
    c4 = next(l for l in report.levels if l.level == "C4")
    assert c4.verdict == "adequate"
    assert c4.flagged is False


def test_bottleneck_insufficient_history():
    report = bottleneck(_history({"C4": 0.1}, n=1), delegation_policy={"C4": "human_required"})
    assert report.status == ScoreStatus.INSUFFICIENT_SAMPLE
    assert report.flagged_levels == ()


def test_bottleneck_ignores_non_ok_observations():
    # non-OK results never contribute an observation (absent != zero).
    history = [
        {"C4": _ok("C4", 0.1)},
        {"C4": OwnershipResult(
            level="C4", label="C4-l", status=ScoreStatus.NOT_APPLICABLE,
            human_pct=None, ai_pct=None, ci=None, n_eff=0.0, pi_s=None,
            censored=None, rung=Rung.DESIGNED, method_version="t", flags=())},
        {"C4": _ok("C4", 0.1)},
    ]
    report = bottleneck(history, delegation_policy={"C4": "human_required"})
    c4 = next(l for l in report.levels if l.level == "C4")
    # only 2 OK observations < min_sessions(3) → insufficient, not flagged
    assert c4.verdict == "insufficient_history"
    assert c4.flagged is False


# ── orchestration_efficiency ───────────────────────────────────────────────────


def test_orchestration_raises_without_quality():
    session = _session(("human", "do a thing"), ("ai", "a long detailed answer here"))
    with pytest.raises(ValueError, match="requires a quality argument"):
        orchestration_efficiency(session, None)


def test_orchestration_rejects_out_of_range_quality():
    session = _session(("human", "x"), ("ai", "y"))
    with pytest.raises(ValueError, match="quality must be in"):
        orchestration_efficiency(session, 1.5)


def test_orchestration_bundles_economy_with_quality():
    session = _session(
        ("human", "summarize this"),                       # 2 human tokens
        ("ai", "here is a fairly long detailed answer block"),  # 8 ai tokens
    )
    result = orchestration_efficiency(session, 0.7)
    assert result.quality == 0.7
    assert result.prompt_economy == round(8 / 2, 6)
    assert result.caveat  # always carries the not-standalone caveat


def test_orchestration_economy_none_when_no_human_tokens():
    session = _session(("ai", "answer with no human prompt"))
    result = orchestration_efficiency(session, 0.5)
    assert result.prompt_economy is None
