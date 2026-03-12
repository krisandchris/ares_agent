from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.infra.event_store import InMemoryEventStore


def test_http_flow_success_and_query_roundtrip(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"environment_analysis":"street parking scene","scene_elements":["motor_vehicle","sidewalk"],"evidence_reasoning":"vehicle occupies sidewalk space","violation_category":"motor_vehicle_illegal_parking","open_risk_type":"","confidence":0.9,"segmentation_targets":["motor_vehicle","sidewalk_or_bus_stop_or_unmarked_area"],"relation_hint":"vehicle occupies sidewalk space"}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"mask_uri":"s3://mock-evidence/motor_vehicle_illegal_parking_mask.png","crop_image_uris":["s3://mock-evidence/motor_vehicle_illegal_parking_crop_1.png"],"overlay_image_uris":["s3://mock-evidence/motor_vehicle_illegal_parking_overlay.png"],"evidence_basis_summary":"the motor vehicle occupies sidewalk space"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"motor_vehicle_illegal_parking","final_confidence":0.92,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"the vehicle occupies the sidewalk"}',
        encoding="utf-8",
    )
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  timeout_ms: 3000",
                "  retry:",
                "    max_attempts: 3",
                "    backoff_ms: 1000",
                "  send_preliminary: true",
                "  send_refined: true",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture}",
                f"  segmentation_fixture: {sam_fixture}",
                f"  evidence_judge_fixture: {judge_fixture}",
            ]
        ),
        encoding="utf-8",
    )
    callback_payloads: list[dict[str, object]] = []

    def fake_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        callback_payloads.append(payload)
        return {"status_code": 200, "backend_trace_id": "trace-it"}

    client = TestClient(
        create_app(
            config_path=config_path,
            callback_sender=fake_sender,
            event_store=InMemoryEventStore(),
        )
    )

    create_response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-003.jpg",
            "camera_id": "front",
            "location": "南山路",
            "device_id": "dog-19",
            "task_id": "patrol-sh-003",
            "occur_time": "2026-03-09T10:20:00Z",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    query_response = client.get(f"/v1/events/{created['event_id']}")

    assert query_response.status_code == 200
    queried = query_response.json()
    assert queried["result"]["refined_feedback"]["final_category"] == "motor_vehicle_illegal_parking"
    assert [payload["stage"] for payload in callback_payloads] == ["preliminary", "refined"]


def test_http_flow_failure_and_query_roundtrip(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"environment_analysis":"storefront sidewalk scene","scene_elements":["goods","sidewalk"],"evidence_reasoning":"goods block pedestrian passage","violation_category":"goods_blocking_road","open_risk_type":"","confidence":0.84,"segmentation_targets":["goods_or_materials","sidewalk","passage_obstruction"],"relation_hint":"goods block sidewalk"}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"mask_uri":"s3://mock-evidence/goods_blocking_road_mask.png","crop_image_uris":["s3://mock-evidence/goods_blocking_road_crop_1.png"],"overlay_image_uris":["s3://mock-evidence/goods_blocking_road_overlay.png"],"evidence_basis_summary":"goods block pedestrian passage"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"goods_blocking_road","final_confidence":0.89,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"goods obstruct the sidewalk"}',
        encoding="utf-8",
    )
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  timeout_ms: 3000",
                "  retry:",
                "    max_attempts: 3",
                "    backoff_ms: 1000",
                "  send_preliminary: true",
                "  send_refined: true",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture}",
                f"  segmentation_fixture: {sam_fixture}",
                f"  evidence_judge_fixture: {judge_fixture}",
            ]
        ),
        encoding="utf-8",
    )

    def failing_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {"status_code": 503, "backend_trace_id": "trace-fail", "error_message": "backend unavailable"}

    client = TestClient(
        create_app(
            config_path=config_path,
            callback_sender=failing_sender,
            event_store=InMemoryEventStore(),
        )
    )

    create_response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-004.jpg",
            "camera_id": "left",
            "location": "水坊街",
            "device_id": "dog-20",
            "task_id": "patrol-sh-004",
            "occur_time": "2026-03-09T10:30:00Z",
        },
    )

    assert create_response.status_code == 502
    created = create_response.json()
    query_response = client.get(f"/v1/events/{created['event_id']}")

    assert query_response.status_code == 200
    queried = query_response.json()
    assert queried["result"]["stage"] == "failed"
    assert queried["result"]["error_type"] == "RuntimeError"
