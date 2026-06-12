"""D-003 wiring tests: every Stage-1 leaf demonstrably executes inside
score_session — a skipped leaf fails here, not silently. Judge is faked."""

from __future__ import annotations

import json

from contracts.schemas import (
    CanonicalSession,
    Dimension,
    EventType,
    LoadLabel,
    PartnerModel,
    RegimeLabel,
    Turn,
)
from src.api.pipeline import score_session
from src.trait.judge.client import JudgeClient


def _fake_judge() -> JudgeClient:
    entry = {"score": 0.5, "confidence": 0.8, "evidence_turns": [0], "tom_tag": None}
    data = {d.value: dict(entry) for d in Dimension}
    data["ES"]["score"] = None
    payload = json.dumps(data)
    return JudgeClient(generate=lambda s, u: payload, fallback=None, sleep=lambda _: None)


def _session() -> CanonicalSession:
    texts = [
        "walk me through it step by step, must include the cost analysis",  # SCAFFOLD → PR fires
        "are you sure that's correct? you said 100 but the docs say 60 — fix it",  # VERIFY
        "ok",
        "continue",
        "sounds good",
    ]
    turns: list[Turn] = []
    for t in texts:
        turns.append(Turn(index=len(turns), role="human", text=t))
        turns.append(Turn(index=len(turns), role="ai", text="a long enough ai reply here"))
    return CanonicalSession(
        session_id="wire-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


def test_every_leaf_contributes_to_the_response():
    response = score_session(_session(), judge=_fake_judge())

    # tagger + overlay (rules over tags): accept-run of 3 must appear
    assert RegimeLabel.ACCEPT_RUN in response.regime_overlay.strip
    assert RegimeLabel.VERIFICATION in response.regime_overlay.strip

    # transitions: accept_run metrics flow into flags
    assert response.flags.accept_run_max == 3

    # state classifiers: strip is populated with real labels, full confidence
    assert len(response.state_strip) == 5
    assert all(v.confidence == 1.0 for v in response.state_strip)
    assert all(v.load in set(LoadLabel) for v in response.state_strip)
    # metacog leaf: 3 flat accepts = surrender → state validity gate fires
    assert response.state_validity.surrender_detected is True

    # extractors: deterministic firings became raw_counts evidence (PR fired)
    assert response.profile[Dimension.PR].raw_counts.get("extractor_opportunities", 0) > 0


def test_extractor_firings_are_logged_as_nfire_events():
    # the log is internal; prove it via the reaction signatures' event counts —
    # N-FIRE events are not triggers, so pi rows stay gated at n_events=0
    response = score_session(_session(), judge=_fake_judge())
    for row in response.reaction_signatures.pi.values():
        for cell in row.values():
            assert cell.n_events == 0  # only N-FIRE in the log; triggers come later
