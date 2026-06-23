"""D3 — same fixture scored twice yields identical output. Non-blocking; exits 0."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.discovery._common import fake_judge, first_gold_session, info, warn  # noqa: E402


def main() -> None:
    from src.api.pipeline import score_session_with_artifacts

    session = first_gold_session()
    r1 = json.loads(score_session_with_artifacts(session, judge=fake_judge()).response.model_dump_json())
    r2 = json.loads(score_session_with_artifacts(session, judge=fake_judge()).response.model_dump_json())
    if r1 == r2:
        info("D3 determinism: PASS (identical output on two runs)")
    else:
        diverged = [k for k in r1 if r1.get(k) != r2.get(k)]
        warn(f"DETERMINISM FAIL — output differs at: {diverged}")


if __name__ == "__main__":
    main()
