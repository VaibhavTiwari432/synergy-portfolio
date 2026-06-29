"""Pre-filter eligibility gate (ADR-0019, v3.23 §3 corrected by Appendix R).

Before judge scoring, decide which judge-typed neurons a task's intents can
structurally elicit. A neuron the task cannot elicit (e.g. CA "pushes back on
AI" in a pure EXTRACT task) is marked structurally N/A rather than scored —
distinguishing "the task never called for this" from "could fire, did not".

Scope and safety:
- Governs ONLY judge-typed neurons. The 9 deterministic neurons fire from event
  evidence, not intent; they are listed in `event_gated_exempt` and never
  filtered here.
- Reuses ScoreStatus.NOT_APPLICABLE (its docstring already == "spec STRUCTURAL_NA").
  Structural vs. behavioral is carried as a reason string, NOT a new enum — no
  contract/schema bump (non-negotiable #1, frozen surface).
- The shipped matrix is a permissive scaffold: every neuron triggers on all 10
  intents until a cell is tightened, so the gate excludes nothing by default
  (safe no-op). It is not wired onto the live path — flag-off until corpus
  validation (ADR-0019 §acceptance), mirroring cspc_weighting.

ponytail: matrix loaded once per construction; pass an EligibilityGate instance
around rather than re-reading the YAML per chat.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from contracts.schemas import ScoreStatus

# Default matrix location (frozen-contract neighbour).
DEFAULT_MATRIX_PATH = Path(__file__).resolve().parents[2] / "contracts" / "neuron_task_eligibility.yaml"

STRUCTURAL_NA = "STRUCTURAL_NA"  # cannot fire given the task's intents
BEHAVIORAL_NA = "BEHAVIORAL_NA"  # could fire, did not


class EligibilityGate:
    """Maps a task's intent tags to the judge-typed neurons it can elicit."""

    def __init__(self, matrix_path: str | Path = DEFAULT_MATRIX_PATH):
        with open(matrix_path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        self.version: str = doc.get("version", "unknown")
        self.intent_tags: set[str] = set(doc["intent_tags"])
        self.exempt: frozenset[str] = frozenset(doc.get("event_gated_exempt", ()))
        self.matrix: dict[str, dict] = doc["eligibility_matrix"]

    def _triggers(self, neuron_id: str) -> set[str]:
        return set(self.matrix[neuron_id].get("triggers_on", ()))

    def determine_scorable_neurons(self, task_intents) -> set[str]:
        """Judge-typed neurons that can fire given these intents.

        A neuron is scorable if any of its `triggers_on` intents is present.
        Deterministic (exempt) neurons are never returned here — they are not
        judge-gated. Unknown intent tags are ignored (gate never invents tags).
        """
        intents = {str(i) for i in task_intents} & self.intent_tags
        return {nid for nid in self.matrix if self._triggers(nid) & intents}

    def classify_na_reason(self, neuron_id: str, task_intents) -> str:
        """STRUCTURAL_NA if no `triggers_on` intent is present, else BEHAVIORAL_NA.

        Only meaningful for judge-typed neurons in the matrix; a deterministic
        (exempt) neuron is not the gate's concern and raises KeyError to surface
        misuse rather than silently mislabel.
        """
        if neuron_id in self.exempt:
            raise KeyError(f"{neuron_id} is event-gated/deterministic — not intent-filtered")
        intents = {str(i) for i in task_intents} & self.intent_tags
        return BEHAVIORAL_NA if self._triggers(neuron_id) & intents else STRUCTURAL_NA

    def na_status(self) -> ScoreStatus:
        """The ScoreStatus a structurally-ineligible neuron carries (reuses the
        existing N/A status; the reason string distinguishes the two NA kinds)."""
        return ScoreStatus.NOT_APPLICABLE


@lru_cache(maxsize=1)
def default_gate() -> EligibilityGate:
    """Process-wide singleton over the default matrix (the matrix is frozen)."""
    return EligibilityGate()


if __name__ == "__main__":
    # ponytail self-check: permissive scaffold must exclude nothing, exempt the
    # 9 deterministic neurons, and classify NA by intent presence.
    g = EligibilityGate()
    assert len(g.matrix) == 98, f"expected 98 judge-typed, got {len(g.matrix)}"
    assert len(g.exempt) == 9, f"expected 9 exempt, got {len(g.exempt)}"
    # Permissive default: any single real intent makes every neuron scorable.
    scorable = g.determine_scorable_neurons(["VERIFY"])
    assert scorable == set(g.matrix), "scaffold must be a no-op (excludes nothing)"
    # Empty / unknown intents → nothing scorable, everything STRUCTURAL_NA.
    assert g.determine_scorable_neurons([]) == set()
    assert g.classify_na_reason("CA-16", []) == STRUCTURAL_NA
    assert g.classify_na_reason("CA-16", ["VERIFY"]) == BEHAVIORAL_NA
    # Exempt neurons are not the gate's concern.
    try:
        g.classify_na_reason("EC-06", ["VERIFY"])
        raise AssertionError("expected KeyError for exempt neuron")
    except KeyError:
        pass
    print(f"eligibility_gate self-check OK (matrix v{g.version}, 98 judge / 9 exempt)")
