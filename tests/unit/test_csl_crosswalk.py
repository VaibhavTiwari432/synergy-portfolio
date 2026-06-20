from __future__ import annotations

import pytest
import yaml

from csl.crosswalk import ACF_LEVELS, contract_neuron_ids, load_acf_crosswalk


def test_acf_crosswalk_covers_every_contract_neuron():
    crosswalk = load_acf_crosswalk()
    contract_ids = contract_neuron_ids()

    assert crosswalk.mapped_ids | set(crosswalk.excluded) == contract_ids
    assert crosswalk.mapped_ids & set(crosswalk.excluded) == set()
    assert len(contract_ids) == 107


def test_acf_crosswalk_has_all_seven_levels_with_labels():
    crosswalk = load_acf_crosswalk()

    assert tuple(crosswalk.levels) == ACF_LEVELS
    for level, entry in crosswalk.levels.items():
        assert entry["label"]
        assert entry["foundation_signal"]
        assert entry["neurons"], f"{level} should not be empty"


def test_crosswalk_keeps_expected_sentinel_mappings():
    crosswalk = load_acf_crosswalk()

    assert "C1" in crosswalk.levels_for("AL-08")  # recency-sensitive sourcing
    assert "C3" in crosswalk.levels_for("EC-01")  # factual checking
    assert "C4" in crosswalk.levels_for("CD-02")  # lateral concept injection
    assert "C6" in crosswalk.levels_for("CD-08")  # analogical novelty
    assert "C7" in crosswalk.levels_for("AUI-02")  # delegation judgment


def test_crosswalk_rejects_missing_contract_ids(tmp_path):
    source = yaml.safe_load(open("csl/acf_crosswalk.yaml", encoding="utf-8"))
    source["acf_levels"]["C7"]["neurons"].remove("AUI-02")
    path = tmp_path / "acf_crosswalk.yaml"
    path.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(ValueError, match="omits contract neuron ids"):
        load_acf_crosswalk(path)


def test_crosswalk_rejects_unknown_ids(tmp_path):
    source = yaml.safe_load(open("csl/acf_crosswalk.yaml", encoding="utf-8"))
    source["acf_levels"]["C1"]["neurons"].append("XX-999")
    path = tmp_path / "acf_crosswalk.yaml"
    path.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown neuron ids"):
        load_acf_crosswalk(path)

