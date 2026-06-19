"""Phase 2.4 acceptance — emergence scanner + judge confirmation.

Acceptance (v3.2 §2.4 / SPEC_emergence): adoption-only -> 0 events;
persistence-only -> 0 events; genuine bilateral fusion -> one BI event at C4/C6;
never C1/C2; candidates judge-confirmed before reportable; frozen threshold
artifact fails loud if missing; no runtime refit.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from contracts.schemas import CanonicalSession, PartnerModel, Turn
from csl.emergence import (
    AbstainingConfirmer,
    EmbeddingCache,
    EmergenceConfig,
    JudgeConfirmation,
    LexicalEmbedder,
    load_emergence_config,
    reportable_events,
    scan_emergence,
)


def _session(*pairs: tuple[str, str]) -> CanonicalSession:
    turns = [Turn(index=i, role=r, text=t) for i, (r, t) in enumerate(pairs)]
    return CanonicalSession(
        session_id="emg-test", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


class _Confirmer:
    """Test judge: confirms with a fixed classification."""

    def __init__(self, *, confirmed=True, level="C4", trigger="BI"):
        self._confirmed, self._level, self._trigger = confirmed, level, trigger

    def confirm(self, packet):
        return JudgeConfirmation(
            judge_confirmed=self._confirmed,
            acf_level=self._level,
            trigger_type=self._trigger,
            confirmation="explicit",
            direction_change=True,
            output_delta=True,
        )


# fixtures with strong lexical separation (threshold is NOT tuned to them) --------

_ADOPTION = _session(
    ("human", "Tell me about pandas for CSV processing."),
    ("ai", "Use pandas to read the CSV and vectorize row operations for speed and efficiency."),
    ("human", "Great, I'll use pandas to read the CSV and vectorize the row operations "
              "for speed and efficiency."),
)

_PERSISTENCE = _session(
    ("human", "I think the bottleneck is memory pressure in my streaming pipeline "
              "with bounded windows."),
    ("ai", "You could profile the code with cProfile to find the slow functions."),
    ("human", "Right, as I said, the bottleneck is memory pressure in my streaming "
              "pipeline with bounded windows."),
)

_FUSION = _session(
    ("human", "Help me speed up my Python script that processes CSV files."),
    ("ai", "You can use the pandas library to read the CSV and vectorize the row "
           "operations for speed."),
    ("human", "Building on that, what if we reframe the real problem: instead of faster "
              "parsing, treat this as a streaming pipeline where memory pressure, not "
              "compute, is the bottleneck. Consider partitioning records into bounded windows."),
)


def test_frozen_artifact_loads_with_required_keys():
    cfg = load_emergence_config()
    assert cfg.thresholds["novelty_high"] == 0.5
    assert cfg.embedder_id == "lexical-bow-hashing-v0"
    assert cfg.window["max_human_turns"] == 3


def test_missing_artifact_fails_loud():
    with pytest.raises(FileNotFoundError):
        load_emergence_config(Path("does/not/exist/emergence_thresholds.yaml"))


def test_malformed_artifact_fails_loud(tmp_path):
    bad = tmp_path / "emergence_thresholds.yaml"
    bad.write_text(yaml.safe_dump({"embedder_id": "x", "thresholds": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="thresholds missing keys"):
        load_emergence_config(bad)


def test_embedder_mismatch_is_refused():
    class _Other:
        id = "other-embedder-v9"

        def embed(self, text):
            return (1.0,) + (0.0,) * 255

    with pytest.raises(ValueError, match="does not match the frozen threshold"):
        scan_emergence(_FUSION, EmbeddingCache(_Other()))


def test_adoption_only_yields_zero_events():
    events = scan_emergence(_ADOPTION, confirmer=_Confirmer())
    assert reportable_events(events) == []


def test_persistence_only_yields_zero_events():
    events = scan_emergence(_PERSISTENCE, confirmer=_Confirmer())
    assert reportable_events(events) == []


def test_bilateral_fusion_yields_one_event_at_c4_or_c6():
    events = scan_emergence(_FUSION, confirmer=_Confirmer(level="C4", trigger="BI"))
    reportable = reportable_events(events)
    assert len(reportable) == 1
    ev = reportable[0]
    assert ev.acf_level in ("C4", "C6")
    assert ev.trigger_type == "BI"
    assert ev.judge_confirmed is True


def test_default_confirmer_abstains_no_reportable_events():
    # candidate is found but the unwired judge abstains -> audit-only, 0 reportable.
    events = scan_emergence(_FUSION, confirmer=AbstainingConfirmer())
    assert len(events) >= 1
    assert all(e.judge_confirmed is False for e in events)
    assert reportable_events(events) == []


def test_never_reportable_at_c1_or_c2_even_if_judge_says_so():
    # structural scope guard: a judge that mislabels C1/C2 cannot produce a
    # reportable emergence event.
    events = scan_emergence(_FUSION, confirmer=_Confirmer(confirmed=True, level="C1"))
    assert reportable_events(events) == []


def test_scanner_is_deterministic():
    a = scan_emergence(_FUSION, confirmer=_Confirmer())
    b = scan_emergence(_FUSION, confirmer=_Confirmer())
    assert a == b


def test_lexical_embedder_is_byte_identical_across_instances():
    v1 = LexicalEmbedder().embed("memory pressure streaming pipeline")
    v2 = LexicalEmbedder().embed("memory pressure streaming pipeline")
    assert v1 == v2


def test_centroid_distance_separates_adoption_from_fusion():
    cache = EmbeddingCache()
    cfg = EmergenceConfig(
        version="t", status="t", embedder_id=cache.embedder_id,
        thresholds={"novelty_high": 0.5, "uptake_min": 0.15,
                    "injection_min": 0.15, "reframing_min": 1},
        window={"max_human_turns": 3, "ai_prior_turns": 5, "human_prior_turns": 5},
    )
    # sanity: fusion produces a candidate, adoption does not (same config).
    assert len(scan_emergence(_FUSION, cache, config=cfg, confirmer=_Confirmer())) >= 1
    assert reportable_events(
        scan_emergence(_ADOPTION, cache, config=cfg, confirmer=_Confirmer())
    ) == []
