from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.infra.event_store import InMemoryEventStore


def test_create_app_runs_full_workflow_in_http_mode_with_configured_clients(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"environment_analysis":"street storefront scene","scene_elements":["storefront","goods","sidewalk"],"evidence_reasoning":"goods extend onto sidewalk","violation_category":"goods_blocking_road","open_risk_type":"","confidence":0.84,"segmentation_targets":["goods","storefront_entrance","sidewalk"],"relation_hint":"goods placed outside storefront and block sidewalk"}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"overlay_image":"s3://mock/goods_overlay.png","mask_labels":["goods","storefront_entrance","sidewalk"],"relation_hint":"goods placed outside storefront and block sidewalk","segmentation_status":"ok","mask_uri":"s3://mock/goods_mask.png","crop_image_uris":["s3://mock/goods_crop.png"],"overlay_image_uris":["s3://mock/goods_overlay.png"],"evidence_basis_summary":"goods block sidewalk"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"goods_blocking_road","final_confidence":0.89,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"goods block sidewalk"}',
        encoding="utf-8",
    )
    stub_config_path = tmp_path / "stub_agent_config.yaml"
    stub_config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture}",
                f"  segmentation_fixture: {sam_fixture}",
                f"  evidence_judge_fixture: {judge_fixture}",
                "model_clients:",
                "  mode: mock",
            ]
        ),
        encoding="utf-8",
    )
    stub_app = create_app(config_path=stub_config_path)
    stub_client = TestClient(stub_app)

    def local_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        response = stub_client.post(url, json=payload, headers=headers)
        return response.json()

    callback_payloads: list[dict[str, object]] = []

    http_config_path = tmp_path / "http_agent_config.yaml"
    http_config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: true",
                "  send_refined: true",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture}",
                f"  segmentation_fixture: {sam_fixture}",
                f"  evidence_judge_fixture: {judge_fixture}",
                "prompts:",
                "  preliminary:",
                "    system: |",
                "      PRELIM SYSTEM",
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
                "    timeout_ms: 12000",
                "    temperature: 0.1",
                "    max_tokens: 1024",
                "  judge:",
                "    base_url: http://127.0.0.1:30001",
                "    endpoint: /mock/vlm/judge",
                "    model_name: inspection-vlm",
                "    timeout_ms: 15000",
                "    temperature: 0.0",
                "    max_tokens: 1024",
                "  sam3:",
                "    base_url: http://127.0.0.1:8001",
                "    endpoint: /mock/sam3/segment",
                "    timeout_ms: 10000",
            ]
        ),
        encoding="utf-8",
    )

    client = TestClient(
        create_app(
            config_path=http_config_path,
            callback_sender=lambda url, headers, payload: callback_payloads.append(payload) or {"status_code": 200},
            event_store=InMemoryEventStore(),
            model_requesters={
                "preliminary": local_requester,
                "judge": local_requester,
                "sam3": local_requester,
            },
        )
    )

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-100.jpg",
            "frame_id": "frame-100",
            "device_id": "dog-99",
            "task_id": "patrol-sh-100",
            "occur_time": "2026-03-09T12:00:00Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["refined_feedback"]["final_category"] == "goods_blocking_road"
    assert [payload["stage"] for payload in callback_payloads] == ["preliminary", "refined"]
