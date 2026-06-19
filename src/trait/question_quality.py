"""
src/trait/question_quality.py — EIG question-quality feature extractor (v3 P5).
OWNER: Chief Engineer. (Brief §P5; spec V9 / §C3; SAF_ARI_v3_ClaudeCode_Upgrades §P5.)

Scores the human's prompts for question quality and emits per-turn features plus
a per-session question-complexity summary for the longitudinal layer. The
features are intended to feed EXISTING PR / AL / EC neurons as new evidence
fields — NO new dimension, NO new neuron (ontology freeze, non-negotiable #1).

  score_questions(session) -> QuestionQualityResult
    per_turn:        [QuestionFeature(turn_id, eig_proxy, graesser_type, bloom_tier, specificity)]
    session_summary: SessionQuestionSummary(mean_complexity, complexity_trend, originality)

Everything here is DETERMINISTIC (Tier-A style: regex/keyword cues, no judge, no
embeddings) so the same transcript yields byte-identical features.

── The three instruments (and their honest limits) ──────────────────────────
* `bloom_tier` ∈ 1..6 — Bloom's *revised* taxonomy (remember, understand, apply,
  analyze, evaluate, create), assigned by the highest-tier cognitive cue present.
* `graesser_type` — the Graesser & Person (1994) question taxonomy (16 categories),
  assigned by the best-matching surface cue.
* `eig_proxy` ∈ [0,1] — an Expected-Information-Gain-STYLE heuristic (Coenen/
  Nelson/Gureckis OED): how much the question is *expected* to reduce uncertainty
  given the prior context. It is a proxy built from cognitive tier, question
  openness, targeting specificity, and novelty-vs-prior-context — NOT true EIG.
  OED rests on assumptions about the asker's priors we do not model; treat this as
  one question-quality feature among several, never ground truth (spec §C3 honest
  limit).
* `specificity` ∈ [0,1] — how concretely targeted the prompt is (constraints,
  quantities, code, named entities, success criteria).

── Deviation recorded (DISCREPANCY D-020) ───────────────────────────────────
The spec states the Bloom mapping and Graesser taxonomy are "already in project
files." They are not present in the repo (grep: only the spec docs reference
them). They are therefore implemented self-contained here, as documented
enumerations, rather than imported. If a canonical taxonomy asset lands later,
swap these tables for it behind the same function signatures.

── STOP-FOR-HUMAN-REVIEW (brief §P5; not bypassable in code) ─────────────────
Which exact neuron each feature feeds (PR vs AL vs EC) is an OPEN QUESTION, not a
silent decision. `PROPOSED_NEURON_MAP` below is a *proposal for review only* — it
is NOT wired into the pipeline or the neuron evidence stream. Wiring happens after
human sign-off (see DISCREPANCY D-020). The proposal references only existing
PR/AL/EC neuron ids (freeze-safe); `test_question_quality.py` asserts it adds zero
new neurons.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from contracts.schemas import CanonicalSession


class _Frozen(BaseModel):
    """Frozen, extra-forbidding base, mirroring contracts/schemas.py house style."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ── Graesser & Person (1994) question taxonomy — the 16 categories ───────────
# Ordered most-specific cue first; the first matching category wins. Categories
# with no surface cue fall through to CONCEPT_COMPLETION (the generic wh-fill).
GRAESSER_TYPES = (
    "verification",
    "disjunctive",
    "concept_completion",
    "feature_specification",
    "quantification",
    "definition",
    "example",
    "comparison",
    "interpretation",
    "causal_antecedent",
    "causal_consequence",
    "goal_orientation",
    "instrumental_procedural",
    "enablement",
    "expectational",
    "judgmental",
)

# (category, compiled cue). Evaluated top-to-bottom; judgmental/causal/procedural
# (the "deep" categories) are checked before the shallow fill categories so a
# "why should I..." reads as judgmental, not bare concept-completion.
_GRAESSER_CUES: list[tuple[str, re.Pattern[str]]] = [
    ("judgmental", re.compile(r"\b(should i|should we|what'?s the best|which.*\bbetter\b|do you recommend|would you recommend|is it (a )?good|worth it|right approach)\b", re.I)),
    ("expectational", re.compile(r"\b(why (did|does|is|isn'?t|didn'?t|won'?t|can'?t)|i expected|wasn'?t it supposed)\b", re.I)),
    ("causal_consequence", re.compile(r"\b(what happens if|what (will|would) happen|consequence|what'?s the (effect|impact)|what results?)\b", re.I)),
    ("causal_antecedent", re.compile(r"\b(why\b|what caused|what led to|what'?s the reason|how come)\b", re.I)),
    ("comparison", re.compile(r"\b(difference between|compared? to|versus|vs\.?|\bover\b.*\binstead\b|trade-?offs?)\b", re.I)),
    ("interpretation", re.compile(r"\b(what does this (mean|do|say)|what'?s (happening|going on)|interpret|make sense of)\b", re.I)),
    ("instrumental_procedural", re.compile(r"\b(how (do|can|should|would) (i|we|you)|how to|what steps|walk me through|step by step)\b", re.I)),
    ("enablement", re.compile(r"\b(what do (i|we) need|what'?s required|what enables|prerequisite|in order to)\b", re.I)),
    ("goal_orientation", re.compile(r"\b(what is the (goal|purpose|point|objective)|why are you|what are you trying)\b", re.I)),
    ("example", re.compile(r"\b(example|for instance|such as|give me a (sample|case))\b", re.I)),
    ("definition", re.compile(r"\b(what is a?n?|what'?s a?n?|define|definition of|what do you mean by)\b", re.I)),
    ("quantification", re.compile(r"\b(how (much|many|long|often|fast)|what (percentage|fraction|number))\b", re.I)),
    ("feature_specification", re.compile(r"\b(what (are the |kind of |type of |sort of )?(properties|attributes|features|characteristics)|what kind)\b", re.I)),
    ("disjunctive", re.compile(r"\b(\bor\b.*\?|which (of|one)|either)\b", re.I)),
    ("verification", re.compile(r"\b(is it true|are you sure|is (this|that) (correct|right|wrong)|did you|does (this|it)|can you confirm|isn'?t (it|that))\b", re.I)),
]

