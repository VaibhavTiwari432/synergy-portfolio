"""
src/sustainability/probe_schema.py — retention-probe schema access.
OWNER: Chief Engineer. (Brief §3.9: schema only in Scope A; no delivery.)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "probe_schema.yaml"

#: probe formats permitted by contract (generative recall only)
ALLOWED_FORMATS = ("free_recall", "application", "teach_back")


@lru_cache(maxsize=1)
def load_probe_schema() -> dict[str, Any]:
    return yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_probe_record(record: dict[str, Any]) -> list[str]:
    """Return a list of violations (empty = valid). Delivery is out of scope;
    this validates records arriving from future tiers."""
    schema = load_probe_schema()
    fields: dict[str, dict] = schema["probe_record"]["fields"]
    problems: list[str] = []

    for name, spec in fields.items():
        if spec.get("required") and record.get(name) is None:
            problems.append(f"missing required field: {name}")

    fmt = record.get("format")
    if fmt is not None and fmt not in ALLOWED_FORMATS:
        problems.append(
            f"format {fmt!r} not permitted (recognition is excluded by design)"
        )

    score = record.get("score")
    if score is not None and not (0.0 <= float(score) <= 1.0):
        problems.append(f"score {score} out of [0, 1]")

    return problems
