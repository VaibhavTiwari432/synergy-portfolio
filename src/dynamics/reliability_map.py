"""
src/dynamics/reliability_map.py — partner reliability map SCAFFOLD.
OWNER: Chief Engineer. (Brief §3.8; spec §10 A11.)

Era-keyed reliability priors R̂(claim_domain, model_era). Scope A ships the
schema + update/back-test hooks only; PartnerModel captures (family, model_id,
era_key) from day one so the data exists when the map goes live. Seeded from
benchmark priors LATER via ADR — shipping invented numbers would be worse
than shipping none, so the default map is empty and read access says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contracts.schemas import PartnerModel, Rung


@dataclass(frozen=True)
class ReliabilityEntry:
    era_key: str            # "YYYY-MM"
    family: str
    model_id: str
    claim_domain: str       # e.g. "code", "math", "citations", "general"
    reliability: float      # 0–1 prior that claims in this cell are sound
    n_verified: int         # verified outcomes backing the entry
    rung: Rung = Rung.DESIGNED


@dataclass
class ReliabilityMap:
    """Scaffold: storage + the two hooks the framework needs later."""

    entries: dict[tuple[str, str, str], ReliabilityEntry] = field(default_factory=dict)

    @staticmethod
    def _key(partner: PartnerModel, claim_domain: str) -> tuple[str, str, str]:
        return (partner.era_key, partner.family, claim_domain)

    def lookup(self, partner: PartnerModel, claim_domain: str) -> ReliabilityEntry | None:
        """None = no prior (callers must treat as absent, never as 0.5)."""
        return self.entries.get(self._key(partner, claim_domain))

    def record_outcome(
        self, partner: PartnerModel, claim_domain: str, *, verified_sound: bool
    ) -> None:
        """Back-test hook: fold one judge-verified outcome into the cell."""
        key = self._key(partner, claim_domain)
        prev = self.entries.get(key)
        if prev is None:
            self.entries[key] = ReliabilityEntry(
                era_key=partner.era_key, family=partner.family,
                model_id=partner.model_id, claim_domain=claim_domain,
                reliability=1.0 if verified_sound else 0.0, n_verified=1,
            )
            return
        n = prev.n_verified + 1
        updated = prev.reliability + ((1.0 if verified_sound else 0.0) - prev.reliability) / n
        self.entries[key] = ReliabilityEntry(
            era_key=prev.era_key, family=prev.family, model_id=prev.model_id,
            claim_domain=prev.claim_domain, reliability=updated, n_verified=n,
            rung=prev.rung,
        )

    def back_test(self, claim_domain: str) -> dict[str, float] | None:
        """Per-era reliability ordering for one domain (None = no data). The
        A11 contract: this ordering must predict judge-verified error rates,
        or the era is demoted and calibration_slope suspended for it."""
        cells = [e for e in self.entries.values() if e.claim_domain == claim_domain]
        if not cells:
            return None
        return {e.era_key: e.reliability for e in sorted(cells, key=lambda e: e.era_key)}