# ── Bloom's revised taxonomy — tier cues, highest first ──────────────────────
_BLOOM_CUES: list[tuple[int, re.Pattern[str]]] = [
    (6, re.compile(r"\b(design|create|compose|devise|propose|formulate|construct|invent|synthesi[sz]e|generate (a|an)|build (a|an).*(from scratch|new)|come up with)\b", re.I)),
    (5, re.compile(r"\b(evaluate|assess|critique|justify|judge|recommend|defend|argue|weigh|pros and cons|trade-?offs?|should i|which.*\bbetter\b|is it (a )?good)\b", re.I)),
    (4, re.compile(r"\b(analy[sz]e|why\b|how does|how do .* work|differentiate|distinguish|break (it |this )?down|what caused|relationship between|contrast|debug|diagnose|compare)\b", re.I)),
    (3, re.compile(r"\b(how (do|can|should) (i|we)|implement|apply|calculate|solve|write (the )?code|fix|convert|refactor|build|configure|set up)\b", re.I)),
    (2, re.compile(r"\b(what is|what'?s|explain|describe|summari[sz]e|what does .* mean|paraphrase|clarify|tell me about)\b", re.I)),
    (1, re.compile(r"\b(who|when|where|list|name the|what year|how many)\b", re.I)),
]

# ── specificity cues (each present cue adds graded weight) ───────────────────
_SPECIFICITY_CUES: list[tuple[float, re.Pattern[str]]] = [
    (0.25, re.compile(r"`[^`]+`|```|def \w+\(|\bclass \w+|\w+\.(py|js|ts|sql|json|yaml|md)\b|\w+\(\)")),  # code / inline code
    (0.20, re.compile(r"\b\d[\d,.]*\s*(%|percent|ms|s|kb|mb|gb|px|x|rows?|items?|chars?|tokens?)?\b")),     # quantities
    (0.20, re.compile(r"\b(must|without|only|at most|at least|no more than|exactly|using|in (python|java|rust|go|sql|typescript))\b", re.I)),  # constraints
    (0.15, re.compile(r"\b(so that|such that|the goal is|i want|i need|in order to|so it)\b", re.I)),        # success criteria
    (0.15, re.compile(r"\b([A-Z][a-z]+[A-Z]\w*|[A-Z]{2,}|[A-Z][a-z]+ [A-Z][a-z]+)\b")),                     # named entities / proper nouns
]

# question openness by Graesser category → expected uncertainty reduction band
_OPEN_TYPES = frozenset({
    "causal_antecedent", "causal_consequence", "interpretation", "judgmental",
    "comparison", "goal_orientation", "instrumental_procedural", "expectational",
    "enablement",
})
_CLOSED_TYPES = frozenset({"verification", "disjunctive"})

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an and or of to in is it for on with you i we this that how what why "
    "do does did can could should would will be are was were as at by".split()
)


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


class QuestionFeature(_Frozen):
    """Per-turn question-quality features (spec V9 interface)."""

    turn_id: int = Field(ge=0)
    eig_proxy: float = Field(ge=0.0, le=1.0)
    graesser_type: str
    bloom_tier: int = Field(ge=1, le=6)
    specificity: float = Field(ge=0.0, le=1.0)


class SessionQuestionSummary(_Frozen):
    """Per-session question-complexity summary for the longitudinal layer."""

    #: mean per-turn complexity over scored human prompts, [0,1]
    mean_complexity: float = Field(ge=0.0, le=1.0)
    #: OLS slope of complexity over prompt order, [-1,1]; 0.0 if <2 prompts
    complexity_trend: float = Field(ge=-1.0, le=1.0)
    #: mean novelty-vs-prior-context across prompts, [0,1] (question diversity)
    originality: float = Field(ge=0.0, le=1.0)
    #: how many human prompts were scored (absent ≠ zero — context for the means)
    n_questions: int = Field(ge=0)


