from pathlib import Path
from base64 import b64decode
import pytest

from ares_agent.tools.vlm1_tester import DEFAULT_CONFIG_PATH, create_gradio_app, run_vlm1_preliminary_test


def test_vlm1_tester_defaults_to_service_config_example() -> None:
    assert DEFAULT_CONFIG_PATH == Path("config/service_config.example.yaml")
    assert create_gradio_app.__kwdefaults__ is not None
    assert create_gradio_app.__kwdefaults__["config_path"] == Path.cwd() / DEFAULT_CONFIG_PATH


def test_run_vlm1_preliminary_test_returns_prompt_preview_and_result(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"environment_analysis":"street storefront scene","scene_elements":["storefront","goods","sidewalk"],"evidence_reasoning":"goods extend onto sidewalk","violation_category":"goods_blocking_road","open_risk_type":"","confidence":0.84,"segmentation_targets":["goods","storefront_entrance","sidewalk"],"relation_hint":"goods placed outside storefront and block sidewalk"}',
        encoding="utf-8",
    )
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
                "    left:",
                "      enabled_categories:",
                "        - goods_blocking_road",
                "      priority_categories:",
                "        - goods_blocking_road",
                "      scene_hint: storefront-facing camera",
                "  location_defaults:",
                "    南山路:",
                "      enabled_categories:",
                "        - goods_blocking_road",
                "      location_constraints:",
                "        - focus on storefront frontage and sidewalk occupation",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      Analyze this inspection image.",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
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
                "model_clients:",
                "  mode: mock",
            ]
        ),
        encoding="utf-8",
    )

    result = run_vlm1_preliminary_test(
        config_path=config_path,
        image_uri="s3://street/frame-001.jpg",
        camera_id="left",
        location="南山路",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )

    assert result.event_id.startswith("evt_")
    assert result.scene_activation.enabled_categories == ["goods_blocking_road"]
    assert result.scene_activation.location_constraints == [
        "focus on storefront frontage and sidewalk occupation"
    ]
    assert result.system_prompt.startswith("ROLE BLOCK")
    assert "goods_blocking_road" in result.system_prompt
    assert result.user_prompt == "Analyze this inspection image."
    assert result.input_image_uri == "s3://street/frame-001.jpg"
    assert result.messages[1]["content"][1]["image_url"]["url"] == "s3://street/frame-001.jpg"
    assert result.result.violation_category == "goods_blocking_road"


def test_run_vlm1_preliminary_test_supports_http_mode_with_custom_requester(tmp_path: Path) -> None:
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
                "      priority_categories:",
                "        - motor_vehicle_illegal_parking",
                "      scene_hint: road-facing camera",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      Analyze this inspection image.",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
                "category_registry:",
                "  motor_vehicle_illegal_parking:",
                "    definition: vehicle occupies prohibited area",
                "    common_objects:",
                "      - motor_vehicle",
                "      - blind_path",
                "    relation_focus:",
                "      - vehicle_occupies_prohibited_area",
                "open_risk_registry:",
                "  guidance: |",
                "    If obvious risk exists outside prioritized categories, output open_risk.",
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /v1/chat/completions",
                "    model_name: inspection-vlm",
                "    timeout_ms: 12000",
            ]
        ),
        encoding="utf-8",
    )

    captured_payloads: list[dict[str, object]] = []

    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        captured_payloads.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": {
                            "environment_analysis": "road scene",
                            "scene_elements": ["motor_vehicle", "blind_path"],
                            "evidence_reasoning": "vehicle occupies blind path",
                            "violation_category": "motor_vehicle_illegal_parking",
                            "open_risk_type": "",
                            "confidence": 0.9,
                            "segmentation_targets": ["motor_vehicle", "blind_path"],
                            "relation_hint": "vehicle occupies blind path",
                        }
                    }
                }
            ]
        }

    result = run_vlm1_preliminary_test(
        config_path=config_path,
        image_uri="https://example.com/frame-010.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-18",
        task_id="patrol-sh-002",
        occur_time="2026-03-09T10:05:00Z",
        preliminary_requester=fake_requester,
    )

    assert result.result.violation_category == "motor_vehicle_illegal_parking"
    assert captured_payloads[0]["model"] == "inspection-vlm"
    assert result.user_prompt == "Analyze this inspection image."


