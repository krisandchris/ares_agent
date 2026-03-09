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
    assert user_content[0]["text"].startswith("Analyze frame frame-010")
    assert user_content[1]["image_url"]["url"] == "s3://street/frame-010.jpg"


def test_default_prompt_builder_builds_judge_messages_with_preliminary_context() -> None:
    builder = DefaultInspectionPromptBuilder()
    preliminary = PreliminaryResult(
        suspected_categories=["road_occupying_vendor"],
        risk_level="high",
        prelim_confidence=0.91,
        need_retake=False,
        open_risk_hints=["street obstruction risk"],
        evidence_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
    )

    messages = builder.build_judge_messages(
        event_id="evt_123",
        category_code="road_occupying_vendor",
        evidence_basis_summary="stall overlaps sidewalk boundary",
        preliminary=preliminary,
    )

    assert messages[0]["role"] == "system"
    assert "evidence judge" in messages[0]["content"].lower()
    user_text = messages[1]["content"][0]["text"]
    assert "evt_123" in user_text
    assert "risk_level=high" in user_text
    assert "prelim_confidence=0.91" in user_text
    assert "need_retake=False" in user_text
    assert "road_occupying_vendor" not in user_text
    assert "evidence_targets=" not in user_text
    assert "open_risk_hints=" not in user_text
    assert "evidence_basis_summary=" not in user_text
