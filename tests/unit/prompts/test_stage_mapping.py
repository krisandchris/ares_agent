"""Tests for stage_mapping module."""

from __future__ import annotations

import json

import pytest

from ares_agent.domain.stage1_output import RelationItem, Stage1Output
from ares_agent.domain.stage2_output import Stage2Candidate, Stage2Output, FactVerification
from ares_agent.prompts.stage_mapping import (
    map_stage1_to_preliminary,
    map_stage2_to_evidence_judge,
    map_stage2_to_preliminary,
    reconstruct_stage1_json,
)
from ares_agent.workflows.inspection_event_workflow import PreliminaryResult


def _make_stage1() -> Stage1Output:
    return Stage1Output(
        environment_analysis="test scene",
        scene_elements=["sidewalk", "bicycle"],
        key_anchors=["pedestrian_walkway"],
        key_relations=[
            RelationItem(
                subject="电动自行车",
                relation="occupying",
                object="pedestrian_walkway",
                description="画面左侧电动自行车占据人行道",
                bbox=[100, 200, 300, 400],
            ),
        ],
    )


def _make_stage2(violation_categories: list[str] | None = None) -> Stage2Output:
    cats = violation_categories or ["nonmotor_vehicle_illegal_parking"]
    return Stage2Output(
        sample_id="evt_test",
        fact_verifications=[
            FactVerification(
                relation_index=0,
                subject="电动自行车",
                relation="occupying",
                object="pedestrian_walkway",
                bbox=[100, 200, 300, 400],
                visibility_level="clear",
                information_loss_type="none",
                key_attributes_visible=["wheel", "body"],
                subject_visible=True,
                subject_match=True,
                bbox_observation="电动自行车在bbox内",
                global_context_observation="人行道被占据",
                verification_result="supported",
                verification_confidence=0.9,
            ),
        ],
        candidates=[
            Stage2Candidate(
                violation_category=cats,
                evidence_relation_indices=[0],
                evidence_reasoning="电动自行车占据人行道",
                relation_hint="电动自行车 occupying pedestrian_walkway",
                segmentation_targets=["电动自行车"],
                confidence=0.85,
                sample_category="positive samples",
            ),
        ],
    )


def test_map_stage1_to_preliminary_produces_none_candidate() -> None:
    stage1 = _make_stage1()
    result = map_stage1_to_preliminary(stage1)
    assert isinstance(result, PreliminaryResult)
    assert result.environment_analysis == "test scene"
    assert len(result.candidates) == 1
    assert result.candidates[0].violation_category == "none"


def test_map_stage2_to_preliminary_with_violation() -> None:
    stage1 = _make_stage1()
    stage2 = _make_stage2()
    result = map_stage2_to_preliminary(stage2, stage1)
    assert len(result.candidates) == 1
    assert result.candidates[0].violation_category == "nonmotor_vehicle_illegal_parking"
    assert result.candidates[0].confidence == 0.85


def test_map_stage2_to_preliminary_with_no_violation() -> None:
    stage1 = _make_stage1()
    stage2 = _make_stage2(violation_categories=["no_violation"])
    result = map_stage2_to_preliminary(stage2, stage1)
    assert len(result.candidates) == 1
    assert result.candidates[0].violation_category == "none"


def test_map_stage2_to_preliminary_multiple_categories() -> None:
    stage1 = _make_stage1()
    stage2 = _make_stage2(violation_categories=["nonmotor_vehicle_illegal_parking", "goods_blocking_road"])
    result = map_stage2_to_preliminary(stage2, stage1)
    assert len(result.candidates) == 2
    cats = {c.violation_category for c in result.candidates}
    assert "nonmotor_vehicle_illegal_parking" in cats
    assert "goods_blocking_road" in cats


def test_map_stage2_to_evidence_judge_with_violation() -> None:
    stage2 = _make_stage2()
    result = map_stage2_to_evidence_judge(stage2)
    assert result.final_category == "nonmotor_vehicle_illegal_parking"
    assert result.final_confidence == 0.85
    assert result.evidence_basis_match is True
    assert result.violation_relation_confirmed is True
    assert result.archive_readiness is True


def test_map_stage2_to_evidence_judge_no_violation() -> None:
    stage2 = _make_stage2(violation_categories=["no_violation"])
    result = map_stage2_to_evidence_judge(stage2)
    assert result.final_category == "none"
    assert result.evidence_basis_match is False


def test_reconstruct_stage1_json_roundtrip() -> None:
    result = PreliminaryResult(
        environment_analysis="test",
        scene_elements=["a", "b"],
        candidates=[],
    )
    json_str = reconstruct_stage1_json(result)
    data = json.loads(json_str)
    assert data["environment_analysis"] == "test"
    assert data["scene_elements"] == ["a", "b"]
    assert data["key_anchors"] == []
    assert data["key_relations"] == []
