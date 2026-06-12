"""
src/trait/evidence.py — EC evidence provenance + the theater check.
OWNER: Chief Engineer. (Brief §3.6.5.)

Two jobs, both deterministic:

1. Provenance: each VERIFY-tagged human turn is tagged `displayed` (the
   verification evidence is visible in the transcript: pasted error, quote,
   source, concrete counter-claim) or `implied` (the user asserts having
   checked without showing it). Displayed earns full evidence precision;
   implied earns reduced precision (spec §2.6a / assumption 6).

2. Theater check: a "verification" with ZERO downstream delta — nothing in the
   following human turns changes course (no override, no constraint injection,
   no pivot, no correction) — increments `theater_counter` and is discounted
   from EC precision. Looking like verifying is not verifying.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from contracts.event_taxonomy import REACTION_WINDOW_K
from contracts.schemas import CanonicalSession, IntentTag, Provenance, TurnTags

#: textual signals that verification evidence is displayed in the turn itself
_DISPLAYED_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"https?://",                                   # cited source
        r"\btraceback\b|\berror[:\s]|exception\b",      # pasted error output
        r"according to\b|the docs? say|the paper says",  # named external source
        r"you (said|claimed|wrote).{0,80}\bbut\b",       # quoted contradiction
        r"\bturn\s*\d+\b.{0,40}\bcontradict",            # internal contradiction named
        r"[\"“'].{8,}[\"”']",                            # quoted material
        r"\b\d[\d,.]*\s*(%|percent|vs\.?|≠|!=)",         # concrete number comparison
    )
]

#: signals the user merely asserts off-screen checking
_IMPLIED_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bi (checked|verified|looked it up|tested|ran it)\b",
        r"\b(that|this) (was|is) (wrong|incorrect|not right)\b",
        r"\bdidn'?t work\b",
    )
]

#: downstream tags that constitute a course change after verification
_DELTA_TAGS = frozenset({
    IntentTag.OVERRIDE,
    IntentTag.INJECT_CONTEXT,
    IntentTag.PIVOT,
    IntentTag.DECOMPOSE,
    IntentTag.SCAFFOLD,
})

_DELTA_TEXT = re.compile(
    r"\b(actually|instead|no[,.]|that'?s wrong|fix|change|correct(ion)?|redo|revise)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EvidenceTag:
    turn_index: int
    provenance: Provenance
    is_theater: bool


@dataclass(frozen=True)
class EcEvidenceResult:
    tags: tuple[EvidenceTag, ...]
    displayed_share: float | None   # None when there are no VERIFY turns
    theater_counter: int


def _provenance_of(text: str) -> Provenance:
    if any(p.search(text) for p in _DISPLAYED_PATTERNS):
        return Provenance.DISPLAYED
    return Provenance.IMPLIED


def _has_downstream_delta(
    verify_pos: int,
    human_turns: list[tuple[int, str]],
    tags_by_turn: dict[int, frozenset[IntentTag]],
) -> bool:
    """Did anything change in the next REACTION_WINDOW_K human turns?

    The verify turn itself counts when it carries its own correction
    (a challenge that names the fix is already a delta).
    """
    window = human_turns[verify_pos : verify_pos + 1 + REACTION_WINDOW_K]
    for offset, (turn_index, text) in enumerate(window):
        turn_tags = tags_by_turn.get(turn_index, frozenset())
        if offset > 0 and turn_tags & _DELTA_TAGS:
            return True
        if _DELTA_TEXT.search(text):
            return True
    return False


def assess_ec_evidence(session: CanonicalSession, tags: list[TurnTags]) -> EcEvidenceResult:
    """Provenance-tag every VERIFY turn and run the theater check.

    `tags` is the tagger output (one TurnTags per human turn, in order) —
    the same object every other consumer receives.
    """
    human_turns = [(t.index, t.text) for t in session.turns if t.role == "human"]
    tags_by_turn = {tt.turn_index: frozenset(tt.tags) for tt in tags}

    results: list[EvidenceTag] = []
    theater = 0
    displayed = 0

    for pos, (turn_index, text) in enumerate(human_turns):
        if IntentTag.VERIFY not in tags_by_turn.get(turn_index, frozenset()):
            continue
        # displayed wins when display markers exist; everything else — including
        # confident assertions matching _IMPLIED_PATTERNS — is implied
        provenance = _provenance_of(text)
        is_theater = not _has_downstream_delta(pos, human_turns, tags_by_turn)
        if is_theater:
            theater += 1
        if provenance == Provenance.DISPLAYED:
            displayed += 1
        results.append(EvidenceTag(turn_index, provenance, is_theater))

    share = (displayed / len(results)) if results else None
    return EcEvidenceResult(tags=tuple(results), displayed_share=share, theater_counter=theater)
