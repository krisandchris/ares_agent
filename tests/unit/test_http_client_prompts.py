from ares_agent.domain.events import EventSeed
from ares_agent.model_clients.http_clients import SglangVlmJudgeClient, SglangVlmPreliminaryClient
from ares_agent.prompts.builders import ConfigurableInspectionPromptBuilder, DefaultInspectionPromptBuilder
from ares_agent.workflows.inspection_event_workflow import PreliminaryResult


def test_preliminary_http_client_uses_prompt_builder_messages() -> None:
    captured: list[dict[str, object]] = []

    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        captured.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": {
                            "suspected_categories": ["goods_blocking_road"],
                            "risk_level": "medium",
                            "prelim_confidence": 0.84,
                            "need_retake": False,
                            "open_risk_hints": [],
                            "evidence_targets": ["goods_or_materials", "sidewalk", "passage_obstruction"],
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

    client.analyze(
        EventSeed(
            image_uri="s3://street/frame-011.jpg",
            frame_id="frame-011",
            device_id="dog-31",
            task_id="patrol-sh-011",
            occur_time="2026-03-09T11:10:00Z",
        )
    )

    assert captured
    assert captured[0]["messages"][0]["role"] == "system"
    assert captured[0]["messages"][1]["content"][1]["image_url"]["url"] == "s3://street/frame-011.jpg"


def test_judge_http_client_includes_preliminary_result_in_user_prompt() -> None:
    captured: list[dict[str, object]] = []

    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        captured.append(payload)
        return {
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
        }

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
        preliminary=PreliminaryResult(
            suspected_categories=["road_occupying_vendor"],
            risk_level="high",
            prelim_confidence=0.91,
            need_retake=False,
            open_risk_hints=["street obstruction risk"],
            evidence_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        ),
    )

    assert captured
    user_content = captured[0]["messages"][1]["content"]
    judge_text = user_content[0]["text"]
    assert "category_code=road_occupying_vendor" in judge_text
    assert "mask_labels=stall, storefront_boundary, sidewalk_or_roadway" in judge_text
    assert "relation_hint=stall overlaps sidewalk outside storefront boundary" in judge_text
    assert "evidence_basis_summary=stall overlaps sidewalk boundary" in judge_text
    assert user_content[1]["image_url"]["url"] == "s3://mock/overlay.png"
    assert "event_id=" not in judge_text
    assert "segmentation_status=" not in judge_text
    assert "risk_level=" not in judge_text
    assert "prelim_confidence=" not in judge_text
    assert "need_retake=" not in judge_text


def test_judge_http_client_can_use_configurable_templates() -> None:
    captured: list[dict[str, object]] = []

    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        captured.append(payload)
        return {
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
        }

    client = SglangVlmJudgeClient(
        endpoint="/mock/vlm/judge",
        model_name="inspection-vlm",
        requester=fake_requester,
        prompt_builder=ConfigurableInspectionPromptBuilder(
            preliminary_system_template="You are a custom preliminary model.",
            preliminary_user_template="Frame={frame_id}; Image={image_uri}",
            judge_system_template="Custom judge system",
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
        preliminary=PreliminaryResult(
            suspected_categories=["road_occupying_vendor"],
            risk_level="high",
            prelim_confidence=0.91,
            need_retake=False,
            open_risk_hints=["street obstruction risk"],
            evidence_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        ),
    )

    assert captured[0]["messages"][0]["content"] == "Custom judge system"
    user_content = captured[0]["messages"][1]["content"]
    judge_text = user_content[0]["text"]
    assert "category_code=road_occupying_vendor" in judge_text
    assert "mask_labels=stall, storefront_boundary, sidewalk_or_roadway" in judge_text
    assert "relation_hint=stall overlaps sidewalk outside storefront boundary" in judge_text
    assert "evidence_basis_summary=stall overlaps sidewalk boundary" in judge_text
    assert user_content[1]["image_url"]["url"] == "s3://mock/overlay.png"
    assert "event_id=" not in judge_text
    assert "segmentation_status=" not in judge_text
