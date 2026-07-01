"""D4 — every leaf module is exercised by some test. Non-blocking; exits 0.

CORRECTED vs the brief's sketch: leaf tests in this repo are GROUPED
(tests/unit/test_extractors.py, test_dynamics_leaves.py, …), not one
test_<module>.py per leaf. A per-file-name probe floods false 'missing' hits.
This probe instead asks the real question: is the leaf imported/referenced by ANY
test? An unreferenced leaf is the true coverage gap.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.discovery._common import info, proposal_stub, warn  # noqa: E402

LEAF_DIRS = [
    "src/trait/extractors/per_dimension",
    "src/state",
    "src/dynamics",
]


def main() -> None:
    test_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (ROOT / "tests").rglob("test_*.py")
    )

    uncovered = []
    for d in LEAF_DIRS:
        for leaf in (ROOT / d).glob("*.py"):
            if leaf.stem == "__init__":
                continue
            # referenced by import path (…import stem) or module dotted path?
            dotted = (d.replace("/", ".") + "." + leaf.stem)
            if leaf.stem in test_text or dotted in test_text:
                continue
            uncovered.append(f"{d}/{leaf.name}")

    if uncovered:
        warn(f"leaf module(s) not referenced by any test: {uncovered}")
        proposal_stub(
            title="Leaf modules with no test reference",
            finding=f"{uncovered} are not imported/referenced by any test file.",
            domain="Test coverage",
        )
    else:
        info("D4 coverage: PASS (all leaf modules referenced by tests)")


if __name__ == "__main__":
    main()
