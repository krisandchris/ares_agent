from pathlib import Path

from ares_agent.api.app import _build_model_clients_from_config, _build_prompt_builder_from_config
from ares_agent.infra.config import load_config
from ares_agent.model_clients.http_clients import Sam3FastApiClient, SglangVlmJudgeClient, SglangVlmPreliminaryClient
from ares_agent.prompts.builders import ConfigurableInspectionPromptBuilder


def test_build_prompt_builder_from_config_uses_yaml_templates(tmp_path: Path) -> None:
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
                "        - focus on roadside occupation",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      PRELIM USER",
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
    builder = _build_prompt_builder_from_config(config)

    assert isinstance(builder, ConfigurableInspectionPromptBuilder)
    assert builder.preliminary_role_block.strip() == "ROLE BLOCK"
    assert builder.preliminary_global_policy_block.strip() == "GLOBAL BLOCK"
    assert builder.preliminary_user_template.strip() == "PRELIM USER"
    assert builder.judge_system_template.strip() == "JUDGE SYSTEM"
    assert builder.judge_user_template.strip() == "JUDGE USER {category_code}"


def test_build_model_clients_from_config_uses_http_clients_when_mode_is_http(tmp_path: Path) -> None:
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
                "        - focus on roadside occupation",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      PRELIM USER",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /mock/vlm/preliminary",
                "    model_name: inspection-vlm",
                "  judge:",
                "    base_url: http://127.0.0.1:30001",
                "    endpoint: /mock/vlm/judge",
                "    model_name: inspection-vlm",
                "  sam3:",
                "    base_url: http://127.0.0.1:8001",
                "    endpoint: /mock/sam3/segment",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    preliminary_client, segmentation_client, judge_client = _build_model_clients_from_config(config)

    assert isinstance(preliminary_client, SglangVlmPreliminaryClient)
    assert isinstance(segmentation_client, Sam3FastApiClient)
    assert isinstance(judge_client, SglangVlmJudgeClient)
    assert isinstance(preliminary_client.prompt_builder, ConfigurableInspectionPromptBuilder)
    assert isinstance(judge_client.prompt_builder, ConfigurableInspectionPromptBuilder)


def test_build_model_clients_from_config_requires_prompt_templates_in_http_mode(tmp_path: Path) -> None:
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
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /mock/vlm/preliminary",
                "    model_name: inspection-vlm",
                "  judge:",
                "    base_url: http://127.0.0.1:30001",
                "    endpoint: /mock/vlm/judge",
                "    model_name: inspection-vlm",
                "  sam3:",
                "    base_url: http://127.0.0.1:8001",
                "    endpoint: /mock/sam3/segment",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    try:
        _build_model_clients_from_config(config)
    except ValueError as exc:
        assert "prompt templates" in str(exc)
    else:
        raise AssertionError("expected http mode without prompts to fail")
