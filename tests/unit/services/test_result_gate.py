"""Tests for ResultGate."""

from __future__ import annotations

import pytest

from ares_agent.domain.stage2_output import Stage2Candidate
from ares_agent.services.result_gate import ResultGate


def _candidate(category: str) -> Stage2Candidate:
    return Stage2Candidate(
        violation_category=[category],
        evidence_relation_indices=[0],
        evidence_reasoning="test",
        relation_hint="",
        segmentation_targets=[],
        confidence=0.8,
        sample_category="positive samples",
    )


POLICIES = {
    "南山路": {
        "front": {
            "enabled_categories": [
                "road_occupying_vendor",
                "goods_blocking_road",
                "motor_vehicle_illegal_parking",
            ],
        },
        "left": {
            "enabled_categories": ["unauthorized_electrical_wiring"],
        },
    },
    "水坊街": {
        "left": {"enabled_categories": ["staff_not_wear_mask"]},
        "right": {"enabled_categories": []},
    },
}


def test_gate_passes_allowed_categories() -> None:
    gate = ResultGate(POLICIES)
    candidates = [_candidate("road_occupying_vendor"), _candidate("goods_blocking_road")]
    result = gate.filter("南山路", "front", candidates)
    assert len(result) == 2


def test_gate_filters_disallowed_categories() -> None:
    gate = ResultGate(POLICIES)
    candidates = [_candidate("road_occupying_vendor"), _candidate("staff_not_wear_mask")]
    result = gate.filter("南山路", "front", candidates)
    assert len(result) == 1
    assert result[0].violation_category == ["road_occupying_vendor"]


def test_gate_all_filtered() -> None:
    gate = ResultGate(POLICIES)
    candidates = [_candidate("staff_not_wear_mask")]
    result = gate.filter("南山路", "front", candidates)
    assert len(result) == 0


def test_gate_unknown_location_passes_all() -> None:
    gate = ResultGate(POLICIES)
    candidates = [_candidate("road_occupying_vendor"), _candidate("staff_not_wear_mask")]
    result = gate.filter("未知路", "front", candidates)
    assert len(result) == 2


def test_gate_unknown_camera_passes_all() -> None:
    gate = ResultGate(POLICIES)
    candidates = [_candidate("road_occupying_vendor")]
    result = gate.filter("南山路", "back", candidates)
    assert len(result) == 1


def test_gate_empty_enabled_categories_passes_all() -> None:
    gate = ResultGate(POLICIES)
    candidates = [_candidate("road_occupying_vendor")]
    result = gate.filter("水坊街", "right", candidates)
    assert len(result) == 1


def test_gate_different_location_different_rules() -> None:
    gate = ResultGate(POLICIES)
    candidates = [_candidate("staff_not_wear_mask")]
    assert len(gate.filter("水坊街", "left", candidates)) == 1
    assert len(gate.filter("南山路", "front", candidates)) == 0


def test_gate_empty_candidates() -> None:
    gate = ResultGate(POLICIES)
    result = gate.filter("南山路", "front", [])
    assert len(result) == 0
