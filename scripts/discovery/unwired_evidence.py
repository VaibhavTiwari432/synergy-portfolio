"""D1 — deterministic neurons with no extractor. Non-blocking; exits 0."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from scripts.discovery._common import info, proposal_stub, warn  # noqa: E402


def main() -> None:
    ct = yaml.safe_load((ROOT / "contracts" / "contract_table.yaml").read_text())
    neurons = ct["neurons"]
    # NOTE: the contract-table field is `id`, NOT `neuron_id` (the brief's sketch
    # used the wrong key and reported a phantom hit — corrected here).
    det_ids = {
        n["id"] for n in neurons
        if str(n.get("extractor_type", "")).lower() == "deterministic"
    }
    fired: set[str] = set()
    for p in (ROOT / "src" / "trait" / "extractors" / "per_dimension").glob("*.py"):
        fired |= set(re.findall(r"[A-Z]{2,3}-\d{2}", p.read_text()))

    unwired = sorted(det_ids - fired)
    if unwired:
        warn(f"{len(unwired)} deterministic neuron(s) have NO extractor: {unwired}")
        proposal_stub(
            title="Unwired deterministic neurons",
            finding=f"Contract marks {unwired} deterministic, but no extractor fires them.",
            domain="Unwired evidence",
        )
    else:
        info(f"D1 unwired-evidence: PASS ({len(det_ids)} deterministic neurons all wired)")


if __name__ == "__main__":
    main()
