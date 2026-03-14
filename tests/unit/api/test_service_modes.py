from pathlib import Path
import json

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.infra.event_store import InMemoryEventStore
from ares_agent.services.image_uri_resolver import ImageUriResolver


def _parse_json_lines(output: str) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        parsed.append(json.loads(line))
    return parsed


def test_create_app_runs_vlm1_only_chain_and_preserves_minio_http_url(tmp_path: Path) -> None:
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
                "orchestrator:",
                "  chain_mode: vlm1_only",
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: true",
                "  send_refined: false",
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
    callback_payloads: list[dict[str, object]] = []

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

    client = TestClient(
        create_app(
            config_path=config_path,
            callback_sender=lambda url, headers, payload: callback_payloads.append(payload) or {"status_code": 200},
            event_store=InMemoryEventStore(),
            model_requesters={"preliminary": fake_requester},
        )
    )

    minio_url = "https://minio.example.com/street-images/patrol/frame-001.jpg"
    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": minio_url,
            "camera_id": "front",
            "location": "南山路",
            "device_id": "dog-17",
            "task_id": "patrol-sh-001",
            "occur_time": "2026-03-09T10:00:00Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "preliminary"
    assert body["preliminary_feedback"]["violation_category"] == "motor_vehicle_illegal_parking"
    assert body["preliminary_feedback"]["async_enqueued"] is False
    assert [payload["stage"] for payload in callback_payloads] == ["preliminary"]
    assert captured_payloads[0]["messages"][1]["content"][1]["image_url"]["url"] == minio_url


def test_create_app_resolves_s3_uri_for_vlm1_only_chain(tmp_path: Path) -> None:
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
                "orchestrator:",
                "  chain_mode: vlm1_only",
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: false",
                "  send_refined: false",
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

    class FakeResolver:
        def resolve(self, image_uri: str) -> str:
            assert image_uri == "s3://test-bucket/folder/image.jpg"
            return "https://minio.example.com/presigned/test-bucket/folder/image.jpg?X-Amz-Signature=demo"

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

    client = TestClient(
        create_app(
            config_path=config_path,
            event_store=InMemoryEventStore(),
            model_requesters={"preliminary": fake_requester},
            image_uri_resolver=FakeResolver(),
        )
    )

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://test-bucket/folder/image.jpg",
            "camera_id": "front",
            "location": "南山路",
            "device_id": "dog-17",
            "task_id": "patrol-sh-002",
            "occur_time": "2026-03-09T10:20:00Z",
        },
    )

    assert response.status_code == 200
    assert set(response.json()) == {"event_id", "stage", "frame_seed", "preliminary"}
    assert response.json()["stage"] == "preliminary"
    assert set(response.json()["preliminary"]) == {"environment_analysis", "scene_elements", "candidates"}
    assert captured_payloads[0]["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "https://minio.example.com/presigned/test-bucket/folder/image.jpg"
    )


def test_vlm1_only_logs_keep_root_event_id_even_after_image_uri_resolution(
    tmp_path: Path,
    capsys,
) -> None:
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
                "orchestrator:",
                "  chain_mode: vlm1_only",
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: false",
                "  send_refined: false",
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

    class FakeResolver:
        def resolve(self, image_uri: str) -> str:
            return "https://minio.example.com/presigned/test-bucket/folder/image.jpg?X-Amz-Signature=demo"

    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
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

    client = TestClient(
        create_app(
            config_path=config_path,
            event_store=InMemoryEventStore(),
            model_requesters={"preliminary": fake_requester},
            image_uri_resolver=FakeResolver(),
        )
    )

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://test-bucket/folder/image.jpg",
            "camera_id": "front",
            "location": "南山路",
            "device_id": "dog-17",
            "task_id": "patrol-sh-002",
            "occur_time": "2026-03-09T10:20:00Z",
        },
    )

    assert response.status_code == 200
    root_event_id = response.json()["event_id"]
    logs = _parse_json_lines(capsys.readouterr().out)
    model_logs = [entry for entry in logs if entry.get("event") == "model.request.succeeded"]
    assert model_logs
    assert all(entry["event_id"] == root_event_id for entry in model_logs)


def test_vlm1_only_can_ignore_preliminary_callback_failure_when_configured(tmp_path: Path) -> None:
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
                "orchestrator:",
                "  chain_mode: vlm1_only",
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: true",
                "  send_refined: false",
                "  block_on_preliminary_failure: false",
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

    def fake_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
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

    def failing_callback_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("callback unavailable")

    client = TestClient(
        create_app(
            config_path=config_path,
            callback_sender=failing_callback_sender,
            event_store=InMemoryEventStore(),
            model_requesters={"preliminary": fake_requester},
        )
    )

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "camera_id": "front",
            "location": "南山路",
            "device_id": "dog-17",
            "task_id": "patrol-sh-001",
            "occur_time": "2026-03-09T10:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json()["stage"] == "preliminary"
