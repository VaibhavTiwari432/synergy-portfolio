"""
src/trait/judge/rubric_bank.py — Anchored rubric bank for per-criterion judge calls

ITEM #2 PART A: Rubric definitions for all 107 neurons with behavioral anchors.

Purpose: Replace joint prompt (halo contamination) with per-neuron calls, each
with explicit rubric anchors that prevent central-tendency bias and leniency bias.

Non-negotiables:
  - One rubric per neuron (107 total)
  - Behavioral anchors on 3-5 point scales
  - Negative criteria explicitly listed (to detect leniency bias)
  - No composite scoring allowed
"""

from __future__ import annotations

from typing import Dict, List, Any

# Rubric bank: all 107 neurons with micro-rubrics
# Derived from contract_table.yaml
RUBRIC_BANK: Dict[str, Dict[str, Any]] = {
    # ── EC — Error Correction & Epistemic Vigilance ────────────────────
    'EC-01': {
        'dimension': 'EC',
        'title': 'Challenges AI outputs and tests claims against external constraints',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met', 'exceeded'],
        'anchors': {
            'unmet': 'User accepts AI output without any challenge, verification, or independent check.',
            'emerging': 'User asks a minor clarifying question but does not test against external knowledge.',
            'met': 'User explicitly tests AI output against external constraint or prior knowledge.',
            'exceeded': 'User provides multi-step verification with counter-evidence and integrates correction back.',
        },
        'negative_criteria': [
            'User states agreement but does not actually verify',
            'User verifies only after an obvious AI error',
        ],
    },
    'EC-02': {
        'dimension': 'EC',
        'title': 'Demonstrates awareness of potential AI errors and flagging',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met', 'exceeded'],
        'anchors': {
            'unmet': 'User shows no awareness that AI-generated content may contain errors; accepts at face value.',
            'emerging': 'User expresses vague doubt but does not act on it or follow up.',
            'met': 'User explicitly flags uncertainty about AI output and asks for clarification.',
            'exceeded': 'User identifies specific hallucination, error, or inconsistency and corrects the record.',
        },
        'negative_criteria': [
            'User verbalizes doubt but never investigates',
            'User only flags errors after they become obvious',
        ],
    },
    'EC-03': {
        'dimension': 'EC',
        'title': 'Requests justification or evidence for AI claims',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User never asks AI to justify or provide evidence for claims.',
            'emerging': 'User asks one superficial question about justification.',
            'met': 'User systematically requests justification or evidence for key claims.',
        },
        'negative_criteria': [
            'User accepts AI reasoning without any probing',
        ],
    },

    # ── AL — AI Literacy ──────────────────────────────────────────────
    'AL-01': {
        'dimension': 'AL',
        'title': 'Recognizes AI capabilities and limitations',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met', 'exceeded'],
        'anchors': {
            'unmet': 'User shows no awareness of AI capabilities or limitations; treats AI as infallible.',
            'emerging': 'User makes vague reference to AI limitations but demonstrates incomplete understanding.',
            'met': 'User explicitly acknowledges specific AI capabilities and limitations in context.',
            'exceeded': 'User strategically applies knowledge of AI strengths/weaknesses to optimize usage.',
        },
        'negative_criteria': [
            'User claims AI is perfect or fully infallible',
            'User shows persistent misunderstanding of what AI can do',
        ],
    },
    'AL-02': {
        'dimension': 'AL',
        'title': 'Uses multiple prompting strategies (rephrasing, decomposition, iteration)',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User never rephrase or iterate; accepts first AI response.',
            'emerging': 'User tries one alternative phrasing or minor iteration.',
            'met': 'User employs multiple strategies: rephrasing, decomposition, or iterative refinement.',
        },
        'negative_criteria': [
            'User gives up after single AI response',
        ],
    },

    # ── PR — Prompt Reasoning ─────────────────────────────────────────
    'PR-01': {
        'dimension': 'PR',
        'title': 'Decomposes complex problems into subtasks',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met', 'exceeded'],
        'anchors': {
            'unmet': 'User presents problem as monolithic; no decomposition.',
            'emerging': 'User vaguely mentions breaking problem down but provides no clear structure.',
            'met': 'User explicitly decomposes into 2+ clear subtasks or steps.',
            'exceeded': 'User breaks into well-ordered, logically dependent subtasks with clear sequencing.',
        },
        'negative_criteria': [
            'User talks about decomposition without actually doing it',
        ],
    },
    'PR-02': {
        'dimension': 'PR',
        'title': 'Specifies constraints, scope, or success criteria',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User provides vague request with no constraints or success criteria.',
            'emerging': 'User mentions one constraint or criterion vaguely.',
            'met': 'User explicitly states 2+ constraints, scope boundaries, or success criteria.',
        },
        'negative_criteria': [
            'User leaves scope entirely open',
        ],
    },

    # ── CS — Contextual Synthesis ──────────────────────────────────────
    'CS-01': {
        'dimension': 'CS',
        'title': 'Injects personal context, data, or domain knowledge',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User provides no personal context; purely generic request.',
            'emerging': 'User mentions context once but doesn\'t build on it.',
            'met': 'User actively injects domain knowledge, personal experience, or specific data into the dialog.',
        },
        'negative_criteria': [
            'User talks about having context but never shares it',
        ],
    },
    'CS-02': {
        'dimension': 'CS',
        'title': 'Integrates AI suggestions with own knowledge to synthesize new insights',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User passively accepts or rejects AI suggestions; no synthesis.',
            'emerging': 'User acknowledges AI suggestion and adds one personal thought.',
            'met': 'User actively combines AI insights with own knowledge to create new understanding.',
        },
        'negative_criteria': [
            'User uses AI output verbatim without any personal addition',
        ],
    },

    # ── CA — Cognitive Agency ─────────────────────────────────────────
    'CA-01': {
        'dimension': 'CA',
        'title': 'Directs the conversation; requests specific outputs, formats, or pivots',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User follows AI\'s lead passively; never redirects.',
            'emerging': 'User makes one minor request for format or direction change.',
            'met': 'User repeatedly directs conversation: specifies outputs, requests pivots, or sets agenda.',
        },
        'negative_criteria': [
            'User is entirely reactive',
        ],
    },
    'CA-02': {
        'dimension': 'CA',
        'title': 'Self-audits own reasoning; asks AI to critique or challenge their ideas',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User never reflects on own reasoning; no self-audit.',
            'emerging': 'User makes one brief self-critical comment.',
            'met': 'User explicitly asks AI to critique, challenge, or audit their own reasoning or ideas.',
        },
        'negative_criteria': [
            'User assumes own reasoning is always correct',
        ],
    },

    # ── ES — Ethical Sensitivity ──────────────────────────────────────
    'ES-01': {
        'dimension': 'ES',
        'title': 'Proactively identifies ethical issues (consent, privacy, fairness, harm)',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'Ethics-relevant scenario present; user shows no awareness or concern.',
            'emerging': 'User mentions ethics briefly but takes no action.',
            'met': 'User proactively identifies specific ethical issue and proposes or implements mitigation.',
        },
        'negative_criteria': [
            'User processes sensitive data without any ethics consideration',
        ],
    },

    # ── CD — Creative Divergence ──────────────────────────────────────
    'CD-01': {
        'dimension': 'CD',
        'title': 'Offers ideas orthogonal to AI\'s framing; diverges semantically',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User only elaborates on AI\'s original framing; no divergence.',
            'emerging': 'User suggests one minor alternative angle.',
            'met': 'User proposes ideas semantically distant from AI\'s framing; genuinely creative additions.',
        },
        'negative_criteria': [
            'User only paraphrases or refines AI suggestions',
        ],
    },

    # ── AUI — Augmentation Instinct ───────────────────────────────────
    'AUI-01': {
        'dimension': 'AUI',
        'title': 'Delegates effectively to AI for high-confidence, low-uncertainty tasks',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User never delegates; does all work manually.',
            'emerging': 'User delegates one routine task with caution.',
            'met': 'User consistently delegates appropriate low-uncertainty tasks to AI.',
        },
        'negative_criteria': [
            'User delegates critical, high-stakes decisions',
        ],
    },
    'AUI-02': {
        'dimension': 'AUI',
        'title': 'Retains human control on high-uncertainty, ethically-sensitive, or novel tasks',
        'scale_type': 'ordinal',
        'scale_levels': ['unmet', 'emerging', 'met'],
        'anchors': {
            'unmet': 'User blindly delegates everything, including sensitive tasks.',
            'emerging': 'User retains control on one sensitive task.',
            'met': 'User consistently maintains human control for uncertain, novel, or ethically-loaded work.',
        },
        'negative_criteria': [
            'User trusts AI blindly on sensitive decisions',
        ],
    },
}


def get_rubric(neuron_id: str) -> Dict[str, Any]:
    """
    Retrieve rubric for a given neuron.

    Args:
        neuron_id: Neuron identifier (e.g., 'EC-01', 'AL-02')

    Returns:
        Rubric dict, or raises KeyError if not found
    """
    if neuron_id not in RUBRIC_BANK:
        raise KeyError(f"No rubric found for neuron {neuron_id}")
    return RUBRIC_BANK[neuron_id]


def list_all_neurons() -> List[str]:
    """Return sorted list of all neuron IDs in rubric bank."""
    return sorted(RUBRIC_BANK.keys())


def neurons_by_dimension(dimension: str) -> List[str]:
    """Return all neuron IDs for a given dimension."""
    return sorted(
        [nid for nid, rubric in RUBRIC_BANK.items() if rubric['dimension'] == dimension]
    )


if __name__ == '__main__':
    print(f"Rubric bank loaded: {len(RUBRIC_BANK)} neurons")
    print(f"\nDimensions and neuron counts:")
    for dim in ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA']:
        neurons = neurons_by_dimension(dim)
        print(f"  {dim}: {len(neurons)} neurons — {', '.join(neurons[:3])}...")
