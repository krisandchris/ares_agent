from pathlib import Path

from ares_agent.infra.config import load_config
from ares_agent.prompts.builders import ConfigurableInspectionPromptBuilder
from ares_agent.workflows.inspection_event_workflow import PreliminaryResult


def test_load_config_reads_yaml_prompt_templates(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text("{}", encoding="utf-8")
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text("{}", encoding="utf-8")
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture.name}",
                f"  segmentation_fixture: {sam_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
                "prompts:",
                "  preliminary:",
                "    system: |",
                "      You are a custom preliminary model.",
                "    user: |",
                "      Frame={frame_id}; Image={image_uri}",
                "  judge:",
                "    system: |",
                "      You are a custom judge model.",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert "custom preliminary model" in config.prompts.preliminary.system
    assert "Frame={frame_id}" in config.prompts.preliminary.user
    assert "custom judge model" in config.prompts.judge.system


def test_configurable_prompt_builder_renders_judge_prompt_from_yaml_templates() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_system_template="You are a custom preliminary model.",
        preliminary_user_template="Frame={frame_id}; Image={image_uri}",
        judge_system_template="You are a custom judge model.",
    )

    messages = builder.build_judge_messages(
        category_code="road_occupying_vendor",
        mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
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

    assert messages[0]["content"] == "You are a custom judge model."
    user_text = messages[1]["content"][0]["text"]
    assert "category_code=road_occupying_vendor" in user_text
    assert "mask_labels=stall, storefront_boundary, sidewalk_or_roadway" in user_text
    assert "relation_hint=stall overlaps sidewalk outside storefront boundary" in user_text
    assert "evidence_basis_summary=stall overlaps sidewalk boundary" in user_text
    assert "event_id=" not in user_text
    assert "segmentation_status=" not in user_text
    assert "vlm1_risk_level=" not in user_text
    assert "vlm1_prelim_confidence=" not in user_text
    assert "vlm1_need_retake=" not in user_text
