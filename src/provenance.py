"""
src/provenance.py — single source of truth for instrument provenance.
OWNER: Chief Engineer.

Every score written to the corpus carries enough provenance to be reproduced
and compared across framework / schema / contract-table / code revisions
(Track 1, recoverability: provenance is unrecoverable retroactively once the
transcript purges). These are stamped onto the scores row as queryable columns,
NOT buried in a JSONB blob — the corpus will span many instrument versions and
must be filterable by them.
"""

from __future__ import annotations

import functools
import os
import subprocess
from pathlib import Path

from contracts.schemas import SCHEMA_VERSION

#: SAF/ARI framework revision this scorer implements.
FRAMEWORK_VERSION = "v2.2"

#: Pydantic contract-schema revision (contracts/schemas.py).
#: Re-exported from the contracts package so there is exactly one definition.
SCHEMA_VERSION = SCHEMA_VERSION  # noqa: PLW0127 — intentional re-export

#: Neuron contract-table revision (contracts/contract_table.yaml header).
CONTRACT_TABLE_VERSION = "v6.0"

#: Deterministic-extractor cohort version (bumped when extractor logic changes).
EXTRACTOR_VERSION = "v6.0"

_REPO_ROOT = Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=1)
def git_sha() -> str:
    """Short git SHA of the running code, resolved once and cached.

    Order: SAF_GIT_SHA env override (set in CI/containers where .git is absent)
    → `git rev-parse`. Returns 'unknown' rather than raising — a missing SHA must
    never block scoring, only degrade provenance.
    """
    env_sha = os.environ.get("SAF_GIT_SHA")
    if env_sha:
        return env_sha.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        sha = out.stdout.strip()
        return sha or "unknown"
    except Exception:
        return "unknown"


def provenance_stamp(*, judge_model_id: str | None, judge_model_version: str | None) -> dict:
    """Assemble the provenance column-set for a single score row."""
    return {
        "framework_version": FRAMEWORK_VERSION,
        "schema_version": SCHEMA_VERSION,
        "contract_table_version": CONTRACT_TABLE_VERSION,
        "code_git_sha": git_sha(),
        "judge_model_id": judge_model_id,
        "judge_model_version": judge_model_version,
    }
