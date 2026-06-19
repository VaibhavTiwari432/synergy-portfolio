"""v3 P5 — EIG question-quality feature extractor (brief §P5; spec V9 / §C3).
OWNER: Chief Engineer.

Acceptance shape (spec §P5):
  * higher-tier questions (synthesis/evaluation) yield higher eig_proxy AND bloom_tier;
  * features attach to PR/AL/EC WITHOUT altering the neuron count (freeze-safe);
  * session_summary.complexity_trend is computable across a multi-turn fixture.

The feature→neuron WIRING is gated on human review (brief §P5 STOP); these tests
exercise the extractor and assert the *proposed* mapping is freeze-safe, but
nothing here wires features into the live neuron stream.
"""

from __future__ import annotations

from contracts.schemas import CanonicalSession, PartnerModel, Turn
from src.trait.question_quality import (
    PROPOSED_NEURON_MAP,
    QuestionQualityResult,
    classify_bloom,
    classify_graesser,
    score_questions,
    specificity,
)


def _session(human_prompts: list[str]) -> CanonicalSession:
    turns: list[Turn] = []
    for p in human_prompts:
        turns.append(Turn(index=len(turns), role="human", text=p))
        turns.append(Turn(index=len(turns), role="ai", text="an adequate assistant reply."))
    return CanonicalSession(
        session_id="qq-1", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=turns,
    )


# ── Bloom tiers: cues map to the intended cognitive level ───────────────────


def test_bloom_lookup_is_low_tier():
    assert classify_bloom("who invented the transistor?") == 1
    assert classify_bloom("what is a hash map?") == 2


def test_bloom_synthesis_and_evaluation_are_high_tier():
    assert classify_bloom("design a caching layer from scratch for this API") == 6
    assert classify_bloom("evaluate whether Postgres or Mongo is the better fit here") == 5


# ── Graesser taxonomy: representative categories ────────────────────────────


def test_graesser_categories():
    assert classify_graesser("are you sure that's correct?") == "verification"
    assert classify_graesser("why did the build fail?") in {"causal_antecedent", "expectational"}
    assert classify_graesser("how do I configure the watchdog?") == "instrumental_procedural"
    assert classify_graesser("should I use a queue here?") == "judgmental"
    # a bare wh-fill with no deep cue falls through to concept_completion
    assert classify_graesser("the capital city, please") == "concept_completion"


# ── specificity: constraints/code/quantities raise it ───────────────────────


def test_specificity_rises_with_concreteness():
    vague = specificity("can you help me with my code?")
    concrete = specificity(
        "in Python, refactor `parse()` so that it returns at most 100 rows without using pandas"
    )
    assert concrete > vague
    assert 0.0 <= vague <= concrete <= 1.0


# ── core acceptance: higher-tier questions score higher eig_proxy + bloom ───


def test_high_tier_question_outscores_lookup_on_eig_and_bloom():
    result = score_questions(_session([
        "who wrote the C programming language book?",                 # lookup, tier 1, closed
        "design and justify a fault-tolerant retry policy for this queue, weighing the trade-offs",  # create/evaluate
    ]))
    lookup, synth = result.per_turn[0], result.per_turn[1]
    assert synth.bloom_tier > lookup.bloom_tier
    assert synth.eig_proxy > lookup.eig_proxy
    assert synth.bloom_tier >= 5 and lookup.bloom_tier <= 2


# ── session summary: trend computable across a multi-turn fixture ───────────


def test_session_summary_trend_is_computable_and_rising():
    # complexity deliberately escalates lookup → procedural → synthesis
    result = score_questions(_session([
        "what is REST?",
        "how do I implement pagination in this endpoint?",
        "design an evaluation framework to decide whether our pagination scales, and justify it",
    ]))
    s = result.session_summary
    assert s.n_questions == 3
    assert 0.0 <= s.mean_complexity <= 1.0
    assert s.complexity_trend > 0.0  # escalating complexity → positive slope
    assert 0.0 <= s.originality <= 1.0


def test_single_question_has_flat_trend():
    result = score_questions(_session(["what is a monad?"]))
    assert result.session_summary.n_questions == 1
    assert result.session_summary.complexity_trend == 0.0  # <2 points → flat


def test_empty_session_is_safe():
    session = CanonicalSession(
        session_id="empty", source="plaintext",
        partner_model=PartnerModel(family="openai"), turns=[],
    )
    result = score_questions(session)
    assert isinstance(result, QuestionQualityResult)
    assert result.per_turn == ()
    assert result.session_summary.n_questions == 0
    assert result.session_summary.mean_complexity == 0.0


# ── determinism: same transcript → identical features ───────────────────────


def test_deterministic():
    sess = _session(["why is this slow?", "how do I profile it in Python?"])
    a = score_questions(sess)
    b = score_questions(sess)
    assert a == b


# ── freeze-safety: the PROPOSED mapping references only existing PR/AL/EC ────


def test_proposed_neuron_map_is_freeze_safe():
    import yaml
    from pathlib import Path

    raw = yaml.safe_load(
        Path("contracts/contract_table.yaml").read_text(encoding="utf-8")
    )
    existing = {n["id"] for n in raw["neurons"]}
    assert len(existing) == 107  # ontology freeze (non-negotiable #1)

    mapped = {nid for ids in PROPOSED_NEURON_MAP.values() for nid in ids}
    # every proposed target is an EXISTING neuron — the mapping adds zero neurons
    assert mapped <= existing
    # and only the three intended dimensions are touched
    assert all(nid[:2] in {"PR", "AL", "EC"} for nid in mapped)
