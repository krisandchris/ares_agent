"""Tests for the Step1 -> Step2 workflow (no SAM3)."""

from __future__ import annotations

import json
from typing import Any, cast

from ares_agent.domain.events import EventSeed
from ares_agent.domain.stage1_output import RelationItem, Stage1Output
from ares_agent.domain.stage2_output import FactVerification, Stage2Candidate, Stage2Output
from ares_agent.domain.payloads import StoredEventPayload
from ares_agent.prompts.data_engine_prompts import (
    DataEngineStep1PromptBuilder,
    DataEngineStep2PromptBuilder,
)
from ares_agent.services.feedback import PreliminaryEventFeedback, RefinedEventFeedback
from ares_agent.services.result_gate import ResultGate
from ares_agent.workflows.step1_step2_workflow import build_step1_step2_workflow

CallbackPayload = PreliminaryEventFeedback | RefinedEventFeedback

CONFIG_DIR = __import__("pathlib").Path(__file__).resolve().parents[3] / "config" / "data_engine"


def _make_seed(
    *,
    location: str = "南山路",
    camera_id: str = "front",
) -> EventSeed:
    return EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id=camera_id,
        location=location,
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-05-08T10:00:00Z",
    )


STAGE1_OUTPUT = Stage1Output(
    environment_analysis="人行道上有电动自行车停放",
    scene_elements=["sidewalk", "electric_bicycle", "pedestrian_walkway"],
    key_anchors=["pedestrian_walkway", "sidewalk", "shop_boundary"],
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


def _make_stage2_output(
    violation_categories: list[str] | None = None,
    confidence: float = 0.85,
) -> Stage2Output:
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
                confidence=confidence,
                sample_category="positive samples",
            ),
        ],
    )


def _mock_requester(stage1_output: Stage1Output, stage2_output: Stage2Output):
    """Return a requester that returns stage1 then stage2 responses."""
    call_count = 0

    def requester(url: str, headers: dict, payload: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            content = stage1_output.model_dump_json(ensure_ascii=False)
        else:
            content = stage2_output.model_dump_json(ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}]
        }

    return requester


class FakeSinkPlugin:
    def __init__(self, calls: list[CallbackPayload]) -> None:
        self.calls = calls

    def send(self, event_payload: object, runtime_config: object) -> dict[str, object]:
        assert isinstance(event_payload, (PreliminaryEventFeedback, RefinedEventFeedback))
        self.calls.append(event_payload)
        return {"success": True, "runtime_config": runtime_config}


def _stored_payload(output: object) -> StoredEventPayload:
    content = getattr(output, "content", None)
    assert isinstance(content, dict)
    return cast(StoredEventPayload, content)


POLICIES = {
    "南山路": {
        "front": {
            "enabled_categories": [
                "nonmotor_vehicle_illegal_parking",
                "road_occupying_vendor",
            ],
        },
    },
}


def _build_workflow(
    *,
    stage1_output: Stage1Output = STAGE1_OUTPUT,
    stage2_output: Stage2Output | None = None,
    policies: dict | None = None,
    callback_payloads: list[CallbackPayload] | None = None,
    runtime_config: dict | None = None,
):
    if stage2_output is None:
        stage2_output = _make_stage2_output()
    if policies is None:
        policies = POLICIES
    if callback_payloads is None:
        callback_payloads = []
    if runtime_config is None:
        runtime_config = {"callback": {"plugin": "http_callback"}}

    requester = _mock_requester(stage1_output, stage2_output)
    step1_builder = DataEngineStep1PromptBuilder.from_files(
        registry_path=CONFIG_DIR / "stage1_registry.yaml",
        system_template_path=CONFIG_DIR / "stage1_system_core.txt",
        user_template_path=CONFIG_DIR / "stage1_user_prompt.txt",
    )
    step2_builder = DataEngineStep2PromptBuilder.from_files(
        registry_path=CONFIG_DIR / "stage2_rule_registry.yaml",
        system_template_path=CONFIG_DIR / "stage2_system_core.txt",
        user_template_path=CONFIG_DIR / "stage2_user_prompt.txt",
    )
    return build_step1_step2_workflow(
        step1_prompt_builder=step1_builder,
        step2_prompt_builder=step2_builder,
        endpoint="http://fake-vlm/v1",
        model_name="test-model",
        step1_temperature=0.4,
        step2_temperature=0.2,
        max_tokens=4096,
        step1_requester=requester,
        step2_requester=requester,
        result_gate=ResultGate(policies),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config=runtime_config,
    )


def test_step1_step2_workflow_full_pipeline() -> None:
    callback_payloads: list[CallbackPayload] = []
    workflow = _build_workflow(callback_payloads=callback_payloads)

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    assert payload["stage"] == "refined"
    assert payload["event_id"].startswith("evt_")
    assert "stage1_output" in payload
    assert "stage2_output" in payload
    assert "candidates" in payload
    assert payload["event_version"] == 2
    assert len(callback_payloads) == 1
    assert isinstance(callback_payloads[0], RefinedEventFeedback)
    assert callback_payloads[0].final_category == "nonmotor_vehicle_illegal_parking"


