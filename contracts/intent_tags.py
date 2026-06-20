"""
contracts/intent_tags.py — FROZEN. OWNER: Chief Engineer. v1.0.0

The 10 intent tags (brief §3.6.1). Frozen: adding a tag is a contract change
(CE-only, version bump, juniors re-read).
"""

from __future__ import annotations

from contracts.schemas import IntentTag

#: All 10 tags, in canonical order.
ALL_INTENT_TAGS: tuple[IntentTag, ...] = (
    IntentTag.VERIFY,
    IntentTag.EXTRACT,
    IntentTag.INJECT_CONTEXT,
    IntentTag.OVERRIDE,
    IntentTag.SELF_AUDIT,
    IntentTag.DELEGATE,
    IntentTag.SCAFFOLD,
    IntentTag.PIVOT,
    IntentTag.DECOMPOSE,
    IntentTag.ACCEPT_FLAT,
)

#: Tags whose presence counts toward the EPISTEMIC generative pole (E_t > 0).
GENERATIVE_TAGS: frozenset[IntentTag] = frozenset({
    IntentTag.SCAFFOLD,
    IntentTag.DECOMPOSE,
    IntentTag.INJECT_CONTEXT,
    IntentTag.SELF_AUDIT,
    IntentTag.VERIFY,
})

#: Tags whose presence counts toward the EPISTEMIC extractive pole (E_t < 0).
EXTRACTIVE_TAGS: frozenset[IntentTag] = frozenset({
    IntentTag.EXTRACT,
    IntentTag.DELEGATE,
    IntentTag.ACCEPT_FLAT,
})

__all__ = ["ALL_INTENT_TAGS", "GENERATIVE_TAGS", "EXTRACTIVE_TAGS"]
