"""
src/claims/tier_engine.py — tier detection + structural claim gating.
OWNER: Chief Engineer. (Brief §3.10; spec §9.)

Tier is detected from the PAYLOAD, never requested by the caller: a transcript
with no telemetry is Tier 1, whatever the client says. enforce() is the last
step before a ScoreResponse leaves the system; it raises on rung overreach
(a bug, loudly) and applies minor protection by WITHHOLDING (not zeroing)
the composite and debt values.
"""

from __future__ import annotations

from contracts.schemas import (
    CanonicalSession,
    Composite,
    ScoreResponse,
    ScoreStatus,
    Tier,
)
from src.claims.rungs import exceeds_tier_ceiling


class ClaimsViolation(Exception):
    """A response carries a claim above its tier's ceiling. Never emitted —
    raised so the contract tests and CI catch the bug that produced it."""


def detect_tier(session: CanonicalSession) -> Tier:
    """Scope A: transcripts only → always Tier 1. Telemetry (Tier 2) and
    controlled-stimulus (Tier 3) detection land with those scopes; the
    signature is frozen now so callers never choose their own tier."""
    has_telemetry = bool(session.metadata.get("telemetry"))
    return 2 if has_telemetry else 1


def _rung_audit(response: ScoreResponse) -> list[str]:
    tier = response.tier
    found: list[str] = []
    checks = [
        ("composite", response.composite.rung),
        ("state_validity", response.state_validity.rung),
        ("flags", response.flags.rung),
        ("reaction_signatures", response.reaction_signatures.rung),
        ("regime_overlay", response.regime_overlay.rung),
        ("sustainability.s_human_hat", response.sustainability.s_human_hat.rung),
        ("sustainability.debt_ewma", response.sustainability.debt_ewma.rung),
        ("sustainability.lambda", response.sustainability.lambda_.rung),
        ("report", response.report.rung),
        *((f"profile.{d.value}", s.rung) for d, s in response.profile.items()),
    ]
    for path, rung in checks:
        if exceeds_tier_ceiling(rung, tier):
            found.append(f"{path} carries rung {rung.value} above tier {tier} ceiling")
    return found


def apply_minor_protection(response: ScoreResponse) -> ScoreResponse:
    """No bare composite / peer rank / debt score to minors (non-negotiable #15).
    Withhold = NOT_APPLICABLE with reason; the 8-dim profile (band material)
    and flags remain — the report renders them in band form."""
    composite = Composite(
        value=None,
        ci=None,
        status=ScoreStatus.NOT_APPLICABLE,
        gates_passed=response.composite.gates_passed,
        state_compromised_caveat=response.composite.state_compromised_caveat,
        rung=response.composite.rung,
    )
    debt = response.sustainability.debt_ewma.model_copy(update={"value": None})
    sustainability = response.sustainability.model_copy(update={"debt_ewma": debt})
    return response.model_copy(update={"composite": composite, "sustainability": sustainability})


def enforce(response: ScoreResponse, *, is_minor: bool = False) -> ScoreResponse:
    """The structural gate every response passes on its way out."""
    violations = _rung_audit(response)
    if violations:
        raise ClaimsViolation("; ".join(violations))
    if is_minor:
        response = apply_minor_protection(response)
    return response
