from ares_agent.domain.events import EventSeed
from ares_agent.prompts.builders import DefaultInspectionPromptBuilder
from ares_agent.workflows.inspection_event_workflow import PreliminaryResult


def test_default_prompt_builder_builds_preliminary_messages_from_event_seed() -> None:
    builder = DefaultInspectionPromptBuilder()
    seed = EventSeed(
        image_uri="s3://street/frame-010.jpg",
        frame_id="frame-010",
        device_id="dog-30",
        task_id="patrol-sh-010",
        occur_time="2026-03-09T11:00:00Z",
    )

    messages = builder.build_preliminary_messages(seed)

    assert messages[0]["role"] == "system"
    assert "preliminary inspection" in messages[0]["content"].lower()
    user_content = messages[1]["content"]
    assert user_content[0]["text"] == "Analyze inspection image for violations."
    assert user_content[1]["image_url"]["url"] == "s3://street/frame-010.jpg"


def test_default_prompt_builder_builds_judge_messages_with_preliminary_context() -> None:
    builder = DefaultInspectionPromptBuilder()
    preliminary = PreliminaryResult(
        environment_analysis="street storefront scene",
        scene_elements=["storefront", "stall", "sidewalk"],
        evidence_reasoning="stall extends into sidewalk",
        segmentation_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
        violation_category="road_occupying_vendor",
        open_risk_type="",
        confidence=0.91,
    )

    messages = builder.build_judge_messages(
        category_code="road_occupying_vendor",
        overlay_image="s3://mock/overlay.png",
        mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
        evidence_basis_summary="stall overlaps sidewalk boundary",
    )

    assert messages[0]["role"] == "system"
    assert "evidence judge" in messages[0]["content"].lower()
    user_content = messages[1]["content"]
    user_text = user_content[0]["text"]
    assert "category_code=road_occupying_vendor" in user_text
    assert "mask_labels=stall, storefront_boundary, sidewalk_or_roadway" in user_text
    assert "relation_hint=stall overlaps sidewalk outside storefront boundary" in user_text
    assert "evidence_basis_summary=stall overlaps sidewalk boundary" in user_text
    assert user_content[1]["image_url"]["url"] == "s3://mock/overlay.png"
    assert "event_id=" not in user_text
    assert "segmentation_status=" not in user_text
    assert "risk_level=" not in user_text
    assert "prelim_confidence=" not in user_text
    assert "need_retake=" not in user_text
