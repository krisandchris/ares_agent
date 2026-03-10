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
                "      category_code={category_code}; mask_labels={mask_labels}; relation_hint={relation_hint}; evidence_basis_summary={evidence_basis_summary}",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert "custom preliminary model" in config.prompts.preliminary.system
    assert "Frame={frame_id}" in config.prompts.preliminary.user
    assert "custom judge model" in config.prompts.judge.system
    assert "category_code={category_code}" in config.prompts.judge.user


def test_configurable_prompt_builder_renders_judge_prompt_from_yaml_templates() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_system_template="You are a custom preliminary model.",
        preliminary_user_template="Analyze inspection image for violations.",
        judge_system_template="You are a custom judge model.",
        judge_user_template=(
            "category_code={category_code}; mask_labels={mask_labels}; "
            "relation_hint={relation_hint}; evidence_basis_summary={evidence_basis_summary}"
        ),
    )

    messages = builder.build_judge_messages(
        category_code="road_occupying_vendor",
        overlay_image="s3://mock/overlay.png",
        mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
        evidence_basis_summary="stall overlaps sidewalk boundary",
    )

    assert messages[0]["content"] == "You are a custom judge model."
    user_content = messages[1]["content"]
    user_text = user_content[0]["text"]
    assert (
        user_text
        == "category_code=road_occupying_vendor; mask_labels=stall, storefront_boundary, sidewalk_or_roadway; "
        "relation_hint=stall overlaps sidewalk outside storefront boundary; "
        "evidence_basis_summary=stall overlaps sidewalk boundary"
    )
    assert user_content[1]["image_url"]["url"] == "s3://mock/overlay.png"
    assert "event_id=" not in user_text
    assert "segmentation_status=" not in user_text
