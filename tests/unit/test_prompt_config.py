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
                "    user: |",
                "      Event={event_id}; Category={category_code}; Risk={risk_level}; Evidence={evidence_basis_summary}",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert "custom preliminary model" in config.prompts.preliminary.system
    assert "Frame={frame_id}" in config.prompts.preliminary.user
    assert "custom judge model" in config.prompts.judge.system
    assert "Risk={risk_level}" in config.prompts.judge.user


def test_configurable_prompt_builder_renders_judge_prompt_from_yaml_templates() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_system_template="ignored",
        preliminary_user_template="ignored",
        judge_system_template="You are a custom judge model.",
        judge_user_template=(
            "Event={event_id}; Category={category_code}; Risk={risk_level}; "
            "Targets={evidence_targets}; Hints={open_risk_hints}; Evidence={evidence_basis_summary}"
        ),
    )

    messages = builder.build_judge_messages(
        event_id="evt_123",
        category_code="road_occupying_vendor",
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
    assert "Event=evt_123" in user_text
    assert "Category=road_occupying_vendor" in user_text
    assert "Risk=high" in user_text
    assert "Targets=stall, storefront_boundary, sidewalk_or_roadway" in user_text
    assert "Hints=street obstruction risk" in user_text
