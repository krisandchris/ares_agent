"""Tests for data_engine VLM clients."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ares_agent.domain.events import EventSeed
from ares_agent.model_clients.data_engine_clients import (
    DataEngineStep1Client,
    DataEngineStep2Client,
    _strip_json_fence,
)
from ares_agent.prompts.data_engine_prompts import (
    DataEngineStep1PromptBuilder,
    DataEngineStep2PromptBuilder,
)
from ares_agent.workflows.inspection_event_workflow import PreliminaryResult

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "data_engine"


def _make_seed() -> EventSeed:
    return EventSeed(
        image_uri="http://example.com/img.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-01",
        task_id="test-001",
        occur_time="2026-05-08T10:00:00Z",
    )


def _mock_requester(responses: list[dict], call_log: list | None = None):
    """Return a requester that cycles through the given responses."""
    idx = 0

    def requester(url: str, headers: dict, payload: dict) -> dict:
        nonlocal idx
        if call_log is not None:
            call_log.append({"url": url, "payload": payload})
        resp = responses[idx % len(responses)]
        idx += 1
        return resp

    return requester


def test_strip_json_fence_plain() -> None:
    assert _strip_json_fence('{"key": "value"}') == '{"key": "value"}'


def test_strip_json_fence_with_fence() -> None:
    text = '```json\n{"key": "value"}\n```'
    assert _strip_json_fence(text) == '{"key": "value"}'


def test_strip_json_fence_with_fence_no_lang() -> None:
    text = '```\n{"key": "value"}\n```'
    assert _strip_json_fence(text) == '{"key": "value"}'


STAGE1_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "environment_analysis": "测试场景",
                        "scene_elements": ["人行道", "电动自行车"],
                        "key_anchors": ["pedestrian_walkway"],
                        "key_relations": [
                            {
                                "subject": "电动自行车",
                                "relation": "occupying",
                                "object": "pedestrian_walkway",
                                "description": "画面左侧电动自行车占据人行道",
                                "bbox": [100, 200, 300, 400],
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            }
        }
    ]
}


def test_step1_client_analyze() -> None:
    call_log: list = []
    builder = DataEngineStep1PromptBuilder.from_files(
        registry_path=CONFIG_DIR / "stage1_registry.yaml",
        system_template_path=CONFIG_DIR / "stage1_system_core.txt",
        user_template_path=CONFIG_DIR / "stage1_user_prompt.txt",
    )
    client = DataEngineStep1Client(
        endpoint="http://fake-vlm/v1",
        model_name="test-model",
        prompt_builder=builder,
        requester=_mock_requester([STAGE1_RESPONSE], call_log),
    )
    result = client.analyze(_make_seed())
    assert isinstance(result, PreliminaryResult)
    assert result.environment_analysis == "测试场景"
    assert len(call_log) == 1
    messages = call_log[0]["payload"]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"


STAGE2_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps(
                    {
                        "sample_id": "evt_test",
                        "fact_verifications": [
                            {
                                "relation_index": 0,
                                "subject": "电动自行车",
                                "relation": "occupying",
                                "object": "pedestrian_walkway",
                                "bbox": [100, 200, 300, 400],
                                "visibility_level": "clear",
                                "information_loss_type": "none",
                                "key_attributes_visible": ["wheel", "body"],
                                "subject_visible": True,
                                "subject_match": True,
                                "bbox_observation": "电动自行车在bbox内",
                                "global_context_observation": "人行道被占据",
                                "verification_result": "supported",
                                "verification_confidence": 0.9,
                            }
                        ],
                        "candidates": [
                            {
                                "violation_category": ["nonmotor_vehicle_illegal_parking"],
                                "evidence_relation_indices": [0],
                                "evidence_reasoning": "电动自行车占据人行道",
                                "relation_hint": "occupying",
                                "segmentation_targets": ["电动自行车"],
                                "confidence": 0.85,
                                "sample_category": "positive samples",
                            }
                        ],
                    },
                    ensure_ascii=False,
                )
            }
        }
    ]
}


def test_step2_client_judge() -> None:
    builder = DataEngineStep2PromptBuilder.from_files(
        registry_path=CONFIG_DIR / "stage2_rule_registry.yaml",
        system_template_path=CONFIG_DIR / "stage2_system_core.txt",
        user_template_path=CONFIG_DIR / "stage2_user_prompt.txt",
    )
    client = DataEngineStep2Client(
        endpoint="http://fake-vlm/v1",
        model_name="test-model",
        prompt_builder=builder,
        requester=_mock_requester([STAGE2_RESPONSE]),
    )
    preliminary = PreliminaryResult(
        environment_analysis="test",
        scene_elements=[],
        candidates=[],
    )
    result = client.judge(
        event_id="evt_test",
        category_code="none",
        overlay_image="http://example.com/img.jpg",
        mask_labels=[],
        relation_hint="",
        evidence_basis_summary="",
        preliminary=preliminary,
    )
    assert result.final_category == "nonmotor_vehicle_illegal_parking"
    assert result.final_confidence == 0.85
    assert result.evidence_basis_match is True
