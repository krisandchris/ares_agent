from pathlib import Path

import pytest

from ares_agent.infra.config import load_config


def test_load_config_reads_callback_and_review_settings(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text("{}", encoding="utf-8")
    segmentation_fixture = tmp_path / "sam.json"
    segmentation_fixture.write_text("{}", encoding="utf-8")
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "agent:",
                "  service_name: street-inspection-agent",
                "orchestrator:",
                "  enable_async_refine: true",
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: true",
                "  send_refined: true",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture.name}",
                f"  segmentation_fixture: {segmentation_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
                "review:",
                "  enable_manual_review: true",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.agent.service_name == "street-inspection-agent"
    assert config.orchestrator.enable_async_refine is True
    assert config.callback.plugin == "http_callback"
    assert config.callback.send_preliminary is True
    assert config.callback.send_refined is True
    assert config.mock_clients.preliminary_fixture == prelim_fixture.resolve()
    assert config.mock_clients.segmentation_fixture == segmentation_fixture.resolve()
    assert config.mock_clients.evidence_judge_fixture == judge_fixture.resolve()
    assert config.review.enable_manual_review is True


def test_load_config_reads_scene_policies_and_structured_preliminary_prompt_blocks(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text("{}", encoding="utf-8")
    segmentation_fixture = tmp_path / "sam.json"
    segmentation_fixture.write_text("{}", encoding="utf-8")
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
                f"  segmentation_fixture: {segmentation_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
                "scene_policies:",
                "  camera_defaults:",
                "    front:",
                "      enabled_categories:",
                "        - motor_vehicle_illegal_parking",
                "      scene_hint: road-facing camera",
                "  location_defaults:",
                "    南山路:",
                "      enabled_categories:",
                "        - goods_blocking_road",
                "      location_constraints:",
                "        - focus on roadside and sidewalk occupation",
                "  overrides:",
                "    南山路:",
                "      left:",
                "        enabled_categories:",
                "          - staff_not_wear_mask",
                "          - goods_blocking_road",
                "        priority_categories:",
                "          - staff_not_wear_mask",
                "prompts:",
                "  preliminary:",
                "    role_block: |",
                "      ROLE BLOCK",
                "    global_policy_block: |",
                "      GLOBAL POLICY BLOCK",
                "    scene_activation_block_template: |",
                "      camera_id={camera_id}; location={location}; enabled_categories={enabled_categories}",
                "    reasoning_block: |",
                "      REASONING BLOCK",
                "    output_contract_block: |",
                "      OUTPUT CONTRACT BLOCK",
                "    user: |",
                "      Analyze this inspection image under the configured scene policy and output the required JSON.",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.scene_policies is not None
    assert config.scene_policies.camera_defaults["front"].scene_hint == "road-facing camera"
    assert config.scene_policies.location_defaults["南山路"].location_constraints == [
        "focus on roadside and sidewalk occupation"
    ]
    assert config.scene_policies.overrides["南山路"]["left"].enabled_categories == [
        "staff_not_wear_mask",
        "goods_blocking_road",
    ]
    assert config.prompts.preliminary.role_block.strip() == "ROLE BLOCK"
    assert "camera_id={camera_id}" in config.prompts.preliminary.scene_activation_block_template


def test_load_config_rejects_refined_without_preliminary_callback(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text("{}", encoding="utf-8")
    segmentation_fixture = tmp_path / "sam.json"
    segmentation_fixture.write_text("{}", encoding="utf-8")
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: false",
                "  send_refined: true",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture.name}",
                f"  segmentation_fixture: {segmentation_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="send_refined requires send_preliminary"):
        load_config(config_path)
