"""D2 — every ScoreRun field is populated on a real score. Non-blocking; exits 0."""

from __future__ import annotations

import dataclasses
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.discovery._common import fake_judge, first_gold_session, info, warn  # noqa: E402


def main() -> None:
    from src.api.pipeline import score_session_with_artifacts

    run = score_session_with_artifacts(first_gold_session(), judge=fake_judge())
    empty = []
    for f in dataclasses.fields(run):
        val = getattr(run, f.name)
        populated = bool(val) if not isinstance(val, (int, float)) else True
        if not populated:
            empty.append(f.name)
    if empty:
        warn(f"ScoreRun field(s) computed but empty on a real score: {empty}")
    else:
        info("D2 dropped-signals: PASS (all ScoreRun fields populated)")


if __name__ == "__main__":
    main()