def test_run_vlm1_preliminary_test_converts_uploaded_image_to_data_url_in_http_mode(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text("{}", encoding="utf-8")
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text("{}", encoding="utf-8")
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text("{}", encoding="utf-8")
    uploaded_image = tmp_path / "uploaded.jpg"
    uploaded_image.write_bytes(b"jpeg-binary")
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
                "      priority_categories:",
                "        - motor_vehicle_illegal_parking",
                "      scene_hint: road-facing camera",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      Analyze this inspection image.",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
                "category_registry:",
                "  motor_vehicle_illegal_parking:",
                "    definition: vehicle occupies prohibited area",
                "    common_objects:",
                "      - motor_vehicle",
                "    relation_focus:",
                "      - vehicle_occupies_prohibited_area",
                "open_risk_registry:",
                "  guidance: |",
                "    If obvious risk exists outside prioritized categories, output open_risk.",
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /v1/chat/completions",
                "    model_name: inspection-vlm",
                "    timeout_ms: 12000",
            ]
        ),
        encoding="utf-8",
    )

    captured_payloads: list[dict[str, object]] = []

    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        captured_payloads.append(payload)
        return {
            "choices": [
                {
                    "message": {
                        "content": {
                            "environment_analysis": "road scene",
                            "scene_elements": ["motor_vehicle"],
                            "evidence_reasoning": "vehicle occupies prohibited area",
                            "violation_category": "motor_vehicle_illegal_parking",
                            "open_risk_type": "",
                            "confidence": 0.9,
                            "segmentation_targets": ["motor_vehicle"],
                            "relation_hint": "vehicle occupies prohibited area",
                        }
                    }
                }
            ]
        }

    result = run_vlm1_preliminary_test(
        config_path=config_path,
        image_uri="s3://street/ignored.jpg",
        uploaded_image_path=uploaded_image,
        camera_id="front",
        location="南山路",
        device_id="dog-18",
        task_id="patrol-sh-005",
        occur_time="2026-03-09T10:12:00Z",
        mode_override="http",
        preliminary_requester=fake_requester,
    )

    image_url = result.messages[1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")
    assert b64decode(image_url.split(",", 1)[1]) == b"jpeg-binary"


def test_run_vlm1_preliminary_test_prefers_uploaded_image_file_and_exposes_messages(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"environment_analysis":"road scene","scene_elements":["motor_vehicle","blind_path"],"evidence_reasoning":"vehicle occupies blind path","violation_category":"motor_vehicle_illegal_parking","open_risk_type":"","confidence":0.9,"segmentation_targets":["motor_vehicle","blind_path"],"relation_hint":"vehicle occupies blind path"}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text("{}", encoding="utf-8")
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text("{}", encoding="utf-8")
    uploaded_image = tmp_path / "uploaded.jpg"
    uploaded_image.write_bytes(b"fake-image")
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
                "      priority_categories:",
                "        - motor_vehicle_illegal_parking",
                "      scene_hint: road-facing camera",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      Analyze this inspection image.",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
                "category_registry:",
                "  motor_vehicle_illegal_parking:",
                "    definition: vehicle occupies prohibited area",
                "    common_objects:",
                "      - motor_vehicle",
                "      - blind_path",
                "    relation_focus:",
                "      - vehicle_occupies_prohibited_area",
                "open_risk_registry:",
                "  guidance: |",
                "    If obvious risk exists outside prioritized categories, output open_risk.",
                "model_clients:",
                "  mode: mock",
            ]
        ),
        encoding="utf-8",
    )

    result = run_vlm1_preliminary_test(
        config_path=config_path,
        image_uri="s3://street/ignored.jpg",
        uploaded_image_path=uploaded_image,
        camera_id="front",
        location="南山路",
        device_id="dog-18",
        task_id="patrol-sh-003",
        occur_time="2026-03-09T10:10:00Z",
    )

    assert result.input_image_uri == uploaded_image.resolve().as_uri()
    assert result.messages[1]["content"][1]["image_url"]["url"] == uploaded_image.resolve().as_uri()
    assert result.result.violation_category == "motor_vehicle_illegal_parking"


def test_run_vlm1_preliminary_test_allows_mode_override_to_mock(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"environment_analysis":"road scene","scene_elements":["motor_vehicle","blind_path"],"evidence_reasoning":"vehicle occupies blind path","violation_category":"motor_vehicle_illegal_parking","open_risk_type":"","confidence":0.9,"segmentation_targets":["motor_vehicle","blind_path"],"relation_hint":"vehicle occupies blind path"}',
        encoding="utf-8",
    )
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
                "      priority_categories:",
                "        - motor_vehicle_illegal_parking",
                "      scene_hint: road-facing camera",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      Analyze this inspection image.",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
                "category_registry:",
                "  motor_vehicle_illegal_parking:",
                "    definition: vehicle occupies prohibited area",
                "    common_objects:",
                "      - motor_vehicle",
                "    relation_focus:",
                "      - vehicle_occupies_prohibited_area",
                "open_risk_registry:",
                "  guidance: |",
                "    If obvious risk exists outside prioritized categories, output open_risk.",
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /v1/chat/completions",
                "    model_name: inspection-vlm",
            ]
        ),
        encoding="utf-8",
    )

    result = run_vlm1_preliminary_test(
        config_path=config_path,
        image_uri="s3://street/frame-011.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-18",
        task_id="patrol-sh-004",
        occur_time="2026-03-09T10:11:00Z",
        mode_override="mock",
    )

    assert result.result.violation_category == "motor_vehicle_illegal_parking"


def test_run_vlm1_preliminary_test_rejects_unsupported_image_uri_in_http_mode(tmp_path: Path) -> None:
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
                "      priority_categories:",
                "        - motor_vehicle_illegal_parking",
                "      scene_hint: road-facing camera",
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
                "      OUTPUT BLOCK",
                "    user: |",
                "      Analyze this inspection image.",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "    user: |",
                "      JUDGE USER {category_code}",
                "category_registry:",
                "  motor_vehicle_illegal_parking:",
                "    definition: vehicle occupies prohibited area",
                "    common_objects:",
                "      - motor_vehicle",
                "    relation_focus:",
                "      - vehicle_occupies_prohibited_area",
                "open_risk_registry:",
                "  guidance: |",
                "    If obvious risk exists outside prioritized categories, output open_risk.",
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /v1/chat/completions",
                "    model_name: inspection-vlm",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="HTTP mode requires image_uri to use http, https, or data URL"):
        run_vlm1_preliminary_test(
            config_path=config_path,
            image_uri="s3://street/frame-012.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-18",
            task_id="patrol-sh-006",
            occur_time="2026-03-09T10:13:00Z",
        )
