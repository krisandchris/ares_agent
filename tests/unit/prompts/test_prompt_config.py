from pathlib import Path

from ares_agent.domain.events import EventSeed
from ares_agent.infra.config import load_config
from ares_agent.prompts.builders import ConfigurableInspectionPromptBuilder
from ares_agent.prompts.scene_activation import SceneActivationContext
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
                "    role_block: |",
                "      ROLE BLOCK",
                "    global_policy_block: |",
                "      GLOBAL BLOCK",
                "    scene_activation_block_template: |",
                "      camera_id={camera_id}; location={location}; enabled_categories={enabled_categories}",
                "    reasoning_block: |",
                "      REASONING BLOCK",
                "    output_contract_block: |",
                "      OUTPUT CONTRACT BLOCK",
                "    user: |",
                "      Analyze under current scene policy.",
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

    assert config.prompts.preliminary.role_block.strip() == "ROLE BLOCK"
    assert "camera_id={camera_id}" in config.prompts.preliminary.scene_activation_block_template
    assert "custom judge model" in config.prompts.judge.system
    assert "category_code={category_code}" in config.prompts.judge.user


def test_configurable_prompt_builder_renders_judge_prompt_from_yaml_templates() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_role_block="ROLE BLOCK",
        preliminary_global_policy_block="GLOBAL BLOCK",
        preliminary_scene_activation_block_template=(
            "camera_id={camera_id}; location={location}; "
            "enabled_categories={enabled_categories}; location_constraints={location_constraints}"
        ),
        preliminary_reasoning_block="REASONING BLOCK",
        preliminary_output_contract_block="OUTPUT CONTRACT BLOCK",
        preliminary_user_template="Analyze under current scene policy.",
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


def test_configurable_prompt_builder_renders_preliminary_system_prompt_with_scene_activation_context() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_role_block="ROLE BLOCK",
        preliminary_global_policy_block="GLOBAL BLOCK",
        preliminary_scene_activation_block_template=(
            "camera_id={camera_id}; location={location}; scene_hint={scene_hint}; "
            "enabled_categories={enabled_categories}; disabled_categories={disabled_categories}; "
            "priority_categories={priority_categories}; location_constraints={location_constraints}"
        ),
        preliminary_reasoning_block="REASONING BLOCK",
        preliminary_output_contract_block="OUTPUT CONTRACT BLOCK",
        preliminary_user_template="Analyze under current scene policy.",
        judge_system_template="JUDGE SYSTEM",
        judge_user_template="JUDGE USER {category_code}",
    )

    messages = builder.build_preliminary_messages(
        seed=EventSeed(
            image_uri="s3://street/frame-011.jpg",
            camera_id="left",
            location="南山路",
            device_id="dog-31",
            task_id="patrol-sh-011",
            occur_time="2026-03-09T11:10:00Z",
        ),
        scene_activation_context=SceneActivationContext(
            camera_id="left",
            location="南山路",
            enabled_categories=["staff_not_wear_mask", "goods_blocking_road"],
            disabled_categories=["motor_vehicle_illegal_parking"],
            priority_categories=["staff_not_wear_mask"],
            location_constraints=["focus on storefront frontage"],
            scene_hint="storefront-facing side camera",
        ),
    )

    system_text = messages[0]["content"]
    assert "ROLE BLOCK" in system_text
    assert "GLOBAL BLOCK" in system_text
    assert "camera_id=left" in system_text
    assert "location=南山路" in system_text
    assert "enabled_categories=staff_not_wear_mask, goods_blocking_road" in system_text
    assert "disabled_categories=motor_vehicle_illegal_parking" in system_text
    assert "priority_categories=staff_not_wear_mask" in system_text
    assert "location_constraints=focus on storefront frontage" in system_text
    assert "OUTPUT CONTRACT BLOCK" in system_text
