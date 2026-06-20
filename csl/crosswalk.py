"""Loader and validator for the CSL neuron-to-ACF crosswalk."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ACF_LEVELS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7")
DEFAULT_CROSSWALK_PATH = Path(__file__).with_name("acf_crosswalk.yaml")
DEFAULT_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "contract_table.yaml"


@dataclass(frozen=True)
class ACFCrosswalk:
    """Validated mapping from ACF levels to ARI neuron ids."""

    version: str
    status: str
    levels: dict[str, dict[str, Any]]
    excluded: dict[str, str]

    @property
    def mapped_ids(self) -> set[str]:
        ids: set[str] = set()
        for entry in self.levels.values():
            ids.update(entry["neurons"])
        return ids

    def levels_for(self, neuron_id: str) -> tuple[str, ...]:
        return tuple(
            level
            for level, entry in self.levels.items()
            if neuron_id in entry["neurons"]
        )


def contract_neuron_ids(path: str | Path = DEFAULT_CONTRACT_PATH) -> set[str]:
    """Read the contract table and return the frozen neuron id set."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    neurons = raw.get("neurons") if isinstance(raw, dict) else None
    if not isinstance(neurons, list):
        raise ValueError("contract_table.yaml must contain a neurons list")
    ids = {str(row.get("id")) for row in neurons if isinstance(row, dict) and row.get("id")}
    if len(ids) != len(neurons):
        raise ValueError("contract_table.yaml contains duplicate or missing neuron ids")
    return ids


def load_acf_crosswalk(
    path: str | Path = DEFAULT_CROSSWALK_PATH,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT_PATH,
) -> ACFCrosswalk:
    """Load and validate the crosswalk against the neuron contract table."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("ACF crosswalk must be a mapping")

    levels = raw.get("acf_levels")
    if not isinstance(levels, dict):
        raise ValueError("ACF crosswalk must define acf_levels")

    missing_levels = set(ACF_LEVELS) - set(levels)
    extra_levels = set(levels) - set(ACF_LEVELS)
    if missing_levels or extra_levels:
        raise ValueError(
            "ACF crosswalk levels must be exactly C1-C7 "
            f"(missing={sorted(missing_levels)}, extra={sorted(extra_levels)})"
        )

    normalized_levels: dict[str, dict[str, Any]] = {}
    for level in ACF_LEVELS:
        entry = levels[level]
        if not isinstance(entry, dict):
            raise ValueError(f"{level} must be a mapping")
        label = entry.get("label")
        neurons = entry.get("neurons")
        if not label:
            raise ValueError(f"{level} is missing a label")
        if not isinstance(neurons, list) or not all(isinstance(n, str) for n in neurons):
            raise ValueError(f"{level}.neurons must be a list of ids")
        if len(neurons) != len(set(neurons)):
            raise ValueError(f"{level}.neurons contains duplicate ids")
        normalized_levels[level] = {**entry, "neurons": tuple(neurons)}

    excluded_raw = raw.get("csl_excluded", [])
    if not isinstance(excluded_raw, list):
        raise ValueError("csl_excluded must be a list")
    excluded: dict[str, str] = {}
    for item in excluded_raw:
        if not isinstance(item, dict) or not item.get("id") or not item.get("reason"):
            raise ValueError("each csl_excluded item must contain id and reason")
        excluded[str(item["id"])] = str(item["reason"])

    contract_ids = contract_neuron_ids(contract_path)
    mapped_ids = {
        neuron_id
        for entry in normalized_levels.values()
        for neuron_id in entry["neurons"]
    }

    unknown = (mapped_ids | set(excluded)) - contract_ids
    if unknown:
        raise ValueError(f"ACF crosswalk references unknown neuron ids: {sorted(unknown)}")

    both = mapped_ids & set(excluded)
    if both:
        raise ValueError(f"ACF crosswalk maps and excludes the same ids: {sorted(both)}")

    missing = contract_ids - mapped_ids - set(excluded)
    if missing:
        raise ValueError(f"ACF crosswalk omits contract neuron ids: {sorted(missing)}")

    return ACFCrosswalk(
        version=str(raw.get("version", "")),
        status=str(raw.get("status", "")),
        levels=normalized_levels,
        excluded=excluded,
    )

