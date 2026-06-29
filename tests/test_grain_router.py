"""FIX-0 grain router tests."""

from __future__ import annotations

import pytest

from contracts.schemas import IntentTag, Phase, TurnTags
from src.classifier.grain_router import (
    Grain,
    ci_width_from_synergy_subset,
    classify_grain,
    route_neuron,
    route_neurons,
    session_is_synergy_context,
    synergy_ci_neuron_ids,
)


ACTIVE_TAGS = [TurnTags(turn_index=0, tags=[IntentTag.VERIFY])]
EXTRACT_TAGS = [TurnTags(turn_index=0, tags=[IntentTag.EXTRACT])]


@pytest.mark.parametrize(
    ("neuron_id", "expected"),
    [
        ("EC-01", Grain.SYNERGY),
        ("EC-05", Grain.SYNERGY),
        ("EC-14", Grain.SYNERGY),
        ("CA-01", Grain.SYNERGY),
        ("CA-13", Grain.HUMAN_CONTROL),
        ("CA-16", Grain.HUMAN_CONTROL),
        ("PR-08", Grain.TASK_MANAGEMENT),
        ("PR-15", Grain.TASK_MANAGEMENT),
        ("AL-09", Grain.TASK_MANAGEMENT),
        ("AUI-05", Grain.TASK_MANAGEMENT),
        ("AUI-12", Grain.TASK_MANAGEMENT),
        ("CS-01", Grain.AI_OUTPUT_SHAPING),
        ("CS-03", Grain.AI_OUTPUT_SHAPING),
        ("CS-10", Grain.AI_OUTPUT_SHAPING),
        ("CD-01", Grain.SYNERGY),
        ("CD-05", Grain.OUTPUT_QUALITY),
        ("CD-08", Grain.OUTPUT_QUALITY),
        ("ES-04", Grain.SYNERGY),
        ("ES-11", Grain.HUMAN_CONTROL),
        ("ZZ-99", Grain.UNKNOWN),
    ],
)
def test_classify_grain_twenty_spec_cases(neuron_id, expected):
    assert classify_grain(neuron_id) is expected


def test_synergy_context_requires_active_tags_or_non_extract_phase():
    assert session_is_synergy_context(ACTIVE_TAGS, [Phase.EVALUATE]) is True
    assert session_is_synergy_context([], [Phase.REFINE]) is True
    assert session_is_synergy_context(EXTRACT_TAGS, [Phase.EXTRACT]) is False


def test_synergy_neuron_is_ci_source_in_synergy_context():
    decision = route_neuron("EC-01", tags=ACTIVE_TAGS, phases=[Phase.EVALUATE])
    assert decision.include_in_synergy_ci is True
    assert decision.weight == 1.0


def test_output_quality_is_not_synergy_ci_source():
    decision = route_neuron("CD-08", tags=ACTIVE_TAGS, phases=[Phase.EVALUATE])
    assert decision.include_in_synergy_ci is False
    assert decision.weight < 1.0


def test_extract_only_context_keeps_synergy_out_of_ci_source():
    decision = route_neuron("EC-01", tags=EXTRACT_TAGS, phases=[Phase.EXTRACT])
    assert decision.include_in_synergy_ci is False
    assert decision.reason == "not_synergy_context"


def test_route_neurons_is_deterministic():
    ids = ["EC-01", "CA-16", "CD-08", "PR-08"]
    first = route_neurons(ids, tags=ACTIVE_TAGS, phases=[Phase.EVALUATE])
    second = route_neurons(ids, tags=ACTIVE_TAGS, phases=[Phase.EVALUATE])
    assert first == second


def test_synergy_ci_neuron_ids_preserves_input_order():
    ids = ["CD-08", "EC-01", "PR-08", "CA-16"]
    routes = route_neurons(ids, tags=ACTIVE_TAGS, phases=[Phase.EVALUATE])
    assert synergy_ci_neuron_ids(ids, routes) == ["EC-01", "CA-16"]


def test_acceptance_ci_narrows_from_32_to_about_15_points():
    ids = [f"PR-{i:02d}" for i in range(1, 18)]
    titles = {nid: "Parallelizable sub-task management" for nid in ids}
    synergy_ids = [f"EC-{i:02d}" for i in range(1, 16)]
    ids.extend(synergy_ids)
    titles.update({nid: "Challenges AI outputs and tests claims" for nid in synergy_ids})
    routes = route_neurons(ids, tags=ACTIVE_TAGS, phases=[Phase.EVALUATE], titles=titles)

    narrowed = ci_width_from_synergy_subset(0.32, ids, routes)

    assert narrowed == pytest.approx(0.15, abs=0.01)


def test_ci_width_stays_unchanged_without_synergy_subset():
    ids = ["PR-08", "AUI-05", "CD-08"]
    routes = route_neurons(ids, tags=EXTRACT_TAGS, phases=[Phase.EXTRACT])
    assert ci_width_from_synergy_subset(0.32, ids, routes) == pytest.approx(0.32)

