from pathlib import Path

import yaml

from ares_agent.domain.events import EventSeed
from ares_agent.infra.config import load_config
from ares_agent.prompts.builders import ConfigurableInspectionPromptBuilder
from ares_agent.prompts.scene_activation import SceneActivationContext
from type_helpers import image_url_part, message_parts, text_part


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
                "    scene_activation_block_template: |",
                "      scene_hint={scene_hint}; priority_categories={priority_categories}; open_risk_guidance={open_risk_guidance}",
                "    category_focus_block_template: |",
                "      category_definitions:",
                "      {category_definitions}",
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
                "category_registry:",
                "  goods_blocking_road:",
                "    definition: goods on sidewalk",
                "    common_objects:",
                "      - goods",
                "      - sidewalk",
                "    relation_focus:",
                "      - obstruct_pedestrian_passage",
                "open_risk_registry:",
                "  guidance: |",
                "    If obvious risk exists outside prioritized categories, output open_risk.",
                "  examples:",
                "    - fire_or_smoke",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert config.prompts is not None

    assert config.prompts.preliminary.role_block.strip() == "ROLE BLOCK"
    assert "scene_hint={scene_hint}" in config.prompts.preliminary.scene_activation_block_template
    assert "{category_definitions}" in config.prompts.preliminary.category_focus_block_template
    assert "custom judge model" in config.prompts.judge.system
    assert "category_code={category_code}" in config.prompts.judge.user
    assert config.category_registry["goods_blocking_road"].common_objects == ["goods", "sidewalk"]
    assert config.open_risk_registry.guidance.strip() == (
        "If obvious risk exists outside prioritized categories, output open_risk."
    )


def test_configurable_prompt_builder_renders_judge_prompt_from_yaml_templates() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_role_block="ROLE BLOCK",
        preliminary_scene_activation_block_template=(
            "scene_hint={scene_hint}; priority_categories={priority_categories}; "
            "open_risk_guidance={open_risk_guidance}"
        ),
        preliminary_category_focus_block_template="CATEGORY FOCUS\n{category_definitions}",
        preliminary_reasoning_block="REASONING BLOCK",
        preliminary_output_contract_block="OUTPUT CONTRACT BLOCK",
        preliminary_user_template="Analyze under current scene policy.",
        judge_system_template="You are a custom judge model.",
        judge_user_template=(
            "category_code={category_code}; mask_labels={mask_labels}; "
            "relation_hint={relation_hint}; evidence_basis_summary={evidence_basis_summary}"
        ),
        category_registry={},
        open_risk_guidance_default="Default open risk guidance.",
    )

    messages = builder.build_judge_messages(
        category_code="road_occupying_vendor",
        overlay_image="s3://mock/overlay.png",
        mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        relation_hint="stall overlaps sidewalk outside storefront boundary",
        evidence_basis_summary="stall overlaps sidewalk boundary",
    )

    assert messages[0]["content"] == "You are a custom judge model."
    user_content = message_parts(messages[1])
    user_text = text_part(user_content[0])
    assert (
        user_text
        == "category_code=road_occupying_vendor; mask_labels=stall, storefront_boundary, sidewalk_or_roadway; "
        "relation_hint=stall overlaps sidewalk outside storefront boundary; "
        "evidence_basis_summary=stall overlaps sidewalk boundary"
    )
    assert image_url_part(user_content[1]) == "s3://mock/overlay.png"
    assert "event_id=" not in user_text
    assert "segmentation_status=" not in user_text


def test_configurable_prompt_builder_renders_preliminary_system_prompt_with_scene_activation_context() -> None:
    builder = ConfigurableInspectionPromptBuilder(
        preliminary_role_block="ROLE BLOCK",
        preliminary_scene_activation_block_template=(
            "scene_hint={scene_hint}; priority_categories={priority_categories}; "
            "open_risk_guidance={open_risk_guidance}"
        ),
        preliminary_category_focus_block_template="CATEGORY FOCUS\n{category_definitions}",
        preliminary_reasoning_block="REASONING BLOCK",
        preliminary_output_contract_block="OUTPUT CONTRACT BLOCK",
        preliminary_user_template="Analyze under current scene policy.",
        judge_system_template="JUDGE SYSTEM",
        judge_user_template="JUDGE USER {category_code}",
        category_registry={
            "staff_not_wear_mask": {
                "definition": "catering staff missing mask",
                "common_objects": ["staff", "mask", "counter"],
                "relation_focus": ["staff_without_mask"],
                "exceptions": [],
            },
            "goods_blocking_road": {
                "definition": "goods block sidewalk",
                "common_objects": ["goods", "sidewalk"],
                "relation_focus": ["obstruct_pedestrian_passage"],
                "exceptions": [],
            },
        },
        open_risk_guidance_default="Default open risk guidance.",
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
            open_risk_guidance="If strong evidence of uncategorized risk exists, output open_risk.",
        ),
    )

    system_text = messages[0]["content"]
    assert "ROLE BLOCK" in system_text
    assert "camera_id=" not in system_text
    assert "location=南山路" not in system_text
    assert "enabled_categories=" not in system_text
    assert "disabled_categories=" not in system_text
    assert "priority_categories=staff_not_wear_mask" in system_text
    assert "open_risk_guidance=If strong evidence of uncategorized risk exists, output open_risk." in system_text
    assert "CATEGORY FOCUS" in system_text
    assert "definition: catering staff missing mask" in system_text
    assert "goods block sidewalk" not in system_text
    assert "OUTPUT CONTRACT BLOCK" in system_text


def test_example_prompt_config_keeps_vlm1_candidate_fields_in_required_order() -> None:
    prompt_config = yaml.safe_load(Path("config/prompt_config.example.yaml").read_text(encoding="utf-8"))
    output_contract = prompt_config["prompts"]["preliminary"]["output_contract_block"]
    reasoning_block = prompt_config["prompts"]["preliminary"]["reasoning_block"]

    expected_order = [
        "evidence_reasoning",
        "relation_hint",
        "segmentation_targets",
        "violation_category",
        "open_risk_type",
        "confidence",
    ]

    positions = [output_contract.index(field) for field in expected_order]
    assert positions == sorted(positions)
    assert "If multiple distinct violations are visible, output multiple candidates rather than merging them into one." in reasoning_block