class QuestionQualityResult(_Frozen):
    per_turn: tuple[QuestionFeature, ...]
    session_summary: SessionQuestionSummary


def classify_graesser(text: str) -> str:
    for category, cue in _GRAESSER_CUES:
        if cue.search(text):
            return category
    return "concept_completion"


def classify_bloom(text: str) -> int:
    for tier, cue in _BLOOM_CUES:
        if cue.search(text):
            return tier
    # a prompt with no cognitive cue at all is treated as a bare 'understand' ask
    return 2


def specificity(text: str) -> float:
    score = sum(w for w, cue in _SPECIFICITY_CUES if cue.search(text))
    # longer prompts carry more specification, with strong diminishing returns
    length_bonus = min(0.15, len(text) / 4000.0)
    return min(1.0, score + length_bonus)


def _openness(graesser_type: str) -> float:
    if graesser_type in _OPEN_TYPES:
        return 1.0
    if graesser_type in _CLOSED_TYPES:
        return 0.2
    return 0.55


def _eig_proxy(bloom_tier: int, graesser_type: str, spec: float, novelty: float) -> float:
    """EIG-STYLE heuristic (documented approximation, not true EIG).

    Blends cognitive tier, question openness, targeting specificity, and novelty
    vs prior context. Weighted so a high-tier, open, novel, well-targeted question
    scores high and a closed low-tier lookup scores low (the §P5 acceptance shape).
    """
    bloom_norm = (bloom_tier - 1) / 5.0
    value = (
        0.40 * bloom_norm
        + 0.25 * _openness(graesser_type)
        + 0.15 * spec
        + 0.20 * novelty
    )
    return round(min(1.0, max(0.0, value)), 6)


def _complexity(bloom_tier: int, eig: float, spec: float) -> float:
    return 0.5 * ((bloom_tier - 1) / 5.0) + 0.3 * eig + 0.2 * spec


def _ols_slope(ys: list[float]) -> float:
    """Slope of ys against evenly-spaced x∈[0,1]; 0.0 for <2 points."""
    n = len(ys)
    if n < 2:
        return 0.0
    xs = [i / (n - 1) for i in range(n)]
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return round(max(-1.0, min(1.0, slope)), 6)


def score_questions(session: CanonicalSession) -> QuestionQualityResult:
    """Score every human prompt for question quality (deterministic).

    Each human turn is a prompt to the AI and is scored. `eig_proxy` and the
    novelty signal use the running prior context (all preceding human + AI turns).
    """
    features: list[QuestionFeature] = []
    complexities: list[float] = []
    novelties: list[float] = []
    prior_tokens: set[str] = set()

    for turn in session.turns:
        if turn.role != "human":
            prior_tokens |= _tokens(turn.text)
            continue

        cur = _tokens(turn.text)
        # novelty: share of this prompt's content words unseen in prior context
        novelty = 1.0 if not prior_tokens else (
            len(cur - prior_tokens) / len(cur) if cur else 0.0
        )

        graesser = classify_graesser(turn.text)
        bloom = classify_bloom(turn.text)
        spec = specificity(turn.text)
        eig = _eig_proxy(bloom, graesser, spec, novelty)

        features.append(
            QuestionFeature(
                turn_id=turn.index,
                eig_proxy=eig,
                graesser_type=graesser,
                bloom_tier=bloom,
                specificity=round(spec, 6),
            )
        )
        complexities.append(_complexity(bloom, eig, spec))
        novelties.append(novelty)
        prior_tokens |= cur

    n = len(features)
    summary = SessionQuestionSummary(
        mean_complexity=round(sum(complexities) / n, 6) if n else 0.0,
        complexity_trend=_ols_slope(complexities),
        originality=round(sum(novelties) / n, 6) if n else 0.0,
        n_questions=n,
    )
    return QuestionQualityResult(per_turn=tuple(features), session_summary=summary)


# ── PROPOSED feature→neuron mapping — REVIEW ONLY, NOT WIRED (brief §P5 STOP) ─
# This is a proposal for human sign-off, surfaced rather than decided silently.
# It is NOT consumed by the pipeline. Every target is an existing PR/AL/EC neuron
# id (freeze-safe — adds zero neurons); the mapping is the open question for review.
PROPOSED_NEURON_MAP: dict[str, tuple[str, ...]] = {
    # prompt targeting / constraint specification → prompt-reasoning neurons
    "specificity": ("PR-01", "PR-09"),
    # cognitive tier of the ask → prompt-reasoning depth + capability-mapping AL
    "bloom_tier": ("PR-03", "AL-07"),
    # information-seeking value of the question → iterative-refinement + AL
    "eig_proxy": ("PR-03", "AL-01"),
    # verification-shaped questions → error-correction / verification-protocol
    "graesser_type": ("EC-01", "PR-11"),
    # session_summary (mean_complexity, complexity_trend, originality) is a
    # longitudinal/sustainability observable (V9), NOT a single-neuron field.
}
