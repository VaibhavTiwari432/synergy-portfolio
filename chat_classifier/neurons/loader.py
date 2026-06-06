"""
Phase 2 — neuron contract loader.
Loads contract_table.yaml, validates every row against NeuronContract,
and enforces structural invariants (no duplicate ids, every dimension in config).
Raises on the first violation so the Contract Gate is binary and explicit.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from chat_classifier.config import DIMENSIONS
from chat_classifier.schemas import NeuronContract

_DEFAULT_TABLE = Path(__file__).parent / "contract_table.yaml"


def load_contracts(path: str | Path = _DEFAULT_TABLE) -> list[NeuronContract]:
    """
    Load and validate the neuron contract table.

    Args:
        path: path to the YAML file (defaults to the bundled contract_table.yaml)

    Returns:
        List of NeuronContract objects, one per row.

    Raises:
        FileNotFoundError   if the table does not exist
        ValueError          on schema violations, duplicate ids, or unknown dimensions
        pydantic.ValidationError  propagated on individual row failures (with row context)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Contract table not found: {path}")

    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not raw or "neurons" not in raw:
        raise ValueError(
            f"Contract table at {path} has no 'neurons' key. "
            "The YAML must contain a top-level 'neurons:' list."
        )

    rows = raw["neurons"]
    if not isinstance(rows, list):
        raise ValueError("'neurons' must be a YAML list.")

    contracts: list[NeuronContract] = []
    seen_ids: dict[str, int] = {}  # id → row index for duplicate reporting

    for row_idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(
                f"Row {row_idx} is not a YAML mapping (got {type(row).__name__}). "
                "Every neuron must be a key-value block."
            )

        # Dimension guard before Pydantic so error message is clear
        dim = row.get("dimension")
        if dim not in DIMENSIONS:
            raise ValueError(
                f"Row {row_idx} (id={row.get('id')!r}): dimension={dim!r} is not in "
                f"the configured dimension set {DIMENSIONS}. "
                "Either add it to config.DIMENSIONS or fix the row."
            )

        # Pydantic validation
        try:
            contract = NeuronContract.model_validate(row)
        except ValidationError as exc:
            raise ValueError(
                f"Row {row_idx} (id={row.get('id')!r}) failed schema validation:\n{exc}"
            ) from exc

        # Duplicate id guard
        if contract.id in seen_ids:
            raise ValueError(
                f"Duplicate neuron id {contract.id!r} at rows "
                f"{seen_ids[contract.id]} and {row_idx}. "
                "Every neuron must have a unique id."
            )
        seen_ids[contract.id] = row_idx
        contracts.append(contract)

    # Ensure every configured dimension has at least one neuron (brief §6, Phase 2)
    covered = {c.dimension for c in contracts}
    missing = set(DIMENSIONS) - covered
    if missing:
        # Warn but do not raise — the table is seeded incrementally.
        # This only becomes a hard error once Phase 3 tries to score those dims.
        import warnings
        warnings.warn(
            f"The following configured dimensions have no neurons yet: "
            f"{sorted(missing)}. Add rows before running extraction.",
            stacklevel=2,
        )

    return contracts