def test_step1_step2_workflow_top_level_candidates() -> None:
    """Top-level candidates field contains non-no_violation candidates for downstream."""
    workflow = _build_workflow()

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    candidates = payload["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["violation_category"] == ["nonmotor_vehicle_illegal_parking"]
    assert candidates[0]["confidence"] == 0.85
    assert "evidence_reasoning" in candidates[0]


def test_step1_step2_workflow_candidates_filtered_by_gate() -> None:
    """Top-level candidates are filtered by result gate."""
    stage2 = _make_stage2_output(violation_categories=["staff_not_wear_mask"])
    workflow = _build_workflow(stage2_output=stage2)

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    # staff_not_wear_mask not in 南山路/front allowed categories
    assert payload["candidates"] == []


def test_step1_step2_workflow_candidates_excludes_no_violation() -> None:
    """no_violation candidates are excluded from top-level candidates."""
    stage2 = _make_stage2_output(violation_categories=["no_violation"])
    workflow = _build_workflow(stage2_output=stage2)

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    assert payload["candidates"] == []


def test_step1_step2_workflow_preserves_stage1_raw() -> None:
    """Stage1Output is passed raw in the output."""
    workflow = _build_workflow()

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    stage1 = payload["stage1_output"]
    assert stage1["environment_analysis"] == "人行道上有电动自行车停放"
    assert len(stage1["key_relations"]) == 1
    assert stage1["key_relations"][0]["subject"] == "电动自行车"


def test_step1_step2_workflow_preserves_stage2_raw() -> None:
    """Stage2Output is passed raw in the output."""
    workflow = _build_workflow()

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    stage2 = payload["stage2_output"]
    assert len(stage2["candidates"]) == 1
    assert stage2["candidates"][0]["violation_category"] == ["nonmotor_vehicle_illegal_parking"]
    assert len(stage2["fact_verifications"]) == 1


def test_step1_step2_workflow_gate_filters_step2_candidates() -> None:
    """Gate filters Stage2 candidates by allowed categories."""
    callback_payloads: list[CallbackPayload] = []
    stage2 = _make_stage2_output(violation_categories=["staff_not_wear_mask"])
    workflow = _build_workflow(
        stage2_output=stage2,
        callback_payloads=callback_payloads,
    )

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    # Candidate filtered out by gate
    stage2_out = payload["stage2_output"]
    assert len(stage2_out["candidates"]) == 0
    # Callback still sent with "none"
    assert callback_payloads[0].final_category == "none"


def test_step1_step2_workflow_gate_passes_allowed_category() -> None:
    """Gate passes Stage2 output when category is allowed."""
    callback_payloads: list[CallbackPayload] = []
    stage2 = _make_stage2_output(violation_categories=["road_occupying_vendor"])
    workflow = _build_workflow(
        stage2_output=stage2,
        callback_payloads=callback_payloads,
    )

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    stage2_out = payload["stage2_output"]
    assert len(stage2_out["candidates"]) == 1
    assert stage2_out["candidates"][0]["violation_category"] == ["road_occupying_vendor"]


def test_step1_step2_workflow_unknown_location_passes_all() -> None:
    """Unknown location has no gate restriction."""
    callback_payloads: list[CallbackPayload] = []
    stage2 = _make_stage2_output(violation_categories=["staff_not_wear_mask"])
    workflow = _build_workflow(
        stage2_output=stage2,
        callback_payloads=callback_payloads,
    )

    output = workflow.run(input=_make_seed(location="未知路"))
    payload = _stored_payload(output)

    stage2_out = payload["stage2_output"]
    assert len(stage2_out["candidates"]) == 1


def test_step1_step2_workflow_no_violation() -> None:
    """Step2 finds no violation."""
    callback_payloads: list[CallbackPayload] = []
    stage2 = _make_stage2_output(violation_categories=["no_violation"])
    workflow = _build_workflow(
        stage2_output=stage2,
        callback_payloads=callback_payloads,
    )

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    assert payload["stage"] == "refined"
    assert callback_payloads[0].final_category == "none"


def test_step1_step2_workflow_can_skip_callbacks() -> None:
    callback_payloads: list[CallbackPayload] = []
    workflow = _build_workflow(
        callback_payloads=callback_payloads,
        runtime_config={"callback": {"send_preliminary": False, "send_refined": False}},
    )

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    assert payload["stage"] == "refined"
    assert callback_payloads == []


def test_step1_step2_workflow_shared_event_id() -> None:
    callback_payloads: list[CallbackPayload] = []
    workflow = _build_workflow(callback_payloads=callback_payloads)

    output = workflow.run(input=_make_seed())
    payload = _stored_payload(output)

    assert payload["event_id"].startswith("evt_")
    assert callback_payloads[0].event_id == payload["event_id"]
