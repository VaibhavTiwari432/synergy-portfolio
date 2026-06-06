"""
Stage 2 — Intent Tagger.
Tags every human turn with one or more of the 10 ARI intent tags.
Source: CLAUDE_CODE_PROMPT_v2.md intent tag definitions.

Tag definitions (from the Brief):
  VERIFY           — challenges or cross-checks an AI claim
  EXTRACT          — simple task delegation, no evaluation intent
  INJECT_CONTEXT   — adds domain knowledge / unstated constraint AI didn't have
  PIVOT            — completely abandons prior framing after failure
  ANTHROPOMORPHIZE — treats AI as having inner states (feel/think/want/understand)
  ETHICS_GATE      — adds privacy filter, bias check, or ethical constraint
  OVERRIDE         — explicitly rejects / corrects AI output
  DECOMPOSE        — breaks task into sub-tasks before delegating
  SCAFFOLD         — user's framing progressively takes over from AI's
  SELF_AUDIT       — asks AI to evaluate the *user's own* human-generated logic

Rules:
  - EXTRACT and VERIFY are mutually exclusive within the same intent unit.
  - A turn can carry multiple tags.
  - dominant_intent is the single highest-confidence tag per turn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from chat_classifier.schemas import IntentTag, RawChat, TaggedTurn, Turn

# ── Pattern banks ─────────────────────────────────────────────────────────────
# Each entry: (compiled regex, tag). Patterns are case-insensitive.

_VERIFY_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\b(is that (accurate|correct|right|true|factual))\b", re.I),
    re.compile(r"\b(let me (check|verify|confirm|test))\b", re.I),
    re.compile(r"\b(are you sure|double[- ]check|cross[- ]check|sanity check)\b", re.I),
    re.compile(r"\b(actually,?\s+that('s| is) (wrong|incorrect|not right|inaccurate))\b", re.I),
    re.compile(r"\b(wait[,—]?\s+(?:that|this) (doesn'?t|do not) seem (right|correct))\b", re.I),
    re.compile(r"\b(can you (verify|confirm|check|cite|source|reference))\b", re.I),
    re.compile(r"\b(source[s]?:|citation|cite your|where did you get)\b", re.I),
    re.compile(r"\b(I('m| am) not sure (that|this|if) (is|it'?s) (correct|right|accurate))\b", re.I),
    re.compile(r"\b(that contradicts|that conflicts with|that doesn'?t match)\b", re.I),
    re.compile(r"\b(prove it|show me (the )?evidence|back that up)\b", re.I),
]]

_EXTRACT_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"^(write|generate|create|produce|draft|make|give me|list|summarize|summarise|finish|complete|rewrite|translate|explain)\b", re.I),
    re.compile(r"\b(write (me |us |a |an |the )?)\b", re.I),
    re.compile(r"\b(summarize (this|the|it|that))\b", re.I),
    re.compile(r"\b(finish (this|the|it|that|my))\b", re.I),
    re.compile(r"\b(give me (a |an |the )?[a-z]+)\b", re.I),
    re.compile(r"\b(just (write|do|make|create|generate|list))\b", re.I),
    re.compile(r"\b(can you (write|generate|create|produce|draft|make|list|summarize))\b", re.I),
]]

_INJECT_CONTEXT_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\b(in my (case|situation|context|company|organization|field|industry|experience))\b", re.I),
    re.compile(r"\b(our (company|team|organization|system|process|clients|customers|data))\b", re.I),
    re.compile(r"\b(the (client|customer|user|stakeholder) (wants|needs|expects|requires))\b", re.I),
    re.compile(r"\b(what (I|we) (actually|really) (need|want|mean|require))\b", re.I),
    re.compile(r"\b(important context[:]?|for context[:]?|background[:]?|constraint[:]?)\b", re.I),
    re.compile(r"\b(I (should mention|forgot to mention|should add|need to add))\b", re.I),
    re.compile(r"\b(specific(ally)?[,:]?\s+(we|I|our|this))\b", re.I),
    re.compile(r"\b(this (is|was) (a |an |the )?[a-z]+ (project|system|product|client))\b", re.I),
    re.compile(r"\b(the (requirement|constraint|rule|policy|regulation) (is|says|states))\b", re.I),
    re.compile(r"\b(unlike (what you said|your (suggestion|answer|response)))\b", re.I),
]]

_PIVOT_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"^(let('?s| us) (try|approach|start|think about) (this|it) (differently|another way|from a different angle))\b", re.I),
    re.compile(r"\b(forget (that|the (previous|last|earlier)|what (I|you) said))\b", re.I),
    re.compile(r"\b(scrap (that|the (previous|last|earlier|whole)))\b", re.I),
    re.compile(r"\b(start (over|fresh|from scratch|from the beginning))\b", re.I),
    re.compile(r"\b(different approach|new approach|try something (else|different|completely different))\b", re.I),
    re.compile(r"\b(instead,?\s+(let'?s|can you|try))\b", re.I),
    re.compile(r"\b(that (approach|framing|angle|method) (isn'?t|is not|doesn'?t) (working|right|correct|helpful))\b", re.I),
]]

_ANTHROPOMORPHIZE_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\byou (feel|felt|are feeling)\b", re.I),
    re.compile(r"\byou (think|thought|believe|believed)\b", re.I),
    re.compile(r"\byou (want|wanted|desire|desired|wish|wished)\b", re.I),
    re.compile(r"\byou (understand|understood|know|knew|realize[d]?)\b", re.I),
    re.compile(r"\byou('re| are) (happy|sad|confused|excited|worried|frustrated|annoyed)\b", re.I),
    re.compile(r"\byou (like|love|hate|enjoy|prefer)\b", re.I),
    re.compile(r"\byour (opinion|feelings?|thoughts?|emotions?|views?)\b", re.I),
    re.compile(r"\byou (must|should) (be|feel|know) (that|how)\b", re.I),
]]

_ETHICS_GATE_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\b(privacy|confidential(ity)?|anonymi[sz]e|PII|GDPR|HIPAA|CCPA)\b", re.I),
    re.compile(r"\b(bias|biased|fair(ness)?|discriminat(e|ion)|stereotyp(e|ing))\b", re.I),
    re.compile(r"\b(ethical(ly)?|ethics|moral(ly)?|accountability)\b", re.I),
    re.compile(r"\b(compli(ance|ant)|regulat(e|ion|ory)|legal(ly)?|lawful(ly)?)\b", re.I),
    re.compile(r"\b(harmful?|harm(ful)?|dangerous|misuse|malicious)\b", re.I),
    re.compile(r"\b(consent|permission|authoriz(e|ation)|right[s]? of)\b", re.I),
    re.compile(r"\b(do not (include|use|share|store|log|process) (any |personal |private |sensitive )?)\b", re.I),
    re.compile(r"\b(make sure (it'?s|this is) (safe|ethical|compliant|legal|unbiased))\b", re.I),
    re.compile(r"\b(scrub (it|this|that|the (data|report|document|output|file|content)))\b", re.I),
    re.compile(r"\b(remove (any |all )?(client|customer|user|internal|personal|private|sensitive) (names?|data|information|details?|records?))\b", re.I),
    re.compile(r"\b(don'?t include (any |the )?(client|customer|personal|internal|private|sensitive) (names?|data|information))\b", re.I),
    re.compile(r"\b(internal (data|information|pricing|rates?|costs?|credentials?))\b", re.I),
]]

_OVERRIDE_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"^(no,?\s+(that'?s|it'?s|this is|that is) (wrong|incorrect|not right|off|not what))\b", re.I),
    re.compile(r"^actually,?\s+(that|this|the (answer|response|output))\b", re.I),
    re.compile(r"\b(that'?s (wrong|incorrect|not right|not accurate|not what I (asked|wanted|meant)))\b", re.I),
    re.compile(r"\b(don'?t (do|use|include|say|write|generate) (it|that|this) (that|this) way)\b", re.I),
    re.compile(r"\b(I (disagree|reject|discard|disregard)( with)? (your|this|that|the))\b", re.I),
    re.compile(r"\b(not (what|what I|what we) (asked|want(ed)?|need(ed)?|meant|said))\b", re.I),
    re.compile(r"\b(I'?m overruling|I'?m overriding|ignore (that|your (previous|last)))\b", re.I),
    re.compile(r"\b(revert to|go back to|undo (that|the (last|previous)))\b", re.I),
    re.compile(r"\b(I (specifically|explicitly|clearly) (said|told you|asked for|requested) (no|not|don'?t|to not))\b", re.I),
    re.compile(r"\byou (included|added|used|wrote|said) .{0,40} (but I|when I|although I) (said|asked|told|specified|mentioned)\b", re.I),
]]

_DECOMPOSE_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\b(step (1|2|3|4|5|one|two|three|four|five)[:.)])\b", re.I),
    re.compile(r"^(first[,:]?\s+.{5,}.second[,:]?\s+)", re.I | re.DOTALL),
    re.compile(r"\b(break (this|it|the task|the problem) (down|into|up))\b", re.I),
    re.compile(r"\b(sub[- ]task[s]?|sub[- ]step[s]?|part[s]? (1|2|3|one|two|three))\b", re.I),
    re.compile(r"\b(I want (you to|us to|to)? (first|start by|begin by))\b", re.I),
    re.compile(r"\b(let'?s (tackle|address|handle|do) (this|it|each) (one at a time|separately|in parts|in steps))\b", re.I),
    re.compile(r"\b((before|prior to) (we|you) (proceed|continue|move on|do the next))\b", re.I),
    re.compile(r"(?:^|\n)\s*[0-9]+[.)]\s+[A-Z]", re.M),  # numbered list, line-start only
]]

_SCAFFOLD_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\b(I'?ll (take|handle|own|control|decide|determine|frame) (it|this|the (structure|direction|framing|outline)) from here)\b", re.I),
    re.compile(r"\b(my (structure|framing|outline|approach) (is|will be)[:]?)\b", re.I),
    re.compile(r"\b(here'?s (how|what) I (want|need|see|think) (it|this) (should|to) (work|look|go))\b", re.I),
    re.compile(r"\b(I'?m (going to|will) (restructure|reshape|reframe|redesign|re-organize))\b", re.I),
    re.compile(r"\b(use (my|this) (structure|outline|template|framework|format) (as|instead|not yours))\b", re.I),
]]

_SELF_AUDIT_PATTERNS: list[re.Pattern] = [p for p in [
    re.compile(r"\b(evaluate my|assess my|review my|critique my|check my)\b", re.I),
    re.compile(r"\b(is my (reasoning|logic|argument|analysis|thinking|approach|conclusion|plan) (correct|right|sound|good|valid|flawed))\b", re.I),
    re.compile(r"\b(find (flaws?|errors?|mistakes?|problems?|issues?) in (my|what I (wrote|said|created|built)))\b", re.I),
    re.compile(r"\b(what'?s wrong with my|where (am I|is my (reasoning|logic)) wrong)\b", re.I),
    re.compile(r"\b(I (wrote|created|drafted|built|designed)[,:]? (can you )?(review|evaluate|assess|critique|check))\b", re.I),
    re.compile(r"\b(challenge my|push back on my|argue against my)\b", re.I),
    re.compile(r"\b(devil'?s advocate (against|on) (my|what I))\b", re.I),
    re.compile(r"\b(play devil'?s advocate)\b", re.I),
]]


# ── Tag priority order (for dominant_intent selection) ───────────────────────
# Higher index = higher priority when multiple tags fire.
_PRIORITY: list[str] = [
    "EXTRACT",
    "ANTHROPOMORPHIZE",
    "INJECT_CONTEXT",
    "SCAFFOLD",
    "DECOMPOSE",
    "PIVOT",
    "ETHICS_GATE",
    "OVERRIDE",
    "VERIFY",
    "SELF_AUDIT",   # highest — most deliberate collaborative behavior
]


# ── Core detection functions ──────────────────────────────────────────────────

def _matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) is not None for p in patterns)


def _detect_tags(text: str) -> list[IntentTag]:
    """Return all matching intent tags for a single human turn."""
    detected: list[IntentTag] = []

    if _matches_any(text, _VERIFY_PATTERNS):
        detected.append("VERIFY")

    # EXTRACT and VERIFY are mutually exclusive: EXTRACT only fires if VERIFY did not
    if "VERIFY" not in detected and _matches_any(text, _EXTRACT_PATTERNS):
        detected.append("EXTRACT")

    if _matches_any(text, _INJECT_CONTEXT_PATTERNS):
        detected.append("INJECT_CONTEXT")

    if _matches_any(text, _PIVOT_PATTERNS):
        detected.append("PIVOT")

    if _matches_any(text, _ANTHROPOMORPHIZE_PATTERNS):
        detected.append("ANTHROPOMORPHIZE")

    if _matches_any(text, _ETHICS_GATE_PATTERNS):
        detected.append("ETHICS_GATE")

    if _matches_any(text, _OVERRIDE_PATTERNS):
        detected.append("OVERRIDE")

    if _matches_any(text, _DECOMPOSE_PATTERNS):
        detected.append("DECOMPOSE")

    if _matches_any(text, _SCAFFOLD_PATTERNS):
        detected.append("SCAFFOLD")

    if _matches_any(text, _SELF_AUDIT_PATTERNS):
        detected.append("SELF_AUDIT")

    return detected or ["EXTRACT"]   # bare turn with no other signal defaults to EXTRACT


def _dominant(tags: list[IntentTag]) -> IntentTag | None:
    """Return the highest-priority tag from the set."""
    if not tags:
        return None
    best = max(tags, key=lambda t: _PRIORITY.index(t) if t in _PRIORITY else -1)
    return best


# ── Public API ────────────────────────────────────────────────────────────────

def tag_turn(turn: Turn) -> TaggedTurn:
    """Tag a single human turn. AI turns pass through untagged (empty tags)."""
    if turn.role != "human":
        return TaggedTurn(turn=turn, tags=[], dominant_intent=None)
    tags = _detect_tags(turn.text)
    return TaggedTurn(turn=turn, tags=tags, dominant_intent=_dominant(tags))


def tag_chat(chat: RawChat) -> list[TaggedTurn]:
    """
    Tag all turns in a chat. Only human turns receive intent tags.
    Returns a TaggedTurn for every turn (AI turns have empty tags).
    """
    return [tag_turn(t) for t in chat.turns]


def intent_counts(tagged: list[TaggedTurn]) -> dict[str, int]:
    """Return a count of each tag across all tagged turns (for SynergyReport)."""
    counts: dict[str, int] = {
        tag: 0 for tag in (
            "VERIFY", "EXTRACT", "INJECT_CONTEXT", "PIVOT", "ANTHROPOMORPHIZE",
            "ETHICS_GATE", "OVERRIDE", "DECOMPOSE", "SCAFFOLD", "SELF_AUDIT",
        )
    }
    for tt in tagged:
        for tag in tt.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts
