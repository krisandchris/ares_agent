from typing import cast

from ares_agent.domain.json_types import JsonObject
from ares_agent.domain.events import EventSeed
from ares_agent.model_clients.http_clients import PreliminaryRequestPayload, SglangVlmJudgeClient, SglangVlmPreliminaryClient
from ares_agent.prompts.builders import ConfigurableInspectionPromptBuilder, DefaultInspectionPromptBuilder
from type_helpers import (
    RequesterPayload,
    image_url_part,
    json_object,
    make_candidate,
    make_preliminary_result,
    message_parts,
    text_part,
)
import pytest


def test_preliminary_http_client_uses_prompt_builder_messages() -> None:
    captured: list[RequesterPayload] = []

    def fake_requester(url: str, headers: dict[str, str], payload: RequesterPayload) -> JsonObject:
        captured.append(payload)
        return json_object({
            "choices": [
                {
                    "message": {
                        "content": {
                            "environment_analysis": "storefront sidewalk scene",
                            "scene_elements": ["goods", "sidewalk", "storefront_entrance"],
                            "evidence_reasoning": "goods block pedestrian passage",
                            "segmentation_targets": ["goods", "storefront_entrance", "sidewalk"],
                            "relation_hint": "goods placed outside storefront and block sidewalk",
                            "violation_category": "goods_blocking_road",
                            "open_risk_type": "",
                            "confidence": 0.84,
                        }
                    }
                }
            ]
        })

    client = SglangVlmPreliminaryClient(
        endpoint="/mock/vlm/preliminary",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=DefaultInspectionPromptBuilder(),
    )

    client.analyze(
        EventSeed(
            image_uri="s3://street/frame-011.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-31",
            task_id="patrol-sh-011",
            occur_time="2026-03-09T11:10:00Z",
        )
    )

    assert captured
    first_payload = cast(PreliminaryRequestPayload, captured[0])
    assert first_payload["messages"][0]["role"] == "system"
    assert image_url_part(message_parts(first_payload["messages"][1])[1]) == "s3://street/frame-011.jpg"


def test_judge_http_client_includes_preliminary_result_in_user_prompt() -> None:
    captured: list[RequesterPayload] = []

    def fake_requester(url: str, headers: dict[str, str], payload: RequesterPayload) -> JsonObject:
        captured.append(payload)
        return json_object({
            "choices": [
                {
                    "message": {
                        "content": {
                            "final_category": "road_occupying_vendor",
                            "final_confidence": 0.96,
                            "evidence_basis_match": True,
                            "violation_relation_confirmed": True,
                            "exception_excluded": True,
                            "archive_readiness": True,
                            "review_required": False,
                            "rejection_reason": None,
                            "violation_relation_summary": "stall overlaps sidewalk boundary",
                        }
                    }
                }
            ]
        })

    client = SglangVlmJudgeClient(
        endpoint="/mock/vlm/judge",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=DefaultInspectionPromptBuilder(),
    )

    client.judge(
        event_id="evt_123",
        category_code="road_occupying_vendor",
        overlay_image="s3://mock/overlay.png",
        mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
        segmentation_status="ok",
        evidence_basis_summary="stall overlaps sidewalk boundary",
        preliminary=make_preliminary_result(
            environment_analysis="street storefront scene",
            scene_elements=["storefront", "stall", "sidewalk"],
            candidates=[
                make_candidate(
                    violation_category="road_occupying_vendor",
                    confidence=0.91,
                    evidence_reasoning="stall extends into sidewalk",
                    segmentation_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
                    relation_hint="stall overlaps sidewalk outside storefront boundary",
                )
            ],
        ),
    )

    assert captured
    first_payload = cast(PreliminaryRequestPayload, captured[0])
    user_content = message_parts(first_payload["messages"][1])
    judge_text = text_part(user_content[0])
    assert "category_code=road_occupying_vendor" in judge_text
    assert "mask_labels=stall, storefront_boundary, sidewalk_or_roadway" in judge_text
    assert "relation_hint=stall overlaps sidewalk outside storefront boundary" in judge_text
    assert "evidence_basis_summary=stall overlaps sidewalk boundary" in judge_text
    assert image_url_part(user_content[1]) == "s3://mock/overlay.png"
    assert "event_id=" not in judge_text
    assert "segmentation_status=" not in judge_text
    assert "risk_level=" not in judge_text
    assert "prelim_confidence=" not in judge_text
    assert "need_retake=" not in judge_text


def test_judge_http_client_can_use_configurable_templates() -> None:
    captured: list[RequesterPayload] = []

    def fake_requester(url: str, headers: dict[str, str], payload: RequesterPayload) -> JsonObject:
        captured.append(payload)
        return json_object({
            "choices": [
                {
                    "message": {
                        "content": {
                            "final_category": "road_occupying_vendor",
                            "final_confidence": 0.96,
                            "evidence_basis_match": True,
                            "violation_relation_confirmed": True,
                            "exception_excluded": True,
                            "archive_readiness": True,
                            "review_required": False,
                            "rejection_reason": None,
                            "violation_relation_summary": "stall overlaps sidewalk boundary",
                        }
                    }
                }
            ]
        })

    client = SglangVlmJudgeClient(
        endpoint="/mock/vlm/judge",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=ConfigurableInspectionPromptBuilder(
            preliminary_role_block="ROLE BLOCK",
            preliminary_scene_activation_block_template=(
                "scene_hint={scene_hint}; priority_categories={priority_categories}; "
                "open_risk_guidance={open_risk_guidance}"
            ),
            preliminary_category_focus_block_template="CATEGORY FOCUS\n{category_definitions}",
            preliminary_reasoning_block="REASONING BLOCK",
            preliminary_output_contract_block="OUTPUT BLOCK",
            preliminary_user_template="Analyze inspection image for violations.",
            judge_system_template="Custom judge system",
            judge_user_template=(
                "category_code={category_code}; mask_labels={mask_labels}; "
                "relation_hint={relation_hint}; evidence_basis_summary={evidence_basis_summary}"
            ),
            category_registry={},
            open_risk_guidance_default="Default open risk guidance.",
        ),
    )

    client.judge(
        event_id="evt_123",
        category_code="road_occupying_vendor",
        overlay_image="s3://mock/overlay.png",
        mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
        segmentation_status="ok",
        evidence_basis_summary="stall overlaps sidewalk boundary",
        preliminary=make_preliminary_result(
            environment_analysis="street storefront scene",
            scene_elements=["storefront", "stall", "sidewalk"],
            candidates=[
                make_candidate(
                    violation_category="road_occupying_vendor",
                    confidence=0.91,
                    evidence_reasoning="stall extends into sidewalk",
                    segmentation_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
                    relation_hint="stall overlaps sidewalk outside storefront boundary",
                )
            ],
        ),
    )

    first_payload = cast(PreliminaryRequestPayload, captured[0])
    assert first_payload["messages"][0]["content"] == "Custom judge system"
    user_content = message_parts(first_payload["messages"][1])
    judge_text = text_part(user_content[0])
    assert (
        judge_text
        == "category_code=road_occupying_vendor; mask_labels=stall, storefront_boundary, sidewalk_or_roadway; "
        "relation_hint=stall overlaps sidewalk outside storefront boundary; "
        "evidence_basis_summary=stall overlaps sidewalk boundary"
    )
    assert image_url_part(user_content[1]) == "s3://mock/overlay.png"
    assert "event_id=" not in judge_text
    assert "segmentation_status=" not in judge_text


def test_preliminary_http_client_requires_explicit_prompt_builder() -> None:
    with pytest.raises(ValueError, match="prompt_builder"):
        SglangVlmPreliminaryClient(
            endpoint="/mock/vlm/preliminary",
            model_name="inspection-vlm",
        )


def test_judge_http_client_requires_explicit_prompt_builder() -> None:
    with pytest.raises(ValueError, match="prompt_builder"):
        SglangVlmJudgeClient(
            endpoint="/mock/vlm/judge",
            model_name="inspection-vlm",
        )
