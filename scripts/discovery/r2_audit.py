"""D7 / R2 — the precision merge changes CI width, never a score value.
Non-blocking; exits 0."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.discovery._common import fake_judge, first_gold_session, info, proposal_stub, warn  # noqa: E402


def main() -> None:
    from src.api.pipeline import score_session_with_artifacts

    run = score_session_with_artifacts(first_gold_session(), judge=fake_judge())
    violations = []
    for dim, raw in run.raw_profile.items():
        merged = run.response.profile.get(dim)
        rv = getattr(raw, "value", None)
        mv = getattr(merged, "value", None) if merged is not None else None
        if rv is not None and mv is not None and abs(rv - mv) > 1e-9:
            violations.append(f"{dim}: raw={rv:.4f} merged={mv:.4f}")

    if violations:
        warn(f"R2 VIOLATION — state changed a score value (not just CI): {violations}")
        proposal_stub(
            title="R2 violation — precision merge moved a score value",
            finding=f"Score values changed through the merge: {violations}. State must condition CI only (#2).",
            domain="R2 / precision merge",
        )
    else:
        info("D7 R2-audit: PASS (all score values preserved through the precision merge)")


if __name__ == "__main__":
    main()
