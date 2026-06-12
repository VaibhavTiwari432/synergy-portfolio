"""
src/claims/rungs.py — rung ordering + tier ceilings. OWNER: Chief Engineer.
(Brief §3.2, §3.10; spec §0.2.)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from contracts.schemas import Rung, Tier

_CLAIMS_PATH = Path(__file__).resolve().parents[2] / "contracts" / "claims_table.yaml"

#: epistemic ordering (ASPIRATIONAL is not on the evidence ladder — it marks
#: declared intent and is never "above" or "below" evidence rungs for gating;
#: it is simply never user-facing as a measured claim)
_EVIDENCE_ORDER = {Rung.DESIGNED: 0, Rung.MEASURABLE: 1, Rung.VALIDATED: 2}


@lru_cache(maxsize=1)
def load_claims_table() -> dict[str, Any]:
    return yaml.safe_load(_CLAIMS_PATH.read_text(encoding="utf-8"))


def max_rung_for_tier(tier: Tier) -> Rung:
    table = load_claims_table()
    return Rung(table["tiers"][f"tier_{tier}"]["max_rung"])


def exceeds_tier_ceiling(rung: Rung, tier: Tier) -> bool:
    """True when a claim's rung is presented above what the tier permits."""
    if rung == Rung.ASPIRATIONAL:
        return False  # not an evidence claim; flagged elsewhere if user-facing
    ceiling = max_rung_for_tier(tier)
    return _EVIDENCE_ORDER[rung] > _EVIDENCE_ORDER[ceiling]


def forbidden_words_for_tier(tier: Tier) -> tuple[str, ...]:
    table = load_claims_table()
    return tuple(table["tiers"][f"tier_{tier}"]["forbidden_words_user_facing"])
