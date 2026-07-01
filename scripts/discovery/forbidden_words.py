"""D6 — forbidden-word leakage. Non-blocking; exits 0.

'surrender' is a CSPC-owned construct (#5): it may appear in src/state/ (owns it)
and in src/merge/precision.py (the documented R2 consumer that reads
MetacogLabel.SURRENDER to widen CIs, and tags an internal precision flag — never
user-facing). Any OTHER occurrence in src/ is a real finding. 'synergy' must not
appear in a claims OUTPUT string (#4) — the forbidden_word_scan's own word list is
excluded.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.discovery._common import info, proposal_stub, warn  # noqa: E402

# documented, reviewed exceptions — by-design CSPC consumers / compliance prose,
# not leaks. precision.py reads MetacogLabel.SURRENDER to widen CIs (R2 consumer);
# footer.py names the word only in a docstring asserting the copy is forbidden-word
# clean ("no synergy/surrender/dependent stems"). A new occurrence in EITHER file
# would need re-review — remove it from this set to re-flag.
_SURRENDER_OK = {"src/merge/precision.py", "src/claims/footer.py"}


def _rel(p: pathlib.Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def main() -> None:
    hits = []
    for p in (ROOT / "src").rglob("*.py"):
        rel = _rel(p)
        if "/state/" in f"/{rel}" or rel.startswith("src/state/"):
            continue  # state/ owns the SURRENDER construct
        if rel in _SURRENDER_OK:
            continue
        if re.search(r"\bsurrender\b", p.read_text(encoding="utf-8", errors="ignore"), re.I):
            hits.append(rel)

    if hits:
        warn(f"'surrender' outside CSPC (#5) in: {hits}")
        proposal_stub(
            title="'surrender' leaked outside CSPC",
            finding=f"Files {hits} reference 'surrender' outside src/state and the reviewed exceptions.",
            domain="Forbidden words / rung discipline",
        )
    else:
        info("D6 forbidden-words: PASS ('surrender' confined to CSPC + reviewed consumers)")


if __name__ == "__main__":
    main()
