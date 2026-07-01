"""
src/trait/judge/rubric_bank.py — per-neuron judge rubrics for all 98 llm_judge neurons.

Source of truth: contracts/contract_table.yaml (extractor_type: llm_judge).
Deterministic neurons (EC-06/07/09, PR-02/05/07/14, AL-08, ES-01) have NO rubric here —
adding one would create the double-count hazard in normalize.py (non-negotiable L2).

Each rubric:
  title          — what the neuron measures (short)
  dimension      — parent dim key
  scale_levels   — ordered level names [0..4] for all judge neurons
  anchors        — behavioral anchor per level (maps level name → description)
  negative_criteria — behaviors that confirm a floor score (leniency check)
  strength_map   — non-linear [0,1] per level; calibrated by D-study after Gate A

strength_map design:
  [0.0, 0.25, 0.55, 0.82, 1.0] for all 5-level neurons.
  The 0→1 gap is the largest because absent vs minimal is the dominant signal
  boundary. 3→4 is the smallest because both levels represent genuine competence.
  Do NOT use a linear map (level/4) — it re-imports central tendency (L10).
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet


# ── contract constants ─────────────────────────────────────────────────────────

#: Neurons handled by deterministic extractors — no rubric, no judge call.
DETERMINISTIC_NEURONS: FrozenSet[str] = frozenset({
    'EC-06', 'EC-07', 'EC-09',
    'PR-02', 'PR-05', 'PR-07', 'PR-14',
    'AL-08',
    'ES-01',
})

_SCALE5 = ['none', 'minimal', 'partial', 'clear', 'exemplary']
_STR5   = [0.0, 0.25, 0.55, 0.82, 1.0]  # non-linear; D-study refines post Gate A

# ── rubric bank ───────────────────────────────────────────────────────────────

RUBRIC_BANK: Dict[str, Dict[str, Any]] = {

    # ── EC — Error Correction & Epistemic Vigilance ───────────────────────────

    'EC-01': {
        'dimension': 'EC',
        'title': 'Challenges AI outputs and tests claims against external constraints',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Accepts AI output with no challenge, verification, or independent check.',
            'minimal':   'Asks a minor clarifying question but does not test against external knowledge.',
            'partial':   'Poses a partial verification step (restates and asks if correct) but introduces no independent evidence.',
            'clear':     'Explicitly tests AI output against an external constraint, prior knowledge, or independent source.',
            'exemplary': 'Provides multi-step verification — cites counter-evidence or identifies a specific flaw — AND integrates the correction back.',
        },
        'negative_criteria': [
            'States agreement without actually verifying',
            'Verifies only after an obvious AI error, not proactively',
        ],
        'strength_map': _STR5,
    },

    'EC-02': {
        'dimension': 'EC',
        'title': 'Demonstrates awareness of potential AI errors and flags them',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Shows no awareness that AI content may contain errors; accepts at face value.',
            'minimal':   'Expresses vague doubt but does not act on it or follow up.',
            'partial':   'Explicitly flags uncertainty and asks for clarification or alternative.',
            'clear':     'Disagrees with or challenges a specific AI claim, citing why it seems incorrect.',
            'exemplary': 'Identifies a specific hallucination, error, or inconsistency and explicitly corrects the record with evidence.',
        },
        'negative_criteria': [
            'Verbalizes doubt but never investigates',
            'Only flags errors after they become obvious',
        ],
        'strength_map': _STR5,
    },

    'EC-03': {
        'dimension': 'EC',
        'title': 'Contributes independent reasoning beyond AI output',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Human's contribution is a near-lexical copy of AI output; no independent reasoning.",
            'minimal':   'Rephrases AI output with minor additions but no new reasoning.',
            'partial':   'Adds small new context or judgment but AI output dominates the combined response.',
            'clear':     'Integrates AI output with a significant independent contribution — own domain knowledge, criteria, or judgment.',
            'exemplary': "Human's contribution clearly exceeds the AI output; the final text is substantially human-authored.",
        },
        'negative_criteria': [
            'Parrots AI output with surface-level word changes',
            'Never adds original reasoning to AI content',
        ],
        'strength_map': _STR5,
    },

    'EC-04': {
        'dimension': 'EC',
        'title': 'Applies multi-axis review on high-stakes AI recommendations',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Proceeds with or endorses AI output on a high-stakes decision without any review.',
            'minimal':   'Notes that the decision is important but takes no active verification step.',
            'partial':   'Asks AI to double-check or reconsider one aspect of the high-stakes output.',
            'clear':     'Introduces an independent constraint (policy, domain rule, ethical criterion) to stress-test the recommendation.',
            'exemplary': 'Verifies factual accuracy, checks real-world constraints, and retains explicit decision authority rather than delegating the final call.',
        },
        'negative_criteria': [
            'Delegates final decision to AI on a consequential matter',
            'Accepts AI recommendation on high-stakes topic without independent check',
        ],
        'strength_map': _STR5,
    },

    'EC-05': {
        'dimension': 'EC',
        'title': 'Requests and evaluates justification chains for AI claims',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Does not use explanation affordances; accepts a confident AI claim without requesting justification.',
            'minimal':   'Requests a brief explanation but does not follow up when it is incomplete.',
            'partial':   'Requests explanation and partially evaluates it but does not test whether the reasoning is sound.',
            'clear':     'Requests explanation AND evaluates whether the reasoning is valid; pushes back if justification is weak.',
            'exemplary': 'Drives a multi-turn explanation chain: asks, challenges weak links, accepts only once logically sound.',
        },
        'negative_criteria': [
            'Accepts AI reasoning without any probing',
            'Requests explanation as a formality without evaluating the content',
        ],
        'strength_map': _STR5,
    },

    'EC-08': {
        'dimension': 'EC',
        'title': 'Maintains independent evaluative stance on value judgments',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Delegates subjective value judgment entirely to AI without retaining any human evaluative stance.',
            'minimal':   "Accepts AI's framing of the value dimension but adds a minor personal note.",
            'partial':   "Partially contests AI's value framing with own perspective.",
            'clear':     "Maintains an independent evaluative position that differs from or extends AI's framing.",
            'exemplary': "Uses AI's analysis as raw material, applies own ethical/value framework, and retains decision authority.",
        },
        'negative_criteria': [
            "Adopts AI's value framing without independent reflection",
            'Uses AI agreement as a substitute for own ethical judgment',
        ],
        'strength_map': _STR5,
    },

    'EC-10': {
        'dimension': 'EC',
        'title': 'Spontaneously corrects own prior errors and updates working model',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Makes multiple subsequent turns with no self-correction or acknowledgment of error.',
            'minimal':   'Implicitly shifts position in a later turn without acknowledging the earlier error.',
            'partial':   'Partially corrects an earlier mistake when prompted by the AI.',
            'clear':     'Spontaneously notices and corrects their own prior error, updating the working model.',
            'exemplary': 'Proactively identifies own mistake, explains why it was wrong, and integrates the correction to improve the conversation.',
        },
        'negative_criteria': [
            'Persists with a known error rather than correcting it',
            'Waits for AI to flag own error before acknowledging it',
        ],
        'strength_map': _STR5,
    },

    'EC-11': {
        'dimension': 'EC',
        'title': 'Applies calibrated asymmetric skepticism to confident AI claims',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Treats AI's confidence level as a reliable signal of correctness without applying independent skepticism.",
            'minimal':   'Occasionally questions a confident AI claim but inconsistently.',
            'partial':   'Actively questions AI confidence on most high-confidence claims.',
            'clear':     'Routinely identifies when the AI is confidently wrong and applies appropriate skepticism proportional to stakes.',
            'exemplary': 'More scrutiny on high-confidence AI claims on high-stakes topics; uses own domain knowledge as an independent check.',
        },
        'negative_criteria': [
            'Increases trust in response to confident AI tone',
            'Reduces scrutiny when AI presents elaborate justification',
        ],
        'strength_map': _STR5,
    },

    'EC-12': {
        'dimension': 'EC',
        'title': 'Traces upstream AI errors through downstream outputs',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Proceeds with downstream tasks without recognizing an early AI error has compromised later outputs.',
            'minimal':   'Notices an inconsistency in a later output but does not trace it to an upstream error.',
            'partial':   'Suspects upstream contamination and partially investigates.',
            'clear':     'Explicitly traces an error from its origin step through subsequent outputs and identifies all affected content.',
            'exemplary': 'Maps the full error propagation chain, identifies the root-cause step, and systematically corrects all downstream outputs.',
        },
        'negative_criteria': [
            'Treats each output in isolation when earlier errors are present',
            'Accepts late-stage outputs that inherit an uncorrected upstream mistake',
        ],
        'strength_map': _STR5,
    },

    'EC-13': {
        'dimension': 'EC',
        'title': 'Systematically audits AI solutions against boundary conditions',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Accepts AI solution as complete without probing boundary conditions or exceptional inputs.',
            'minimal':   'Identifies at most one edge case but does not systematically check coverage.',
            'partial':   'Probes a small number of edge cases but misses significant boundary conditions.',
            'clear':     'Systematically enumerates multiple boundary conditions and exceptional inputs, checking the solution against each.',
            'exemplary': 'Structured edge-case audit: enumerates boundaries, exceptional inputs, minority scenarios; verifies coverage for each.',
        },
        'negative_criteria': [
            'Treats first-path AI solution as covering all edge cases',
            'Never tests AI solutions against inputs the AI might not have considered',
        ],
        'strength_map': _STR5,
    },

    'EC-14': {
        'dimension': 'EC',
        'title': 'Surfaces and challenges hidden premises in AI reasoning',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI reasoning at face value without probing what the reasoning presupposes.",
            'minimal':   'Questions one surface-level premise but does not identify deeper load-bearing assumptions.',
            'partial':   "Identifies a major implicit assumption in AI's reasoning and flags it.",
            'clear':     "Systematically surfaces and challenges multiple hidden premises in AI's reasoning chain.",
            'exemplary': 'Articulates the full load-bearing assumption structure, challenges each for domain-appropriateness, requires confirmation before accepting the conclusion.',
        },
        'negative_criteria': [
            'Evaluates AI conclusions without examining the premises',
            'Never asks what assumptions an AI recommendation depends on',
        ],
        'strength_map': _STR5,
    },

    # ── PR — Prompt Reasoning ─────────────────────────────────────────────────

    'PR-01': {
        'dimension': 'PR',
        'title': 'Provides rich context, constraints, and success criteria in prompts',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Provides a vague or underspecified request with no context, constraints, or success criteria.',
            'minimal':   'Provides a bare request with minimal context; no constraints or output criteria stated.',
            'partial':   'Provides context and a partial constraint but no explicit success criteria or output format.',
            'clear':     'Provides clear context, at least one constraint, and a partial definition of desired output quality.',
            'exemplary': 'Provides rich context, explicit constraints, concrete examples or analogies, and clear success criteria — fully scaffolded prompt.',
        },
        'negative_criteria': [
            'Leaves scope entirely open with no boundary conditions',
            'Uses generic instructions that could apply to any task',
        ],
        'strength_map': _STR5,
    },

    'PR-03': {
        'dimension': 'PR',
        'title': 'Diagnoses and reformulates prompts iteratively after suboptimal responses',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Makes no attempt to refine or improve the prompt after an unsatisfactory AI response.',
            'minimal':   'Re-asks essentially the same prompt with minor word changes.',
            'partial':   'Reformulates the prompt with one significant change (more context or a new constraint).',
            'clear':     'Clearly diagnoses why the prior response was insufficient and reformulates to address that specific gap.',
            'exemplary': 'Runs an explicit iterative refinement loop: diagnoses the gap, reformulates with targeted improvements, evaluates whether the new response is better.',
        },
        'negative_criteria': [
            'Accepts first AI response regardless of quality',
            'Repeats the same prompt after receiving an unsatisfactory answer',
        ],
        'strength_map': _STR5,
    },

    'PR-04': {
        'dimension': 'PR',
        'title': 'Shares own reasoning chain and co-reasons with AI',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Issues a bare extractive command with no reasoning or rationale ('write this', 'do this').",
            'minimal':   'Provides a minimal rationale but no reasoning chain.',
            'partial':   "Shares partial reasoning that helps AI understand the goal behind the request.",
            'clear':     'Explicitly shares own reasoning or mental model and asks AI to build on or challenge it.',
            'exemplary': 'Co-reasons with AI — shares current hypothesis, asks AI to find flaws, integrates AI reasoning with own.',
        },
        'negative_criteria': [
            'Treats AI as a pure executor rather than a reasoning partner',
            'Never reveals own reasoning for AI to build on',
        ],
        'strength_map': _STR5,
    },

    'PR-06': {
        'dimension': 'PR',
        'title': 'Constructs expert persona frames that constrain AI epistemic posture',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Issues bare task requests with no role or epistemic framing for the AI.',
            'minimal':   'Mentions a general domain but does not define a specific expert persona or epistemic posture.',
            'partial':   'Assigns a general expert role to AI but without specifying the epistemic stance or knowledge frame.',
            'clear':     'Defines a specific expert persona with a clear knowledge domain and instructs AI to reason from that perspective.',
            'exemplary': 'Constructs a rich persona frame — expert role, epistemic posture, knowledge boundaries, reasoning style — and verifies AI is operating from that frame.',
        },
        'negative_criteria': [
            'Relies on AI default persona with no domain grounding',
            'Assigns a role label without specifying what that role implies',
        ],
        'strength_map': _STR5,
    },

    'PR-08': {
        'dimension': 'PR',
        'title': 'Decomposes complex goals into atomic, non-overlapping sub-tasks',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Delegates a complex multi-faceted task as a single monolithic request.',
            'minimal':   'Splits the task loosely but sub-tasks overlap or remain ambiguous.',
            'partial':   'Identifies the major sub-tasks but some bundle multiple objectives.',
            'clear':     'Decomposes into distinct, non-overlapping sub-tasks, each with a single clear objective.',
            'exemplary': 'Produces a precise minimal decomposition where each sub-task is atomic, non-overlapping, and ordered by dependency.',
        },
        'negative_criteria': [
            'Bundles multiple objectives into a single AI request',
            'Never maps task dependencies before structuring the workflow',
        ],
        'strength_map': _STR5,
    },

    'PR-09': {
        'dimension': 'PR',
        'title': 'Defines explicit priority ranking for competing prompt constraints',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Provides multiple directives with no priority ordering; conflicts left for AI to resolve arbitrarily.',
            'minimal':   'Implies relative priority through ordering but does not state it explicitly.',
            'partial':   'Explicitly marks one directive as primary but leaves other conflict resolution implicit.',
            'clear':     'Defines an explicit priority ranking for competing constraints so that conflict resolution is predictable.',
            'exemplary': 'Specifies a full constraint hierarchy — ranks all constraints by priority, defines tie-breaking rules, verifies AI resolved conflicts in intended order.',
        },
        'negative_criteria': [
            'Leaves conflicting constraints for AI to arbitrate without guidance',
            'Provides constraints without ordering them by importance',
        ],
        'strength_map': _STR5,
    },

    'PR-10': {
        'dimension': 'PR',
        'title': 'Pre-resolves lexical and referential ambiguities before submission',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Submits a prompt with multiple semantic ambiguities without acknowledging or resolving them.',
            'minimal':   'Notices one ambiguity after an AI misinterpretation but only addresses it reactively.',
            'partial':   'Proactively identifies one ambiguous term or reference and clarifies it before submission.',
            'clear':     'Systematically identifies and pre-resolves the main lexical and referential ambiguities in the prompt.',
            'exemplary': 'Structured ambiguity audit before submission — identifies all semantic misinterpretation points, resolves each, confirms single intended interpretation.',
        },
        'negative_criteria': [
            'Submits ambiguous prompts without disambiguation',
            'Treats AI misinterpretation as AI failure rather than prompt ambiguity',
        ],
        'strength_map': _STR5,
    },

    'PR-11': {
        'dimension': 'PR',
        'title': 'Embeds structured verification criteria in prompts',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Issues a directive with no self-audit requirement; accepts AI's final output without building in any quality check.",
            'minimal':   "Adds a vague quality instruction ('make sure it's good') but no concrete self-check criterion.",
            'partial':   'Asks AI to review its output for one specific criterion before finishing.',
            'clear':     'Embeds explicit self-audit instructions listing criteria AI must check its output against.',
            'exemplary': 'Builds a structured verification protocol into the prompt: specific criteria, ordered checking steps, instruction to surface any failures before delivering.',
        },
        'negative_criteria': [
            'Never asks AI to verify its own output before delivering',
            'Adds generic quality requests that are not testable',
        ],
        'strength_map': _STR5,
    },

    'PR-12': {
        'dimension': 'PR',
        'title': 'Runs multi-cycle prompt refinement to convergence',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Abandons task or accepts a suboptimal output after the first AI response with no refinement attempt.',
            'minimal':   'Makes one minimal refinement attempt before accepting whatever AI produces.',
            'partial':   'Makes 2-3 refinement cycles but converges prematurely before output is fully satisfactory.',
            'clear':     'Runs a deliberate multi-cycle refinement process, diagnosing each iteration\'s shortfall and targeting corrections.',
            'exemplary': 'Treats prompt construction as progressive optimization: diagnoses each iteration, makes targeted improvements, continues refining until an explicit quality threshold is met.',
        },
        'negative_criteria': [
            'Accepts first AI response without evaluating against requirements',
            'Treats refinement iterations as AI failures rather than prompt improvement opportunities',
        ],
        'strength_map': _STR5,
    },

    'PR-13': {
        'dimension': 'PR',
        'title': 'Optimizes prompt word choice for precision and output-space control',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Treats word choice in prompts as interchangeable; makes no deliberate lexical decisions.',
            'minimal':   'Occasionally reconsiders a word choice but treats this as stylistic preference rather than a precision issue.',
            'partial':   'Deliberately selects specific terms in at least one place to improve output precision.',
            'clear':     'Demonstrates consistent word-level awareness — deliberately chooses synonyms, verb forms, quantifiers, or presuppositions to constrain output space.',
            'exemplary': 'Systematic semantic optimization: examines each significant term for presupposition load, scope, and ambiguity, selects precise alternatives that uniquely target the intended output.',
        },
        'negative_criteria': [
            'Never considers how word choice affects AI output distribution',
            'Uses interchangeable synonyms without evaluating their presuppositions',
        ],
        'strength_map': _STR5,
    },

    'PR-15': {
        'dimension': 'PR',
        'title': 'Identifies and dispatches parallelizable sub-tasks simultaneously',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Sequences all sub-tasks one after another with no attempt to identify parallelizable components.',
            'minimal':   'Runs at most one sub-task concurrently but does not analyze task dependencies before structuring the workflow.',
            'partial':   'Identifies that some sub-tasks could be parallelized but structures them sequentially out of habit.',
            'clear':     'Explicitly identifies independent sub-tasks and dispatches multiple AI requests simultaneously or instructs parallel execution.',
            'exemplary': 'Explicit dependency analysis, maps the task DAG, identifies all independent branches, dispatches all parallelizable sub-tasks simultaneously.',
        },
        'negative_criteria': [
            'Always serializes sub-tasks regardless of dependencies',
            'Never analyzes which parts of a task are structurally independent',
        ],
        'strength_map': _STR5,
    },

    # ── AL — AI Literacy ──────────────────────────────────────────────────────

    'AL-01': {
        'dimension': 'AL',
        'title': 'Decouples AI linguistic fluency from factual reliability',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Equates AI fluency with factual accuracy; accepts confidently phrased output as true without questioning reliability.',
            'minimal':   'Occasionally questions confident AI claims but primarily relies on fluency as a reliability proxy.',
            'partial':   'Shows awareness that AI confidence does not equal accuracy but applies this inconsistently.',
            'clear':     "Routinely treats AI linguistic confidence as independent from factual accuracy; verifies claims based on content domain rather than assertion style.",
            'exemplary': 'Explicitly and consistently decouples AI fluency from factual reliability; applies calibrated independent verification proportional to domain stakes, not assertion style.',
        },
        'negative_criteria': [
            'Increases trust in proportion to how confident AI sounds',
            'Equates detailed AI explanation with verified accuracy',
        ],
        'strength_map': _STR5,
    },

    'AL-02': {
        'dimension': 'AL',
        'title': 'Understands AI as statistical pattern completion, not reasoning',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Attributes AI responses to genuine reasoning or understanding; treats AI as a cognitive agent with intentions or true beliefs.',
            'minimal':   'Occasionally acknowledges AI as a statistical system but reverts to reasoning-attribution in practice.',
            'partial':   'Understands that AI uses statistical pattern completion but does not consistently apply this when interpreting AI outputs.',
            'clear':     "Clearly understands AI derives answers via pattern completion, not logical deduction, and applies this when evaluating AI output reliability.",
            'exemplary': "Explicitly reasons from AI's statistical nature to predict its failure modes, interpret confidence patterns, and calibrate expectations before output is generated.",
        },
        'negative_criteria': [
            'Treats AI as having genuine intentions or beliefs',
            "Attributes AI errors to 'misunderstanding' rather than statistical distribution failure",
        ],
        'strength_map': _STR5,
    },

    'AL-03': {
        'dimension': 'AL',
        'title': 'Proactively re-anchors critical context across long conversations',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Makes no attempt to re-anchor critical context; assumes AI retains all prior information accurately.',
            'minimal':   'Occasionally re-mentions a key point but does not systematically monitor for AI context loss.',
            'partial':   'Proactively summarizes or re-anchors context at least once after noticing a potential memory loss.',
            'clear':     "Tracks conversation length, anticipates where context degradation may occur, and proactively re-injects critical information before it affects output.",
            'exemplary': "Maintains an explicit mental model of AI's effective context window; systematically re-anchors critical constraints at risk of displacement; verifies context retention before proceeding.",
        },
        'negative_criteria': [
            'Relies on AI to remember constraints established many turns earlier',
            'Never re-injects context even after noticing AI has forgotten it',
        ],
        'strength_map': _STR5,
    },

    'AL-04': {
        'dimension': 'AL',
        'title': 'Anticipates and pre-empts structural brittleness in complex prompts',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Provides complex nested, conditional, or recursive instructions without anticipating any structural failure point.',
            'minimal':   'Notices a structural failure after it occurs but did not predict it before submitting the prompt.',
            'partial':   'Anticipates one likely structural failure point and preemptively simplifies or flags it.',
            'clear':     'Proactively identifies where AI is likely to break on complex formatting, deep conditionality, or recursive logic, and restructures to prevent failure.',
            'exemplary': 'Structural brittleness audit before delegating: maps all nested/conditional/recursive elements; identifies each likely failure point; preemptively restructures, stages, or disambiguates.',
        },
        'negative_criteria': [
            'Submits deeply nested or conditional instructions without testing simpler forms first',
            'Treats structural AI failures as AI incompetence rather than preventable prompt complexity',
        ],
        'strength_map': _STR5,
    },

    'AL-05': {
        'dimension': 'AL',
        'title': 'Constructs domain environment before delegating specialized tasks',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Delegates a specialized task with no domain context or custom parameters; relies entirely on AI's default training distribution.",
            'minimal':   'Provides a general domain label but no specific constraints, terminology conventions, or domain-specific parameters.',
            'partial':   'Establishes partial domain context but does not define the specific knowledge environment needed.',
            'clear':     "Explicitly grounds AI in the relevant domain — establishing terminology conventions, key constraints, and domain-specific parameters before task execution.",
            'exemplary': "Constructs a complete domain environment: defines all relevant terminology, constraints, and knowledge anchors; verifies AI has adopted this environment before proceeding.",
        },
        'negative_criteria': [
            "Uses AI's default training distribution for domain-sensitive work without grounding it",
            'Provides domain label without specifying what conventions and constraints apply',
        ],
        'strength_map': _STR5,
    },

    'AL-06': {
        'dimension': 'AL',
        'title': 'Plans for AI output variance and applies variance-reduction strategies',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Treats AI output as deterministic; assumes identical prompts always yield the same result.',
            'minimal':   'Occasionally reruns a prompt but treats variance as error rather than expected stochastic behavior.',
            'partial':   'Acknowledges that AI outputs can vary but does not factor this into task design or verification strategy.',
            'clear':     'Demonstrates probabilistic expectations — plans for output variance, samples multiple outputs, or applies variance-reduction strategies when consistency is required.',
            'exemplary': 'Explicitly reasons about AI output variance in task design: identifies where variance is acceptable and where it is not; applies appropriate sampling or constraint strategies to manage it.',
        },
        'negative_criteria': [
            'Uses a single AI response to make a downstream decision without acknowledging variance',
            'Treats AI output inconsistency as a bug rather than expected behavior',
        ],
        'strength_map': _STR5,
    },

    'AL-07': {
        'dimension': 'AL',
        'title': 'Maintains and applies a dynamic AI capability map across task types',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Treats AI as uniformly capable across all task types; shows no awareness of model-specific capability degradation zones.",
            'minimal':   'Discovers one capability failure reactively but does not generalize to a model of AI capability profile.',
            'partial':   'Demonstrates awareness of a few specific capability limits but treats these as isolated anomalies.',
            'clear':     "Maintains an active mental map of AI's reliable capability zones versus characteristic degradation areas, and structures task delegation accordingly.",
            'exemplary': "Operates with a detailed, continuously updated capability map: proactively routes tasks to AI only in zones of reliable performance; redirects or scaffolds tasks in known degradation zones; updates the map as new failure evidence emerges.",
        },
        'negative_criteria': [
            "Delegates tasks in known AI failure zones without mitigation",
            'Treats all AI failure modes as random rather than systematic',
        ],
        'strength_map': _STR5,
    },

    'AL-09': {
        'dimension': 'AL',
        'title': 'Evaluates model-task fit before delegating specialized work',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Assigns tasks to AI without evaluating whether the model's architecture and training are appropriate.",
            'minimal':   'Occasionally wonders if AI is the right tool but does not conduct a systematic fit assessment.',
            'partial':   'Identifies that the current AI may be suboptimal for the task but proceeds without mitigation.',
            'clear':     "Explicitly evaluates whether the AI model is a good fit for the task and adjusts task framing or model choice accordingly.",
            'exemplary': "Systematic model-task fit assessment: evaluates model's architecture, training modality, and known capability profile against the task's specific requirements; makes an evidence-based delegation decision.",
        },
        'negative_criteria': [
            'Applies a general-purpose AI to highly specialized tasks without verifying fit',
            'Never considers whether a different model or approach would be more appropriate',
        ],
        'strength_map': _STR5,
    },

    'AL-10': {
        'dimension': 'AL',
        'title': "Maintains an explicit model of AI's epistemic state and context window",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Does not model what information AI has access to in the current context; is surprised by AI failures caused by missing context.",
            'minimal':   "Occasionally wonders what the AI 'knows' but does not systematically reason about its epistemic state.",
            'partial':   'Considers what context AI has been given and makes some adjustments, but misses key epistemic blind spots.',
            'clear':     "Maintains an explicit model of what AI does and does not have access to in the current context window; uses this to predict likely failure modes before they occur.",
            'exemplary': "Precisely simulates AI's epistemic state: inventories what information has been provided, what has been omitted, and what AI cannot access from training — proactively addressing gaps before they produce errors.",
        },
        'negative_criteria': [
            'Expects AI to infer unstated context that was never provided',
            'Surprised by AI failures that a model of its context window would have predicted',
        ],
        'strength_map': _STR5,
    },

    'AL-11': {
        'dimension': 'AL',
        'title': 'Applies modality-specific verification calibration',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Assumes uniform AI reliability across modalities; applies same trust level to image, code, audio, and text without modality-specific calibration.',
            'minimal':   'Notices a modality-specific failure reactively but does not adjust verification depth by modality going forward.',
            'partial':   'Shows awareness that AI reliability varies by modality but applies inconsistent verification adjustment.',
            'clear':     'Demonstrates calibrated modality-specific trust — applies proportionally deeper verification to modalities where AI is known to have lower reliability.',
            'exemplary': 'Explicitly reasons about modality-specific reliability profiles before delegating; applies proportionally adjusted verification depth for each modality type; flags high-risk modality combinations for additional scrutiny.',
        },
        'negative_criteria': [
            'Verifies code-generated content with the same depth as text summaries',
            'Never adjusts scrutiny based on the modality of AI output',
        ],
        'strength_map': _STR5,
    },

    'AL-12': {
        'dimension': 'AL',
        'title': "Distinguishes AI behavioral constraints from genuine capability limits",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Cannot distinguish AI refusals from genuine capability failure; attributes all constraint-driven responses to incompetence.",
            'minimal':   'Suspects system-level constraints are influencing AI behavior but cannot identify the specific constraint type.',
            'partial':   'Correctly identifies one category of system constraint (e.g., safety filter, system prompt) affecting the current interaction.',
            'clear':     "Demonstrates working knowledge of main AI behavioral constraint layers — system prompts, safety filters, alignment fine-tuning — and uses this to distinguish constraint-caused behavior from genuine capability limits.",
            'exemplary': "Explicitly models AI's constraint architecture for the current deployment context; correctly distinguishes refusals from capability limits; adapts interaction strategy to work productively within identified constraints.",
        },
        'negative_criteria': [
            'Attributes AI refusals to capability failure rather than constraint behavior',
            'Never considers that system prompts or safety filters might be shaping AI responses',
        ],
        'strength_map': _STR5,
    },

    'AL-13': {
        'dimension': 'AL',
        'title': 'Implements prompt injection defenses when processing external content',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Instructs AI to process externally sourced content with no awareness that embedded instructions could hijack AI behavior.',
            'minimal':   'Vaguely considers external content as potentially unreliable but does not implement any sandboxing protocol.',
            'partial':   'Explicitly acknowledges the risk of instruction injection when processing external content but does not implement a mitigation strategy.',
            'clear':     "Implements a basic sandboxing protocol — separates data content from trusted instructions and directs AI not to follow instructions found in processed external content.",
            'exemplary': 'Complete prompt injection defense: separates trusted instructions from externally sourced data, implements source verification, explicitly instructs AI on trust boundaries, and verifies that embedded instructions were not executed.',
        },
        'negative_criteria': [
            'Processes untrusted external content with full AI instruction privileges',
            'Never considers that web pages or documents may contain adversarial instructions',
        ],
        'strength_map': _STR5,
    },

    # ── ES — Ethics Sensitivity ───────────────────────────────────────────────

    'ES-02': {
        'dimension': 'ES',
        'title': 'Conducts structured bias audit on AI outputs affecting demographic groups',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Accepts AI output without examining it for demographic stereotyping, statistical bias, or cultural blindness.',
            'minimal':   'Expresses vague unease about potential bias but does not identify a specific instance.',
            'partial':   'Flags a specific demographic or cultural bias instance in the AI output.',
            'clear':     'Identifies a specific bias, explains why it is problematic, and requests a corrected output that addresses it.',
            'exemplary': 'Structured bias audit: examines output for demographic stereotyping, cultural assumptions, and statistical skew; identifies all instances; explains their harm; directs a concrete revision.',
        },
        'negative_criteria': [
            'Publishes AI content that reflects demographic stereotypes without review',
            'Flags bias but takes no corrective action',
        ],
        'strength_map': _STR5,
    },

    'ES-03': {
        'dimension': 'ES',
        'title': 'Evaluates AI outputs against applicable legal and regulatory frameworks',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Accepts AI output without evaluating it against applicable legal, safety, or regulatory frameworks.',
            'minimal':   'Mentions a regulatory concern vaguely but does not conduct a systematic compliance check.',
            'partial':   'Explicitly checks AI output against one specific regulatory requirement.',
            'clear':     'Evaluates AI output against the relevant regulatory framework — identifies compliance requirements, checks conformance, flags violations.',
            'exemplary': 'Structured compliance review: enumerates all applicable frameworks, systematically checks each requirement, identifies violations, directs corrections with specific regulatory citations.',
        },
        'negative_criteria': [
            'Deploys AI output in regulated contexts without compliance review',
            'Treats regulatory requirements as post-hoc concerns rather than pre-deployment checks',
        ],
        'strength_map': _STR5,
    },

    'ES-04': {
        'dimension': 'ES',
        'title': 'Refuses to accept AI as a primary authority; verifies against original sources',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Cites AI output directly as a primary authority without seeking independent confirmation.',
            'minimal':   'Acknowledges AI is not a primary source but does not act to verify against true primary sources.',
            'partial':   'Explicitly flags the need to verify against a primary source before acting on the claim.',
            'clear':     'Identifies the appropriate primary source for the claim and describes a concrete plan to cross-reference it.',
            'exemplary': "Consistently refuses to accept AI as a primary authority — for every significant factual claim, identifies the appropriate primary source, describes how to access and verify it, suspends action until verification is complete.",
        },
        'negative_criteria': [
            'Cites AI-generated content as an authoritative reference',
            'Treats AI citation chains as equivalent to primary source verification',
        ],
        'strength_map': _STR5,
    },

    'ES-05': {
        'dimension': 'ES',
        'title': 'Evaluates AI outputs for intellectual property risk before use',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Uses AI-generated text, code, or creative content without considering whether it reproduces copyrighted material.',
            'minimal':   'Acknowledges a vague IP concern but takes no concrete action to assess or address it.',
            'partial':   'Identifies that a specific AI output may derive from copyrighted material and flags it for review.',
            'clear':     'Evaluates AI output for IP risk, identifies the likely source material, and requests a transformation that avoids reproduction.',
            'exemplary': 'Rigorous IP review — evaluates output for reproduction and structural derivation, identifies risk areas, requires a legally distinct transformation, verifies the revised output is sufficiently transformative before use.',
        },
        'negative_criteria': [
            'Publishes AI-generated creative content without IP review',
            'Treats lack of direct copying as proof of IP safety',
        ],
        'strength_map': _STR5,
    },

    'ES-06': {
        'dimension': 'ES',
        'title': 'Assesses dual-use risk before deploying AI-generated content',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Evaluates AI output only for its intended use context without considering how it could be misused.',
            'minimal':   'Vaguely considers potential misuse but does not conduct a systematic dual-use assessment.',
            'partial':   'Identifies one specific misuse scenario and flags it.',
            'clear':     'Explicitly assesses dual-use risk — identifies plausible misuse scenarios and evaluates likelihood and severity of harm.',
            'exemplary': 'Structured dual-use risk analysis: enumerates plausible alternative use contexts, assesses harm likelihood and severity for each, implements targeted mitigations before deployment.',
        },
        'negative_criteria': [
            'Publishes information without considering how it could be weaponized',
            'Treats intended use as the only relevant use context',
        ],
        'strength_map': _STR5,
    },

    'ES-07': {
        'dimension': 'ES',
        'title': 'Identifies and removes manipulative rhetorical techniques from AI persuasive content',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Accepts AI persuasive content without evaluating whether it relies on illegitimate rhetorical techniques or cognitive bias exploitation.',
            'minimal':   "Senses something is 'too persuasive' but cannot identify the specific manipulative technique.",
            'partial':   'Identifies a specific cognitive bias being exploited or an illegitimate rhetorical technique in the AI output.',
            'clear':     'Identifies the manipulative technique, explains the psychological mechanism being exploited, and requests revision to legitimate persuasion only.',
            'exemplary': 'Systematic manipulation audit: scans output for all cognitive bias exploits and rhetorical manipulation tactics; identifies each instance and its target bias; directs a revision that achieves legitimate influence without manipulation.',
        },
        'negative_criteria': [
            'Uses AI to generate manipulative persuasive content without scrutiny',
            'Conflates persuasive effectiveness with legitimate persuasion',
        ],
        'strength_map': _STR5,
    },

    'ES-08': {
        'dimension': 'ES',
        'title': 'Determines and implements AI disclosure requirements before deployment',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Deploys AI-generated work without considering whether disclosure of AI involvement is required.',
            'minimal':   'Aware that AI disclosure may be relevant but does not determine whether it is required.',
            'partial':   'Explicitly considers the disclosure obligation and makes a judgment call about whether to disclose.',
            'clear':     'Accurately applies the relevant disclosure requirement for the deployment context — correctly determining whether legal, organizational, or ethical disclosure is mandated.',
            'exemplary': 'Proactively determines the full disclosure requirement, implements the appropriate disclosure (label, attribution, notice), and verifies compliance with any applicable mandates.',
        },
        'negative_criteria': [
            'Presents AI-generated content as wholly human-authored without disclosure',
            'Assumes no disclosure is needed without checking applicable requirements',
        ],
        'strength_map': _STR5,
    },

    'ES-09': {
        'dimension': 'ES',
        'title': 'Checks AI recommendations against own values and long-term goals',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI recommendations as aligned with own values and goals without explicitly checking for alignment.",
            'minimal':   'Senses a misalignment but cannot specify how the AI recommendation conflicts with actual values.',
            'partial':   'Identifies a specific misalignment between AI recommendation and values or long-term goals.',
            'clear':     'Explicitly checks AI recommendations against stated values and goals — identifies misalignments and requires correction.',
            'exemplary': 'Maintains a clear value-outcome specification and systematically checks every AI recommendation for alignment — verifying congruence with stated values, long-term goals, and organizational commitments before implementation.',
        },
        'negative_criteria': [
            'Implements AI recommendations that contradict stated values without noticing',
            'Treats AI recommendation as a proxy for own preferences',
        ],
        'strength_map': _STR5,
    },

    'ES-10': {
        'dimension': 'ES',
        'title': 'Maintains principled independence on consequential decisions despite AI input',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Routinely defers to AI judgment on consequential decisions without exercising independent evaluation.',
            'minimal':   'Occasionally notes that a decision should be theirs but still defers to AI in practice.',
            'partial':   'Explicitly reclaims decision authority on at least one consequential decision, overriding AI recommendation.',
            'clear':     'Consistently exercises independent judgment on consequential decisions — uses AI analysis as input, not conclusion, and maintains explicit decision ownership.',
            'exemplary': 'Principled independence discipline: clearly distinguishes AI input from human judgment, actively exercises independent evaluation on all consequential decisions, explicitly articulates own reasoning rather than echoing AI conclusions.',
        },
        'negative_criteria': [
            'Delegates consequential decisions to AI without retaining final judgment',
            'Treats AI consensus as a substitute for personal responsibility',
        ],
        'strength_map': _STR5,
    },

    'ES-11': {
        'dimension': 'ES',
        'title': 'Assigns and documents clear accountability attribution for AI-assisted outputs',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Produces AI-assisted output without identifying who is professionally, legally, and morally responsible for its correctness.',
            'minimal':   'Vaguely attributes responsibility to self but does not make it explicit or binding.',
            'partial':   'Explicitly names the responsible party for the output before deployment.',
            'clear':     'Explicitly assigns professional, legal, and moral responsibility to a specific named human agent and documents this assignment before deployment.',
            'exemplary': "Formalizes accountability attribution: assigns responsibility to a specific human agent, documents AI's role and the human's decision authority, ensures the assignment creates a clear, auditable chain of accountability.",
        },
        'negative_criteria': [
            'Deploys AI-assisted output without assigning professional responsibility',
            'Treats AI involvement as diffusing human accountability',
        ],
        'strength_map': _STR5,
    },

    'ES-12': {
        'dimension': 'ES',
        'title': 'Reasons about population-scale and systemic consequences of AI outputs',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Evaluates AI output only for its immediate single-use impact without considering population-scale or systemic effects.',
            'minimal':   'Acknowledges that scale effects exist in principle but does not reason about them for the current output.',
            'partial':   'Identifies one second-order societal consequence of the AI output being deployed at scale.',
            'clear':     'Systematically reasons about population-scale consequences — identifies second and third-order effects and adjusts the output accordingly.',
            'exemplary': 'Structured systemic impact analysis: considers the full range of societal, structural, and behavioral consequences at population scale; identifies all significant second and third-order effects; requires these to be addressed in the output before deployment.',
        },
        'negative_criteria': [
            'Treats AI outputs as single-instance artifacts without scale implications',
            'Never considers downstream societal effects of pattern-level AI deployment',
        ],
        'strength_map': _STR5,
    },

    'ES-13': {
        'dimension': 'ES',
        'title': 'Investigates training data provenance and composition biases',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI output without examining the likely character or composition of the training data that produced it.",
            'minimal':   "Acknowledges that training data may be biased but does not investigate the provenance of the specific output.",
            'partial':   "Explicitly questions what training data likely underlies AI's specific output — identifies potential source biases.",
            'clear':     "Traces the likely training data composition for the current output — identifies overrepresented sources, underrepresented populations, and biases from data skew.",
            'exemplary': 'Structured data provenance analysis: interrogates likely training data composition for the specific domain and output type; identifies minority-representation gaps, geographic or cultural overrepresentation, and embedded historical biases; requires AI to surface these explicitly.',
        },
        'negative_criteria': [
            'Treats AI output as reflecting objective reality rather than training data distribution',
            'Never asks whose perspectives are overrepresented or absent in AI outputs',
        ],
        'strength_map': _STR5,
    },

    'ES-14': {
        'dimension': 'ES',
        'title': "Stewards affected parties' consent, dignity, and interests in AI-generated representations",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Uses AI to generate outputs that represent, characterize, or affect other individuals without verifying their consent, dignity, or interests.',
            'minimal':   'Acknowledges that affected parties exist but does not actively steward their consent or interests.',
            'partial':   'Identifies that the output affects a specific third party and explicitly considers whether their dignity and material interests are preserved.',
            'clear':     "Verifies that AI output preserves the consent, autonomy, and material interests of all affected individuals — and requires revision for any violation.",
            'exemplary': 'Structured consent and agency audit: identifies all affected parties, verifies consent requirements are met, confirms characterizations preserve dignity and material interests, ensures automated outputs cannot act against individuals without human review.',
        },
        'negative_criteria': [
            'Deploys AI-generated characterizations of individuals without consent consideration',
            'Treats AI-generated representations as impersonal data rather than human-affecting content',
        ],
        'strength_map': _STR5,
    },

    # ── CS — Contextual Synthesis ─────────────────────────────────────────────

    'CS-01': {
        'dimension': 'CS',
        'title': 'Achieves full tonal integration between AI-generated and human-authored content',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Inserts AI-generated blocks with no editing for tonal consistency; AI-generated sections are distinctly different in voice.',
            'minimal':   'Makes minor surface edits to AI text but tonal discontinuity remains visible.',
            'partial':   "Edits AI-generated content to partially align its tone with own writing, reducing but not eliminating discontinuity.",
            'clear':     'Achieves smooth tonal integration — AI-generated and human-authored sections are indistinguishable in voice, cadence, and register.',
            'exemplary': 'Actively orchestrates full integration — identifies all tonal discontinuities, edits each transition point, produces a unified artifact where AI and human contributions are seamlessly merged.',
        },
        'negative_criteria': [
            'Leaves AI-generated sections tonally distinct from human-authored sections',
            'Integrates AI blocks as-is without style harmonization',
        ],
        'strength_map': _STR5,
    },

    'CS-02': {
        'dimension': 'CS',
        'title': 'Validates and repairs logical dependencies broken by AI integration',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Integrates AI output that breaks existing logical dependencies, narrative threads, or structural hierarchies without noticing or repairing the damage.',
            'minimal':   'Notices one broken dependency after integration but misses others.',
            'partial':   'Explicitly checks for and repairs the most visible dependencies but misses subtler structural connections.',
            'clear':     'Systematically checks all logical and structural dependencies before integration and repairs any that the AI output has disrupted.',
            'exemplary': 'Maintains an explicit dependency map and validates AI output against all dependencies before integration — ensuring every logical, structural, and narrative connection is preserved or explicitly updated.',
        },
        'negative_criteria': [
            'Integrates AI content without checking whether it breaks existing narrative or logical threads',
            'Relies on readers to notice broken dependencies rather than checking pre-integration',
        ],
        'strength_map': _STR5,
    },

    'CS-03': {
        'dimension': 'CS',
        'title': 'Extracts high-signal content and strips AI verbosity and filler',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Uses AI-generated content verbatim with no pruning of verbose, repetitive, or low-value content.',
            'minimal':   'Removes only the most obvious repetitions but retains significant filler and low-value elaboration.',
            'partial':   'Performs moderate pruning — removes filler and redundancy but retains some verbose sections.',
            'clear':     'Actively extracts high-signal content and strips low-value elaboration, producing a more information-dense synthesis than the raw AI output.',
            'exemplary': 'Systematic information density optimization: classifies each AI-generated section by signal value, prunes all low-density content, retains only high-signal insights, produces a final artifact with higher information density than the AI raw output.',
        },
        'negative_criteria': [
            'Publishes AI output verbatim including all filler and repetition',
            'Never prunes AI output for information density',
        ],
        'strength_map': _STR5,
    },

    'CS-04': {
        'dimension': 'CS',
        'title': "Rewrites AI vocabulary and syntax to match a specific established human voice",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Uses AI vocabulary, syntax, and rhetorical patterns without editing for alignment with a specific established voice.",
            'minimal':   "Makes minimal edits that preserve AI's characteristic tone rather than replacing it with own voice.",
            'partial':   "Edits AI content to partially adopt the target voice — some AI-characteristic patterns remain.",
            'clear':     "Actively edits AI vocabulary, syntax, cadence, and rhetorical patterns to match a specific pre-established human or organizational voice throughout.",
            'exemplary': "Systematic voice alignment: audits AI output for voice mismatches at the sentence level; replaces AI-characteristic patterns with voice-consistent alternatives; produces a final artifact indistinguishable from the target voice.",
        },
        'negative_criteria': [
            "Publishes AI-characteristic phrasing as own voice",
            'Performs stylistic edits without systematically replacing AI rhetorical patterns',
        ],
        'strength_map': _STR5,
    },

    'CS-05': {
        'dimension': 'CS',
        'title': 'Produces accurate cross-domain translations of technical AI content for non-specialists',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Presents highly technical AI output to a non-specialist audience without translation or simplification.',
            'minimal':   'Simplifies AI output superficially — replaces some jargon but preserves technical complexity inappropriate for the audience.',
            'partial':   'Produces a partially translated version that is more accessible but still loses or distorts some accuracy.',
            'clear':     'Produces an accurate, audience-appropriate translation of the technical content — maintains conceptual accuracy while making it accessible to the target audience.',
            'exemplary': 'Full cross-domain translation with accuracy verification: restructures technical content for the non-specialist audience; confirms all critical information is accurately preserved; checks that the translation is neither over-simplified nor under-simplified.',
        },
        'negative_criteria': [
            'Presents expert-level AI content unmodified to non-expert audiences',
            'Simplifies AI content to the point of losing critical accuracy',
        ],
        'strength_map': _STR5,
    },

    'CS-06': {
        'dimension': 'CS',
        'title': 'Makes all implicit inferential steps explicit for the target reader',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Presents AI output with implicit inferential gaps left implicit — readers without shared context cannot follow the reasoning.',
            'minimal':   'Fills in the most obvious gap but leaves other implicit steps unexplained.',
            'partial':   'Identifies multiple implicit inferential steps and makes at least half of them explicit.',
            'clear':     'Identifies all implicit inferential gaps in AI output and makes them explicit for the target reader.',
            'exemplary': 'Systematic gap audit: reads AI output from the perspective of a reader who lacks the author context; identifies every implicit step; makes each explicit; verifies that the artifact is self-contained and coherent without presupposed knowledge.',
        },
        'negative_criteria': [
            "Assumes readers share context that they don't have",
            'Never bridges inferential gaps between AI-generated logical steps',
        ],
        'strength_map': _STR5,
    },

    'CS-07': {
        'dimension': 'CS',
        'title': 'Re-ranks AI-generated information by actual domain relevance',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Presents AI output in AI's default organization, which reflects statistical co-occurrence patterns rather than domain relevance.",
            'minimal':   "Reorders a few items but largely preserves AI's default information hierarchy.",
            'partial':   "Makes a partial reordering based on domain relevance — the most important content is promoted but secondary reordering is inconsistent.",
            'clear':     "Re-ranks AI-generated information according to actual domain relevance and impact, producing a hierarchy that reflects human domain expertise rather than AI's training distribution.",
            'exemplary': "Explicit salience reconstruction: defines domain-specific relevance criteria, re-ranks all AI content against those criteria, demotes or removes low-relevance content, produces a hierarchy that clearly prioritizes by actual impact.",
        },
        'negative_criteria': [
            "Preserves AI's default ordering of content without domain-based re-ranking",
            "Assumes AI's statistical salience matches human domain priorities",
        ],
        'strength_map': _STR5,
    },

    'CS-08': {
        'dimension': 'CS',
        'title': 'Systematically resolves inconsistencies across multi-source AI outputs',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Presents outputs from multiple AI calls or sessions without checking for inconsistencies between them.',
            'minimal':   'Notices one inconsistency between sources but misses others.',
            'partial':   'Resolves the most visible inconsistencies but does not systematically verify coherence across all sources.',
            'clear':     'Systematically checks all AI outputs from multiple sources for logical consistency, narrative coherence, and factual alignment before integrating.',
            'exemplary': 'Structured multi-source coherence check: maps all sources, identifies all points of intersection, verifies consistency at each, resolves all conflicts explicitly, produces an integrated artifact with no unresolved inconsistencies.',
        },
        'negative_criteria': [
            'Integrates contradictory AI outputs without reconciling them',
            'Treats multi-source inconsistencies as AI errors rather than synthesis problems',
        ],
        'strength_map': _STR5,
    },

    'CS-09': {
        'dimension': 'CS',
        'title': 'Maintains real-time attribution tracking across human and AI contributions',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Produces a synthesized artifact without distinguishing which contributions originated from human reasoning versus AI generation.',
            'minimal':   'Can identify the major AI-derived sections in retrospect but did not maintain a tracking record during synthesis.',
            'partial':   'Maintains informal tracking — can attribute most contributions but has gaps in the record.',
            'clear':     'Maintains explicit attribution tracking throughout synthesis — can identify which specific claims, decisions, and structural choices originated from human versus AI.',
            'exemplary': 'Rigorous attribution discipline: maintains a complete real-time record of human versus AI origin for all significant contributions; can produce a full attribution map sufficient for intellectual, legal, and professional accountability.',
        },
        'negative_criteria': [
            'Cannot distinguish own reasoning from AI output in the synthesized artifact',
            'Treats attribution as a post-hoc formality rather than a real-time discipline',
        ],
        'strength_map': _STR5,
    },

    'CS-10': {
        'dimension': 'CS',
        'title': 'Calibrates AI output register for the specific deployment audience',
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Uses AI-generated content with no calibration of formality, technicality, or cultural register for the specific deployment audience.",
            'minimal':   "Makes minor surface adjustments (e.g., removes obvious jargon) but does not calibrate register at a deeper level.",
            'partial':   "Partially calibrates register — adjusts formality or technicality but not both, leaving register mismatches.",
            'clear':     "Actively calibrates AI output's formality, technicality, cultural register, and assumed shared knowledge for the specific deployment audience and relational context.",
            'exemplary': "Systematic register calibration: analyzes target audience's formality expectations, technical vocabulary, cultural context, and prior knowledge level; adjusts every register dimension accordingly; verifies that output reads naturally to the target audience.",
        },
        'negative_criteria': [
            "Deploys AI content in AI's default register without audience calibration",
            'Adjusts formality without calibrating technical register or cultural assumptions',
        ],
        'strength_map': _STR5,
    },

    'CS-11': {
        'dimension': 'CS',
        'title': "Restores accurate epistemic hedges to AI's over-assertive language",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Uses AI-generated text verbatim with its characteristically over-assertive language — publishing provisional claims as definitive statements.",
            'minimal':   'Adds one hedge marker to the AI output but leaves most over-assertive language intact.',
            'partial':   'Restores epistemic hedges to the most obviously uncertain claims but misses subtler over-assertions.',
            'clear':     'Systematically reviews AI-generated claims for over-assertion and restores appropriate hedges throughout the artifact.',
            'exemplary': 'Structured uncertainty calibration pass: reviews every significant AI claim for its actual epistemic status; restores probabilistic hedges and conditionality to all provisional claims; removes false certainty from all estimates; produces an artifact whose language accurately reflects the warranted epistemic confidence.',
        },
        'negative_criteria': [
            "Publishes AI's confident-sounding estimates as if they were established facts",
            'Adds hedges to emotional tone while leaving epistemic over-assertion intact',
        ],
        'strength_map': _STR5,
    },

    # ── CD — Creative Divergence ──────────────────────────────────────────────

    'CD-01': {
        'dimension': 'CD',
        'title': "Audits and rejects AI's statistically probable outputs to drive genuine novelty",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI's most statistically probable output without any push for uniqueness, novelty, or genuine distinctiveness.",
            'minimal':   "Requests a 'more creative' output without specifying what makes it genuinely novel or non-standard.",
            'partial':   "Explicitly rejects AI's default output for being predictable and directs a specific departure from the statistical mean.",
            'clear':     "Actively resists AI's tendency toward averaged outputs — identifies the generic elements, specifies why they are inadequate, and drives toward genuinely interesting alternatives.",
            'exemplary': "Systematic novelty audit: identifies all statistically expected elements in AI's output, explicitly rejects each that is generic, and drives an iterative process toward content where every non-trivial element is genuinely interesting rather than statistically safe.",
        },
        'negative_criteria': [
            "Accepts the most statistically safe AI output as 'creative'",
            'Requests novelty without specifying what would constitute a genuine departure from the average',
        ],
        'strength_map': _STR5,
    },

    'CD-02': {
        'dimension': 'CD',
        'title': "Injects outside-distribution concepts to force AI creative novelty",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Does not introduce any concepts, references, or frameworks that fall outside AI's likely training distribution for this domain.",
            'minimal':   'Introduces one cross-domain reference but does not develop it into a generative creative direction.',
            'partial':   "Introduces multiple outside-distribution elements — metaphors, cultural frameworks, or references — that begin to shape a distinctive creative direction.",
            'clear':     "Actively injects concepts from outside AI's statistical distribution — metaphors, cultural frameworks, emotional nuances, and references that force genuine creative novelty.",
            'exemplary': "Systematic lateral concept injection: identifies the full distribution of AI's likely creative responses, selects concepts from well outside that distribution, and consistently forces outputs that AI could not have reached without this injection.",
        },
        'negative_criteria': [
            "Stays within the conceptual territory AI would explore by default",
            'Uses cross-domain references decoratively without forcing novel creative directions',
        ],
        'strength_map': _STR5,
    },

    'CD-03': {
        'dimension': 'CD',
        'title': "Uses counterfactual probing to stress-test and expand creative hypotheses",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI's initial creative hypothesis without testing it through hypothetical inversions or 'what if' scenarios.",
            'minimal':   "Poses one counterfactual but does not use it to systematically stress-test the creative hypothesis.",
            'partial':   "Uses multiple counterfactuals to probe the creative space around the initial hypothesis.",
            'clear':     "Actively challenges AI's creative output through targeted counterfactual scenarios — using 'what if' inversions to stress-test and expand the initial creative direction.",
            'exemplary': "Counterfactual probing as a systematic creative tool: defines a set of targeted inversions and hypothetical scenarios, uses each to probe the limits of the current creative hypothesis, synthesizes results into a more robust and expanded creative direction.",
        },
        'negative_criteria': [
            'Never inverts or stress-tests AI creative hypotheses',
            "Accepts the first plausible creative direction without exploring alternatives",
        ],
        'strength_map': _STR5,
    },

    'CD-04': {
        'dimension': 'CD',
        'title': "Actively defends distinctive stylistic idiosyncrasies against AI normalization",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Allows AI to normalize all stylistic idiosyncrasies — unique formatting, unconventional pacing, personal humor — producing safe, averaged output.',
            'minimal':   'Preserves one or two specific idiosyncrasies but allows others to be normalized.',
            'partial':   "Actively identifies and defends characteristic stylistic choices against AI normalization.",
            'clear':     "Maintains a clear inventory of stylistic signatures and actively defends each against AI's normalizing tendency throughout the creative process.",
            'exemplary': "Systematic idiosyncrasy preservation: enumerates all distinctive stylistic choices before delegation, monitors each through the creative process, actively rejects AI normalizations, produces a final artifact that retains the full range of authentic stylistic signatures.",
        },
        'negative_criteria': [
            "Allows AI to sand down all distinctive stylistic features",
            "Treats AI normalization as quality improvement rather than style erasure",
        ],
        'strength_map': _STR5,
    },

    'CD-05': {
        'dimension': 'CD',
        'title': "Evaluates AI creative output against an explicit, internalized aesthetic standard",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI creative output without evaluating it against an internalized aesthetic standard; any technically competent output is accepted.",
            'minimal':   'Expresses vague dissatisfaction with AI creative output but cannot articulate the specific aesthetic failure.',
            'partial':   "Articulates a specific aesthetic shortcoming and requests a revision targeting that dimension.",
            'clear':     "Evaluates AI creative output against an explicit, internalized aesthetic standard — identifies what resonates, what falls short, and what would constitute genuinely good work for this audience.",
            'exemplary': "Rigorous aesthetic evaluation: assesses AI creative output against a multi-dimensional standard (quality, resonance, audience impact, originality, craft); identifies shortcomings at each dimension; drives iterative improvement against an explicit standard of excellence.",
        },
        'negative_criteria': [
            'Accepts technically adequate AI creative output without aesthetic evaluation',
            'Cannot articulate what makes a specific AI output aesthetically insufficient',
        ],
        'strength_map': _STR5,
    },

    'CD-06': {
        'dimension': 'CD',
        'title': "Deliberately transcends constraints when breaking them yields superior creative outcomes",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Instructs AI to comply strictly with all stated constraints even when compliance would produce an inferior creative outcome.",
            'minimal':   'Considers breaking a constraint but reverts to compliance without exploring the transcendence.',
            'partial':   "Explicitly evaluates whether a constraint should be broken — identifies the constraint, the potential benefit of breaking it, and makes a deliberate choice.",
            'clear':     "Deliberately violates a stated constraint when identifying that breaking it yields a qualitatively superior creative outcome — with explicit justification.",
            'exemplary': "Constraint-transcendence as a systematic creative tool: evaluates all constraints for creative necessity; identifies which are rules-of-thumb versus binding requirements; deliberately breaks constraints where transcendence yields superior outcomes; documents the justification.",
        },
        'negative_criteria': [
            'Treats all stated constraints as inviolable regardless of creative cost',
            'Never evaluates whether a constraint is limiting creative quality',
        ],
        'strength_map': _STR5,
    },

    'CD-07': {
        'dimension': 'CD',
        'title': "Injects productive conflict and sustains irresolution against AI's harmonizing tendency",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI's tendency to prematurely resolve conflict and avoid genuine irresolution — resulting in narratives without productive tension.",
            'minimal':   "Requests 'more conflict' generically but does not specify the tension type or mechanism.",
            'partial':   'Introduces one specific form of narrative tension (conflict, ambiguity, stakes, or irresolution).',
            'clear':     "Actively injects productive conflict, stakes, and genuine irresolution into AI's creative output — pushing back against AI's tendency to smooth tension into safe conclusions.",
            'exemplary': "Systematic tension architecture: identifies where AI's default narrative flattens conflict; designs specific tension mechanisms appropriate to the work; injects these deliberately; ensures the resulting narrative maintains irresolution where resolution would be premature.",
        },
        'negative_criteria': [
            "Accepts AI's resolution of conflict without testing whether irresolution would be stronger",
            "Treats AI's harmonious outcomes as a creative success",
        ],
        'strength_map': _STR5,
    },

    'CD-08': {
        'dimension': 'CD',
        'title': "Generates novel cross-domain analogies outside AI's statistical mapping",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI's default analogies and metaphors, which reflect high-frequency co-occurrences in training data rather than genuine insight.",
            'minimal':   "Requests 'a different analogy' without specifying what cross-domain novelty would look like.",
            'partial':   "Produces or elicits one genuinely non-standard analogy that falls outside AI's statistical co-occurrence patterns.",
            'clear':     "Actively generates novel cross-domain analogies and metaphorical mappings demonstrably outside AI's training distribution — introducing genuine conceptual insight through unusual connections.",
            'exemplary': "Systematic analogical exploration: rejects default training-data analogies; identifies structurally similar domains outside AI's usual mapping; generates multiple novel cross-domain metaphors; selects the analogy with the highest generative power for the specific communicative purpose.",
        },
        'negative_criteria': [
            "Uses the first analogies AI offers without pushing for novel cross-domain alternatives",
            'Treats high-frequency AI analogies as creative contributions',
        ],
        'strength_map': _STR5,
    },

    'CD-09': {
        'dimension': 'CD',
        'title': "Preserves counterintuitive and structurally unconventional elements against AI normalization",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Allows AI to normalize counterintuitive, unexpected, or structurally unconventional creative elements into statistically expected forms.',
            'minimal':   'Preserves one counterintuitive element but allows others to be normalized.',
            'partial':   'Explicitly protects multiple surprising or unconventional elements from AI normalization.',
            'clear':     "Actively preserves the full range of counterintuitive and unexpected elements — pushing back against any AI tendency to sand them into predictable forms.",
            'exemplary': "Systematic surprise preservation: inventories all non-standard elements before AI delegation, monitors AI's processing for normalization, actively rejects any normalization, produces a final artifact that maintains the original surprise value intact.",
        },
        'negative_criteria': [
            "Allows AI to sand away all elements that make the work distinctive",
            "Treats AI normalization as 'polishing'",
        ],
        'strength_map': _STR5,
    },

    'CD-10': {
        'dimension': 'CD',
        'title': "Integrates authentic embodied experience that AI cannot generate",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Produces creative or analytical work without incorporating any authentic sensory, physical, or embodied experience that AI cannot generate.',
            'minimal':   'Includes one generic sensory detail that could plausibly have been generated by AI.',
            'partial':   'Introduces specific embodied details — sensory, physical, or kinesthetic — that are authentically rooted in direct human experience.',
            'clear':     'Actively integrates rich, specific embodied experience into the work — sensory textures, physical states, kinesthetic memories — that carry genuine felt truth unavailable to AI.',
            'exemplary': 'Embodied experience as a systematic creative differentiator: inventories the authentic human experiences relevant to the task, selects those with the highest felt-truth value, integrates them with precision, evaluates the result for the quality of lived authenticity that AI content categorically cannot replicate.',
        },
        'negative_criteria': [
            'Never contributes authentic personal experience to AI-assisted creative work',
            'Uses generic sensory language that AI could have generated independently',
        ],
        'strength_map': _STR5,
    },

    'CD-11': {
        'dimension': 'CD',
        'title': "Constructs and applies a rich, specific audience model throughout the creative process",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Produces creative work without explicitly modeling the specific target audience's emotional state, cognitive load, prior knowledge, or unstated needs.",
            'minimal':   'Makes generic audience-awareness statements without developing a specific audience model.',
            'partial':   'Describes the target audience with moderate specificity — characterizing their knowledge level and key expectations.',
            'clear':     "Constructs and applies a specific audience model — characterizing the target reader's emotional state, cognitive load, prior knowledge, cultural context, and unstated needs — and calibrates the creative work accordingly.",
            'exemplary': 'Builds and explicitly applies a rich, specific audience model throughout the creative process: characterizes multiple audience dimensions, continuously evaluates each creative decision against this model, produces work genuinely calibrated to a real human receiver rather than a statistical average audience.',
        },
        'negative_criteria': [
            'Optimizes creative work for a generic audience rather than a specific one',
            'Never models the actual receiver of the creative work',
        ],
        'strength_map': _STR5,
    },

    # ── AUI — Augmentation Instinct ───────────────────────────────────────────

    'AUI-01': {
        'dimension': 'AUI',
        'title': "Identifies the precise cognitive friction threshold and delegates at the optimal moment",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Manually executes tasks that AI could handle more efficiently, without recognizing the optimal delegation point.',
            'minimal':   'Identifies that a task is burdensome after struggling with it, rather than anticipating the friction threshold before starting.',
            'partial':   'Recognizes in advance that a task may cross the cognitive friction threshold and considers AI delegation.',
            'clear':     "Accurately identifies the precise point at which a task's complexity exceeds the optimal manual effort threshold and delegates at that point.",
            'exemplary': 'Systematic cognitive friction heuristic: proactively evaluates each task component before execution, identifies the exact delegation threshold, and delegates at the optimal moment — neither too early nor too late.',
        },
        'negative_criteria': [
            'Delegates to AI before understanding what makes a task burdensome',
            'Manually executes tasks past the point where AI delegation would be more efficient',
        ],
        'strength_map': _STR5,
    },

    'AUI-02': {
        'dimension': 'AUI',
        'title': "Applies deliberate task-type differentiation routing rote to AI and nuanced to human",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Delegates all task types to AI uniformly — both rote and high-nuance, high-stakes tasks — without strategic differentiation.',
            'minimal':   'Applies rough task-type filtering but makes delegation errors on ambiguous tasks.',
            'partial':   'Correctly delegates rote, high-volume tasks to AI and retains some high-nuance tasks, though not consistently.',
            'clear':     'Applies deliberate task-type differentiation — delegates rote and pattern-based work to AI and intentionally retains high-nuance, high-stakes, and ethically consequential work for human cognition.',
            'exemplary': 'Systematic task-type routing: classifies each sub-task by automation-suitability dimensions (volume, pattern-complexity, nuance, stakes, ethical weight), delegates all automation-suitable work to AI, explicitly retains all work requiring irreducible human judgment.',
        },
        'negative_criteria': [
            'Delegates high-nuance or ethically consequential tasks to AI with no differentiation',
            'Treats all tasks as equally suitable for AI automation',
        ],
        'strength_map': _STR5,
    },

    'AUI-03': {
        'dimension': 'AUI',
        'title': "Matches AI modality to task structural requirements",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Uses a generative language model for tasks better served by a different AI system type (analytical, visual, retrieval-based, or code-execution).',
            'minimal':   'Recognizes that the current AI may not be the best tool but continues using it without considering alternatives.',
            'partial':   'Identifies a more appropriate AI system type for the task and notes this, even if continuing with the current tool.',
            'clear':     'Explicitly matches the AI system type to the task requirements — choosing the AI modality best suited to the structural requirements of the problem.',
            'exemplary': "Systematic modality assessment: evaluates the task's structural requirements against the capability profiles of available AI modalities; selects the most appropriate modality; verifies that the selection is justified by task structure rather than habit or convenience.",
        },
        'negative_criteria': [
            'Uses the most familiar AI tool regardless of task fit',
            'Never considers alternative AI modalities even when the current one is clearly suboptimal',
        ],
        'strength_map': _STR5,
    },

    'AUI-04': {
        'dimension': 'AUI',
        'title': "Applies explicit interaction ROI thresholds to decide when to stop debugging AI",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Persists with a failing prompt chain without recognizing when the cognitive cost of debugging exceeds the value of the AI-assisted output.',
            'minimal':   'Eventually abandons a prompt chain after excessive debugging effort but does not apply a systematic threshold.',
            'partial':   'Applies an implicit ROI threshold — abandons AI when debugging cost clearly exceeds value — but the threshold is not explicit or consistent.',
            'clear':     'Applies a clear interaction ROI assessment: identifies when AI debugging cost exceeds expected output value and switches to direct human execution at the appropriate moment.',
            'exemplary': 'Maintains an explicit, real-time interaction ROI model: monitors accumulated debugging cost against expected output value, identifies the precise breakeven threshold for the current task, reclaims direct execution authority at the optimal moment.',
        },
        'negative_criteria': [
            'Invests disproportionate debugging effort in a failing AI prompt chain',
            'Never evaluates whether the cost of prompting exceeds the value of the output',
        ],
        'strength_map': _STR5,
    },

    'AUI-05': {
        'dimension': 'AUI',
        'title': "Uses AI as a structured external cognitive scratchpad to offload working memory",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Maintains all intermediate reasoning states and task context internally without using AI as an external cognitive scratchpad.',
            'minimal':   'Uses AI to store some information externally but does not deliberately structure this as working memory offloading.',
            'partial':   'Deliberately offloads at least one class of intermediate cognitive state to AI — freeing working memory for higher-order reasoning.',
            'clear':     'Intentionally uses AI as a structured external cognitive scratchpad — offloads specific intermediate states, retrieves them on demand, and directs freed cognitive resources toward higher-order strategic reasoning.',
            'exemplary': 'Systematic working memory offloading strategy: classifies cognitive tasks by working-memory intensity, offloads all high-load components to AI, maintains only strategic reasoning in active cognition, and demonstrates improved higher-order reasoning as a result.',
        },
        'negative_criteria': [
            'Never uses AI to externalize intermediate reasoning states',
            'Uses AI as an executor rather than as a cognitive extension for complex reasoning',
        ],
        'strength_map': _STR5,
    },

    'AUI-06': {
        'dimension': 'AUI',
        'title': "Monitors own cognitive saturation and offloads to AI at the optimal threshold",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Continues working past cognitive saturation without recognizing degraded performance or adjusting delegation strategy.',
            'minimal':   'Notices fatigue or cognitive overload after performance degrades rather than anticipating it.',
            'partial':   'Identifies the onset of cognitive saturation and adjusts their approach, though not immediately or optimally.',
            'clear':     'Monitors cognitive load in real time, identifies the saturation threshold before performance degrades, and strategically offloads to AI at the optimal moment.',
            'exemplary': 'Continuous metacognitive load monitoring: maintains awareness of own mental saturation state, identifies the productive overload threshold proactively, and delegates to AI precisely at the point where offloading maximizes rather than interrupts productive cognitive engagement.',
        },
        'negative_criteria': [
            'Never adjusts AI delegation in response to own cognitive fatigue',
            'Treats cognitive saturation as a fixed limit rather than something to manage through delegation',
        ],
        'strength_map': _STR5,
    },

    'AUI-07': {
        'dimension': 'AUI',
        'title': "Calibrates prompt crafting investment proportionally to expected output return",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Invests the same level of prompt crafting effort regardless of expected return — either under-investing on high-value tasks or over-investing on low-value ones.',
            'minimal':   'Applies rough prompt effort calibration but makes systematic mismatches between effort and expected value.',
            'partial':   'Consciously calibrates prompt effort for at least some tasks — investing more where expected return is higher.',
            'clear':     'Applies deliberate prompt investment calibration: adjusts cognitive effort devoted to prompt crafting proportionally to the expected improvement in output quality versus the baseline.',
            'exemplary': 'Explicit prompt investment model: evaluates expected return on prompt refinement effort for each task category, allocates crafting effort proportionally, has a clear threshold at which further prompt refinement is not worth the investment.',
        },
        'negative_criteria': [
            'Applies maximal prompt crafting effort to all tasks regardless of value',
            'Under-invests in prompts for high-stakes tasks relative to low-stakes ones',
        ],
        'strength_map': _STR5,
    },

    'AUI-08': {
        'dimension': 'AUI',
        'title': "Monitors for and actively counters AI-delegation-driven skill atrophy",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Delegates specific task types to AI habitually without any awareness that sustained delegation may erode own capability in those areas.',
            'minimal':   'Acknowledges that AI dependency is a theoretical concern but does not assess own current dependency level.',
            'partial':   'Identifies at least one domain where sustained AI delegation is creating potential skill atrophy.',
            'clear':     'Actively monitors capability profile for dependency risk — identifies task domains where habitual delegation is degrading independent capability and takes countermeasures.',
            'exemplary': 'Continuous dependency risk inventory: monitors which task types have been delegated to AI; assesses atrophy risk for each; identifies where genuine skill degradation is occurring; implements deliberate practice or delegation reduction to protect capability profile.',
        },
        'negative_criteria': [
            'Never considers whether habitual AI delegation is eroding own skills',
            'Treats increased AI reliance as unambiguous efficiency improvement',
        ],
        'strength_map': _STR5,
    },

    'AUI-09': {
        'dimension': 'AUI',
        'title': "Defines intervention criteria in advance and reclaims control at the optimal handoff moment",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Allows AI to complete tasks autonomously without monitoring progress — discovering AI errors only after completion when correction is costly.',
            'minimal':   'Reclaims control reactively after identifying an AI error but does not define intervention criteria in advance.',
            'partial':   'Identifies in advance one condition that would trigger mid-task control reclamation.',
            'clear':     'Defines explicit intervention criteria before delegating, monitors AI progress against them, and reclaims control at the appropriate moment when criteria are met.',
            'exemplary': 'Systematic handoff timing management: defines complete intervention criteria before delegation, monitors AI progress continuously against all criteria, reclaims control at the precise optimal moment — early enough to prevent irreversible errors but not so early that productivity value is forfeited.',
        },
        'negative_criteria': [
            'Lets AI complete tasks without any monitoring of intermediate outputs',
            'Only intervenes after a costly error has already occurred',
        ],
        'strength_map': _STR5,
    },

    'AUI-10': {
        'dimension': 'AUI',
        'title': "Maintains explicit skill-gap self-awareness and heightens scrutiny in gap areas",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Uses AI to cover genuine foundational knowledge gaps without acknowledging those gaps — treating AI as a seamless substitute for expertise they do not possess.",
            'minimal':   'Vaguely senses operating outside their competency but does not make this explicit or adjust AI usage accordingly.',
            'partial':   'Explicitly identifies their knowledge gap in the relevant domain and flags it as context for evaluating AI output.',
            'clear':     "Maintains an accurate metacognitive inventory of own knowledge gaps — uses AI to supplement genuine expertise while remaining aware that AI outputs in gap areas cannot be independently verified.",
            'exemplary': "Skill-gap self-awareness as risk management: inventories domain knowledge precisely; identifies all areas where AI would be substituting rather than supplementing expertise; applies proportionally heightened scrutiny in gap areas; does not deploy AI-generated content in gap areas without independent expert review.",
        },
        'negative_criteria': [
            'Presents AI-generated content in expert domains without disclosing own knowledge gaps',
            'Treats AI output in unknown domains as independently verifiable',
        ],
        'strength_map': _STR5,
    },

    'AUI-11': {
        'dimension': 'AUI',
        'title': "Applies stakes-tiered verification depth across AI outputs",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Applies the same verification intensity to all AI outputs regardless of their stakes, domain, or error consequences.',
            'minimal':   'Applies rough verification effort differentiation — spending more time on outputs that feel important.',
            'partial':   'Explicitly allocates more verification effort to higher-stakes outputs and less to routine ones, though threshold criteria are not explicit.',
            'clear':     'Maintains a deliberate verification effort budget — classifies AI outputs by stakes and error consequence, and allocates proportionally calibrated review depth to each category.',
            'exemplary': 'Systematic verification tiering model: classifies outputs into explicit stakes tiers; assigns deep, moderate, and light review protocols to each tier; implements the appropriate review depth for each output; optimizes the total verification budget across the session.',
        },
        'negative_criteria': [
            'Reviews all AI outputs with the same depth regardless of consequences',
            'Never explicitly allocates verification effort based on stakes',
        ],
        'strength_map': _STR5,
    },

    'AUI-12': {
        'dimension': 'AUI',
        'title': "Designs minimum-necessary permission envelopes for autonomous AI agents",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Delegates to an autonomous AI agent with no specification of permission boundaries, resource access limits, or reversibility constraints.',
            'minimal':   'Specifies one dimension of agent permission (e.g., what actions are allowed) but leaves others undefined.',
            'partial':   'Specifies at least two permission dimensions — allowed actions and access scope — before delegation.',
            'clear':     'Defines a minimum-necessary permission envelope for the agent: specifies allowed actions, resource access limits, and reversibility constraints explicitly before delegation.',
            'exemplary': 'Comprehensive agentic permission design: defines minimum necessary authority for each permission dimension (actions, resources, access scope, reversibility); establishes monitoring checkpoints; specifies escalation criteria; verifies that the permission envelope prevents unauthorized scope expansion before delegating.',
        },
        'negative_criteria': [
            'Grants AI agents unbounded permissions without constraint specification',
            'Delegates to autonomous agents without defining what they are not allowed to do',
        ],
        'strength_map': _STR5,
    },

    # ── CA — Collaborative Agency ─────────────────────────────────────────────

    'CA-01': {
        'dimension': 'CA',
        'title': "Exercises confident volitional override of AI outputs that conflict with own judgment",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Defers to AI authority even when AI's output contradicts own judgment, domain knowledge, or values.",
            'minimal':   'Feels discomfort with AI output that conflicts with own judgment but defers anyway without articulating a clear reason.',
            'partial':   'Explicitly disagrees with an AI output but frames the override tentatively.',
            'clear':     'Confidently overrules AI output when it conflicts with own judgment — exercises clear volitional authority over AI recommendations.',
            'exemplary': "Full sovereign override capacity: rejects AI output with explicit justification, explains why AI's reasoning is flawed or inappropriate in this context, rewrites core assumptions when AI has gone fundamentally wrong.",
        },
        'negative_criteria': [
            'Defers to AI even when own domain knowledge contradicts its recommendation',
            "Accepts AI framing because it seems authoritative, not because it is correct",
        ],
        'strength_map': _STR5,
    },

    'CA-02': {
        'dimension': 'CA',
        'title': "Uses AI wait states productively; maintains cognitive momentum during generation",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Goes cognitively idle during AI generation — waiting passively for AI output with no productive cognitive activity.',
            'minimal':   'Engages in minor productive activity during AI wait states but returns to idle before AI completes.',
            'partial':   'Maintains deliberate cognitive activity during AI generation — working on adjacent aspects of the task.',
            'clear':     'Uses AI wait states productively — advances parallel thinking, documents next steps, or makes progress on related work during generation time.',
            'exemplary': 'Systematic cognitive momentum management: plans parallel human work items before initiating AI generation, executes them during AI wait states, and achieves measurable productivity during what would otherwise be dead time.',
        },
        'negative_criteria': [
            'Remains cognitively idle during all AI generation cycles',
            'Treats AI wait time as unavoidable downtime rather than an opportunity',
        ],
        'strength_map': _STR5,
    },

    'CA-03': {
        'dimension': 'CA',
        'title': "Maintains cognitive compartmentalization between distinct problems in a session",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Allows context, framing, or assumptions from one problem to bleed into a structurally different problem in the same session.",
            'minimal':   'Notices context cross-contamination after it has affected an output but did not prevent it.',
            'partial':   'Takes deliberate steps to separate cognitive frames when switching between distinct problems.',
            'clear':     "Maintains clear cognitive compartmentalization between distinct problems, projects, or objectives — preventing AI context from one domain from contaminating reasoning about another.",
            'exemplary': "Systematic context isolation: explicitly resets own cognitive frame and AI's working context when switching between unrelated problems; verifies that no cross-contamination has occurred; maintains clean separation throughout the session.",
        },
        'negative_criteria': [
            'Lets prior problem framing infect reasoning about a structurally different problem',
            'Never resets AI context when switching between unrelated tasks',
        ],
        'strength_map': _STR5,
    },

    'CA-04': {
        'dimension': 'CA',
        'title': "Rapidly diagnoses and strategically recovers from AI failures",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Abandons or dramatically loses momentum when AI hallucinates, loses context, or fundamentally undermines the workflow.',
            'minimal':   'Recovers from AI failure eventually but the recovery is slow and reactive rather than strategic.',
            'partial':   'Diagnoses the cause of the AI failure and takes targeted corrective action.',
            'clear':     'Rapidly diagnoses, restructures, and recovers the workflow from AI failures — applying systematic recovery strategies rather than ad-hoc responses.',
            'exemplary': 'High interactional resilience: rapidly classifies the failure type, applies the appropriate recovery strategy, restores workflow momentum, and extracts a learning that improves the failure-prevention strategy going forward.',
        },
        'negative_criteria': [
            'Treats AI failures as workflow-ending events rather than recoverable situations',
            'Uses the same recovery strategy for all types of AI failure',
        ],
        'strength_map': _STR5,
    },

    'CA-05': {
        'dimension': 'CA',
        'title': "Systematically closes the feedback loop to progressively align AI performance",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Accepts AI errors without closing the feedback loop — does not provide corrections, outcome data, or behavioral observations back to the session.",
            'minimal':   'Provides feedback to AI after a significant error but does not systematically close the feedback loop.',
            'partial':   'Regularly provides corrections and outcome data back to AI during the session.',
            'clear':     'Proactively closes the feedback loop — feeds error logs, outcome data, corrections, and observations back into the session to progressively align AI performance with objectives.',
            'exemplary': 'Systematic terminal feedback provisioning: maintains a feedback discipline throughout the session; feeds all errors, corrections, performance signals, and goal-alignment observations back into AI context; explicitly uses this feedback to progressively improve AI performance over the session.',
        },
        'negative_criteria': [
            'Never feeds error or correction information back to AI to improve subsequent outputs',
            'Treats each AI turn as independent from prior performance signals',
        ],
        'strength_map': _STR5,
    },

    'CA-06': {
        'dimension': 'CA',
        'title': "Maintains a dynamic, evidence-based trust model that updates on session performance signals",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Applies a fixed trust level to AI output regardless of performance signals — neither updating trust upward on reliable performance nor downward on failure.',
            'minimal':   'Makes one trust update in response to a clear AI failure but does not maintain a dynamic trust model.',
            'partial':   'Adjusts trust in response to major performance signals but does so coarsely and inconsistently.',
            'clear':     'Maintains a dynamic, evidence-based trust model — adjusting deference to AI outputs based on real-time performance signals in the current session.',
            'exemplary': 'Calibrated adaptive trust management: tracks AI performance across multiple dimensions, adjusts trust proportionally to evidence quality and stakes level, prevents both chronic over-trust and paralyzing under-trust, and maintains a current trust estimate that is accurate and responsive to session performance.',
        },
        'negative_criteria': [
            'Never recalibrates trust in response to AI performance signals',
            'Applies the same trust level to all AI outputs regardless of domain or recent accuracy',
        ],
        'strength_map': _STR5,
    },

    'CA-07': {
        'dimension': 'CA',
        'title': "Actively resists AI goal drift and maintains fidelity to original human intent",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Allows AI's reframing and simplification to gradually redirect the conversation away from the original human objective.",
            'minimal':   'Notices goal drift after it has occurred but does not prevent it.',
            'partial':   "Re-anchors to the original goal at least once when detecting drift.",
            'clear':     "Actively maintains fidelity to the original human intent across extended multi-turn interactions — explicitly resisting AI's tendency to reframe, simplify, or redirect toward a different objective.",
            'exemplary': "Systematic goal integrity maintenance: documents the original intent, monitors each AI response for goal drift or reframing, immediately corrects any detected drift, ends the session with a verified alignment check between final output and original objective.",
        },
        'negative_criteria': [
            "Allows AI to reframe the goal over time without resistance",
            "Treats AI's simplification of objectives as helpful clarification rather than drift",
        ],
        'strength_map': _STR5,
    },

    'CA-08': {
        'dimension': 'CA',
        'title': "Continuously monitors own cognitive state for biases and attentional drift during AI collaboration",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Shows no awareness of own cognitive state during AI collaboration — does not notice attentional drift, emerging biases, or degraded judgment quality.',
            'minimal':   'Notices cognitive drift or bias after it has affected a decision.',
            'partial':   'Maintains real-time awareness of at least one aspect of own cognitive state during AI collaboration.',
            'clear':     'Demonstrates continuous metacognitive self-monitoring — maintains real-time awareness of own cognitive state, biases, attentional drift, and judgment quality during deep AI collaboration.',
            'exemplary': 'Active metacognitive governance: continuously monitors own full cognitive state during collaboration, identifies emerging biases, attentional drift, and judgment degradation before they propagate into output, applies self-correction strategies in real time.',
        },
        'negative_criteria': [
            'Never notices when AI collaboration is introducing cognitive biases',
            'Treats own judgment during AI collaboration as unaffected by the collaboration process',
        ],
        'strength_map': _STR5,
    },

    'CA-09': {
        'dimension': 'CA',
        'title': "Maintains auditability-grade workflow documentation throughout the session",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Maintains no documentation of workflow decisions, AI contributions, or reasoning steps during the session.',
            'minimal':   'Maintains informal notes but at a level of detail insufficient for retrospective audit or attribution.',
            'partial':   'Maintains documentation sufficient to reconstruct the main decisions and AI contributions.',
            'clear':     'Maintains a workflow record that supports retrospective audit, intellectual attribution, third-party explanation, and basic legal defensibility.',
            'exemplary': 'Rigorous auditability discipline: maintains a complete, real-time record of all significant decisions, AI inputs and outputs, reasoning steps, and attribution — producing documentation sufficient for full forensic audit, intellectual attribution, and legal defensibility on demand.',
        },
        'negative_criteria': [
            'Cannot reconstruct the reasoning behind key decisions made during the session',
            'Relies on memory rather than contemporaneous documentation for attribution',
        ],
        'strength_map': _STR5,
    },

    'CA-10': {
        'dimension': 'CA',
        'title': "Governs selective attention by rejecting all AI scope expansions and tangential content",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Follows AI-generated scope expansions, tangential elaborations, and irrelevant content without resistance — drifting from the core objective.',
            'minimal':   'Occasionally refocuses on the core objective when AI wanders but does not apply systematic attention governance.',
            'partial':   'Explicitly rejects one or more AI scope expansions and maintains deliberate focus on the core objective.',
            'clear':     'Applies consistent selective attention governance — actively resists all AI-generated scope expansions and irrelevant elaborations, maintaining deliberate focus on the core objective throughout.',
            'exemplary': 'Systematic attention governance: at each AI response, explicitly evaluates all content for relevance to the core objective; rejects all scope expansions and tangential content; maintains a strict, documented focus on the core objective from initiation to completion.',
        },
        'negative_criteria': [
            'Follows AI topic expansions that are interesting but irrelevant to the objective',
            'Never explicitly rejects AI content that pulls away from the core goal',
        ],
        'strength_map': _STR5,
    },

    'CA-11': {
        'dimension': 'CA',
        'title': "Regulates affect under AI failure to maintain strategic decision quality",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Human's strategic decision quality degrades visibly after AI failures — frustration or helplessness drives irrational prompt choices and abandoned workflows.",
            'minimal':   'Maintains composure on the surface but underlying strategy becomes less systematic after repeated AI failures.',
            'partial':   'Explicitly regulates own response to AI failure — maintains a deliberate strategy after frustration.',
            'clear':     'Demonstrates consistent affective regulation under AI failure — prevents frustration, helplessness, or impatience from degrading strategic decision quality and prompt rationality.',
            'exemplary': 'Systematic affective regulation: identifies emotional responses to AI failure, applies explicit regulation strategies, maintains full strategic rationality throughout repeated failures, and extracts actionable insights rather than emotional reactions from each failure.',
        },
        'negative_criteria': [
            'Abandons or degrades strategy in response to AI failures',
            'Lets frustration with AI errors drive irrational prompting behavior',
        ],
        'strength_map': _STR5,
    },

    'CA-12': {
        'dimension': 'CA',
        'title': "Applies durable cross-session AI interaction heuristics to improve current performance",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Treats each AI interaction as isolated — does not extract durable insights, heuristics, or failure patterns from prior interactions.',
            'minimal':   'Recalls one prior AI interaction pattern and applies it to the current session.',
            'partial':   'Applies at least two generalizable heuristics derived from prior AI interactions to the current session strategy.',
            'clear':     'Explicitly draws on a repertoire of prior AI interaction patterns, failure modes, and workflow heuristics — applying durable cross-session learning to the current task.',
            'exemplary': 'Systematic cross-session transfer: maintains an evolving repertoire of AI interaction insights; explicitly tests prior heuristics for applicability to the current task; updates the repertoire with new patterns from the current session; demonstrates measurable improvement in interaction effectiveness attributable to prior session learning.',
        },
        'negative_criteria': [
            'Repeats known failure patterns from prior AI interactions without updating strategy',
            'Never deliberately applies learning from past AI sessions to current work',
        ],
        'strength_map': _STR5,
    },

    'CA-13': {
        'dimension': 'CA',
        'title': "Preserves a defensible account of own intellectual contribution throughout AI collaboration",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Produces high-volume AI-assisted work without maintaining any distinct sense of own intellectual contribution, voice, or epistemic ownership.',
            'minimal':   'Makes periodic gestures toward intellectual ownership but cannot clearly identify what is distinctly their contribution versus AI.',
            'partial':   "Maintains a clear sense of own intellectual contribution and creative voice despite deep AI collaboration.",
            'clear':     'Actively preserves intellectual identity — maintains a defensible account of own conceptual contribution, creative voice, and epistemic ownership throughout deep AI collaboration.',
            'exemplary': "Systematic identity authorship discipline: continuously tracks own versus AI's conceptual contributions; maintains an explicit record of creative decisions, intellectual innovations, and reasoning; can articulate a clear, defensible account of authorial identity and contribution even in AI-intensive work.",
        },
        'negative_criteria': [
            'Cannot distinguish own intellectual contributions from AI contributions in the final product',
            'Treats AI-assisted work as equally owned by human and AI without maintaining own perspective',
        ],
        'strength_map': _STR5,
    },

    'CA-14': {
        'dimension': 'CA',
        'title': "Detects recurring AI failure patterns at first recurrence and adjusts strategy proactively",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Does not notice recurring failure patterns or systematic capability limitations in AI's current-session responses — treats each failure as isolated.",
            'minimal':   'Notices a pattern after the third or fourth occurrence but not earlier.',
            'partial':   'Identifies a recurring AI failure pattern and names it explicitly during the session.',
            'clear':     "Demonstrates real-time pattern recognition — detects systematic biases and capability limitations in AI's current-session responses and adjusts interaction strategy proactively.",
            'exemplary': 'Active intra-session pattern learning: detects recurring failure patterns at their first recurrence, classifies the pattern type, adjusts interaction strategy immediately, and tracks whether the adjustment successfully prevents further occurrences.',
        },
        'negative_criteria': [
            'Treats each AI failure as a one-off event rather than part of a pattern',
            'Never adjusts interaction strategy based on observed AI failure modes',
        ],
        'strength_map': _STR5,
    },

    'CA-15': {
        'dimension': 'CA',
        'title': "Actively resists AI sycophancy by treating AI validation as epistemically unreliable",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Treats AI agreement and validation as genuine independent confirmation — does not recognize that AI systems are structurally trained to affirm user views.",
            'minimal':   'Has heard of AI sycophancy but does not actively account for it when receiving AI validation.',
            'partial':   'Explicitly acknowledges that AI validation is not independent confirmation and discounts it for at least one important decision.',
            'clear':     'Consistently treats AI agreement as epistemically unreliable — actively solicits adversarial challenge and disconfirming evidence rather than accepting AI validation.',
            'exemplary': "Systematic sycophancy resistance: explicitly instructs AI to take an adversarial or devil's advocate position; evaluates AI challenges rather than agreements as the primary input; maintains an explicit discipline of treating AI validation as structurally worthless independent confirmation.",
        },
        'negative_criteria': [
            'Uses AI agreement as evidence that an idea is correct',
            'Never tests ideas by specifically asking AI to challenge rather than support them',
        ],
        'strength_map': _STR5,
    },

    'CA-16': {
        'dimension': 'CA',
        'title': "Forms own hypothesis before reading AI output to preserve epistemic independence",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      'Reads AI output before forming own hypothesis, judgment, or prediction — AI framing anchors and displaces independent human thought.',
            'minimal':   'Occasionally forms a prior hypothesis before reading AI output but does not apply this as a discipline.',
            'partial':   'Regularly forms own hypothesis before reading AI output on high-stakes decisions.',
            'clear':     'Maintains a disciplined practice of forming own hypothesis, judgment, or prediction before reading AI output on all non-trivial decisions.',
            'exemplary': 'Systematic pre-generation epistemic independence: before each AI response, explicitly formulates own position; reads AI output as a challenge to that position rather than a replacement; identifies where AI and human positions diverge; preserves an independent baseline that anchors judgment against AI anchoring effects.',
        },
        'negative_criteria': [
            'Reads AI output before thinking through the problem independently',
            'Uses AI output as a substitute for forming own judgment on consequential matters',
        ],
        'strength_map': _STR5,
    },

    'CA-17': {
        'dimension': 'CA',
        'title': "Sustains consistent critical scrutiny from first to last output in a session",
        'scale_levels': _SCALE5,
        'anchors': {
            'none':      "Scrutiny quality declines markedly across the session — late outputs receive dramatically less critical evaluation than those produced at the start.",
            'minimal':   'Shows some scrutiny decline across the session but occasionally re-engages critical evaluation on high-stakes content.',
            'partial':   'Makes deliberate efforts to maintain scrutiny consistency but shows measurable decline on routine content late in the session.',
            'clear':     'Maintains consistent critical scrutiny throughout the session — late outputs receive the same depth of evaluation as early ones, with no significant temporal degradation.',
            'exemplary': 'Systematic vigilance sustainment: explicitly monitors own scrutiny intensity over session duration; applies deliberate re-engagement strategies (checkpoints, self-audit pauses) when fatigue or habituation is detected; produces a session where scrutiny consistency is maintained from first output to last.',
        },
        'negative_criteria': [
            'Scrutinizes early outputs thoroughly but accepts late outputs uncritically',
            'Treats scrutiny fatigue as unavoidable rather than addressable through deliberate re-engagement',
        ],
        'strength_map': _STR5,
    },

}  # end RUBRIC_BANK


# ── derived lookups (used by A2/A3 pipeline wiring) ───────────────────────────

#: neuron_id → parent dimension key (for firings dict routing in normalize.py)
DIM_OF: dict[str, str] = {nid: rb['dimension'] for nid, rb in RUBRIC_BANK.items()}

#: quick membership test
JUDGE_TYPED_NEURONS: FrozenSet[str] = frozenset(RUBRIC_BANK.keys())


def get_rubric(neuron_id: str) -> dict:
    """Return the rubric for a judge-typed neuron.

    Raises KeyError if neuron_id is not judge-typed. For deterministic neurons
    call their extractor directly — adding a rubric here would create the
    double-count hazard in normalize.py (L2).
    """
    if neuron_id in DETERMINISTIC_NEURONS:
        raise KeyError(
            f"{neuron_id!r} is deterministic — no judge rubric exists "
            "(adding one would double-count in the normalizer)"
        )
    return RUBRIC_BANK[neuron_id]  # KeyError if unknown


def list_all_neurons() -> list[str]:
    """Sorted list of all judge-typed neuron IDs (98 neurons)."""
    return sorted(RUBRIC_BANK.keys())


def neurons_by_dimension(dimension: str) -> list[str]:
    """Sorted list of judge-typed neuron IDs for a given dimension."""
    return sorted(nid for nid, rb in RUBRIC_BANK.items() if rb['dimension'] == dimension)


def validate_contract() -> None:
    """Assert no neuron appears in both judge and deterministic sets (L2 guard).
    Call once at module load or in tests.
    """
    overlap = JUDGE_TYPED_NEURONS & DETERMINISTIC_NEURONS
    assert not overlap, f"Contract violation: neurons in both sets: {overlap}"


validate_contract()


if __name__ == '__main__':
    print(f"Rubric bank: {len(RUBRIC_BANK)} judge-typed neurons")
    for dim in ['EC', 'PR', 'AL', 'ES', 'CS', 'CD', 'AUI', 'CA']:
        ns = neurons_by_dimension(dim)
        print(f"  {dim}: {len(ns)} neurons — {', '.join(ns)}")
    print(f"\nDeterministic neurons (no rubric): {sorted(DETERMINISTIC_NEURONS)}")
    print("\nContract validation: PASSED")
