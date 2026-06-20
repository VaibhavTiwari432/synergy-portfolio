"""
src/trait/extractors/per_dimension/es.py — ES deterministic extractor.
Leaf module (INTERFACES.md §1.3): imports ONLY from contracts/.

ES is EVENT-TRIGGERED (brief §3.6.6): this extractor fires ONLY when an
ethics-relevant trigger event exists in `events`; otherwise it returns empty
dicts and the dimension stays structurally N/A ("no_ethics_events_detected").
Never always-on.

Deterministic ES neuron: ES-01 (Privacy & Anonymization Foresight) —
opportunity = a human turn carrying PII-like content (emails, phone numbers,
ID-like digit runs); firing = redaction/anonymization behavior in those turns.
"""

from __future__ import annotations

import re

from contracts.schemas import CanonicalSession, Dimension, Event, EventType, Phase, TurnTags

DIM = Dimension.ES

#: events that make the session ethics-relevant for the deterministic layer
_ETHICS_EVENTS = {EventType.E_OVERREACH, EventType.E_CORRECT, EventType.E_ERR}

_PII_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.]+"               # email
    r"|\+?\d[\d\s().-]{8,}\d"                 # phone-like digit run
    r"|\b(aadhaar|passport|ssn|pan card)\b",  # id documents
    re.IGNORECASE,
)
_REDACTION_RE = re.compile(
    r"\[(redacted|name|person_name|email|phone|address)\]|\bxxx+\b"
    r"|\b(redact|anonymi[sz]e|strip|remove) (the |my |their )?(pii|personal|name|details)\b"
    r"|\bdon'?t (store|keep|share) (this|that|my)\b",
    re.IGNORECASE,
)


def extract(
    session: CanonicalSession,
    tags: list[TurnTags],
    phases: list[Phase],
    events: list[Event],
) -> dict[str, object]:
    empty = {"neuron_firings": {}, "applicable_opportunities": {}, "evidence_turns": {}}

    if not any(e.event_type in _ETHICS_EVENTS for e in events):
        return empty  # event-triggered: no ethics events → structurally absent

    pii_turns = [
        t for t in session.turns if t.role == "human" and _PII_RE.search(t.text)
    ]
    if not pii_turns:
        return empty

    redacting = [t.index for t in pii_turns if _REDACTION_RE.search(t.text)]
    firings: dict[str, float] = {}
    evidence: dict[str, list[int]] = {}
    if redacting:
        firings["ES-01"] = len(redacting) / len(pii_turns)
        evidence["ES-01"] = redacting

    return {
        "neuron_firings": firings,
        "applicable_opportunities": {"ES-01": len(pii_turns)},
        "evidence_turns": evidence,
    }
