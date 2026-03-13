from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.domain.events import EventSeed
from ares_agent.model_clients.http_clients import SglangVlmPreliminaryClient
from ares_agent.prompts.builders import DefaultInspectionPromptBuilder


def test_vlm1_client_parses_standard_violation_result() -> None:
    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {
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
        }

    client = SglangVlmPreliminaryClient(
        endpoint="/mock/vlm/preliminary",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=DefaultInspectionPromptBuilder(),
    )

    result = client.analyze(
        EventSeed(
            image_uri="s3://street/frame-101.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-31",
            task_id="patrol-sh-101",
            occur_time="2026-03-10T09:00:00Z",
        )
    )

    assert result.violation_category == "goods_blocking_road"
    assert result.open_risk_type == ""
    assert result.segmentation_targets == ["goods", "storefront_entrance", "sidewalk"]


def test_vlm1_client_parses_open_risk_result() -> None:
    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": {
                            "environment_analysis": "street scene with visible smoke near storefront",
                            "scene_elements": ["smoke", "storefront", "sidewalk"],
                            "evidence_reasoning": "visible smoke indicates a likely fire risk",
                            "segmentation_targets": ["smoke", "storefront", "sidewalk"],
                            "relation_hint": "smoke rises near storefront facade",
                            "violation_category": "open_risk",
                            "open_risk_type": "fire_or_smoke",
                            "confidence": 0.9,
                        }
                    }
                }
            ]
        }

    client = SglangVlmPreliminaryClient(
        endpoint="/mock/vlm/preliminary",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=DefaultInspectionPromptBuilder(),
    )

    result = client.analyze(
        EventSeed(
            image_uri="s3://street/frame-102.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-32",
            task_id="patrol-sh-102",
            occur_time="2026-03-10T09:05:00Z",
        )
    )

    assert result.violation_category == "open_risk"
    assert result.open_risk_type == "fire_or_smoke"


def test_vlm1_client_parses_none_result() -> None:
    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": {
                            "environment_analysis": "clean sidewalk with normal storefront frontage",
                            "scene_elements": ["storefront", "sidewalk"],
                            "evidence_reasoning": "no obvious violation or risk is visible",
                            "segmentation_targets": [],
                            "relation_hint": "",
                            "violation_category": "none",
                            "open_risk_type": "",
                            "confidence": 0.12,
                        }
                    }
                }
            ]
        }

    client = SglangVlmPreliminaryClient(
        endpoint="/mock/vlm/preliminary",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=DefaultInspectionPromptBuilder(),
    )

    result = client.analyze(
        EventSeed(
            image_uri="s3://street/frame-103.jpg",
            camera_id="left",
            location="水坊街",
            device_id="dog-33",
            task_id="patrol-sh-103",
            occur_time="2026-03-10T09:10:00Z",
        )
    )

    assert result.violation_category == "none"
    assert result.open_risk_type == ""
    assert result.segmentation_targets == []


def test_vlm1_client_normalizes_null_open_risk_type_for_non_open_risk() -> None:
    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": {
                            "environment_analysis": "clean roadway scene",
                            "scene_elements": ["roadway"],
                            "evidence_reasoning": "no obvious violation or risk is visible",
                            "segmentation_targets": [],
                            "relation_hint": "",
                            "violation_category": "none",
                            "open_risk_type": None,
                            "confidence": 0.1,
                        }
                    }
                }
            ]
        }

    client = SglangVlmPreliminaryClient(
        endpoint="/mock/vlm/preliminary",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=DefaultInspectionPromptBuilder(),
    )

    result = client.analyze(
        EventSeed(
            image_uri="s3://street/frame-106.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-35",
            task_id="patrol-sh-106",
            occur_time="2026-03-10T09:20:00Z",
        )
    )

    assert result.violation_category == "none"
    assert result.open_risk_type == ""


def test_vlm1_client_rejects_missing_required_fields() -> None:
    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": {
                            "environment_analysis": "storefront sidewalk scene",
                            "scene_elements": ["goods", "sidewalk"],
                            "violation_category": "goods_blocking_road",
                            "open_risk_type": "",
                            "confidence": 0.84,
                        }
                    }
                }
            ]
        }

    client = SglangVlmPreliminaryClient(
        endpoint="/mock/vlm/preliminary",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=DefaultInspectionPromptBuilder(),
    )

    with pytest.raises(Exception):
        client.analyze(
            EventSeed(
                image_uri="s3://street/frame-104.jpg",
                camera_id="right",
                location="南山路",
                device_id="dog-34",
                task_id="patrol-sh-104",
                occur_time="2026-03-10T09:15:00Z",
            )
        )


def test_vlm1_stub_endpoint_roundtrip_returns_openai_completion_shape(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"environment_analysis":"storefront sidewalk scene","scene_elements":["goods","sidewalk"],"evidence_reasoning":"goods block pedestrian passage","segmentation_targets":["goods","sidewalk"],"relation_hint":"goods block sidewalk","violation_category":"goods_blocking_road","open_risk_type":"","confidence":0.84}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"overlay_image":"s3://mock/overlay.png","mask_labels":["goods","sidewalk"],"relation_hint":"goods block sidewalk","segmentation_status":"ok","mask_uri":"s3://mock/mask.png","crop_image_uris":[],"overlay_image_uris":["s3://mock/overlay.png"],"evidence_basis_summary":"goods block sidewalk"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"goods_blocking_road","final_confidence":0.89,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"goods block sidewalk"}',
        encoding="utf-8",
    )
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture}",
                f"  segmentation_fixture: {sam_fixture}",
                f"  evidence_judge_fixture: {judge_fixture}",
            ]
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app(config_path=config_path))
    response = client.post(
        "/mock/vlm/preliminary",
        json={
            "model": "inspection-vlm",
            "messages": [
                {"role": "system", "content": "preliminary inspection"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "analyze this inspection image"},
                        {"type": "image_url", "image_url": {"url": "s3://street/frame-105.jpg"}},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
