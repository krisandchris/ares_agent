from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app


def test_create_app_bootstraps_workflow_from_config_and_fixture_paths(tmp_path: Path) -> None:
    callback_payloads: list[dict[str, object]] = []

    def fake_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        callback_payloads.append(payload)
        return {"status_code": 200, "backend_trace_id": "trace-config"}

    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        json.dumps(
            {
                "suspected_categories": ["goods_blocking_road"],
                "risk_level": "medium",
                "prelim_confidence": 0.83,
                "need_retake": False,
                "open_risk_hints": [],
                "evidence_targets": ["goods_or_materials", "sidewalk", "passage_obstruction"],
            }
        ),
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        json.dumps(
            {
                "mask_uri": "s3://mock-evidence/goods_blocking_road_mask.png",
                "crop_image_uris": ["s3://mock-evidence/goods_blocking_road_crop_1.png"],
                "overlay_image_uris": ["s3://mock-evidence/goods_blocking_road_overlay.png"],
                "evidence_basis_summary": "goods are stacked on the sidewalk and block pedestrian passage",
            }
        ),
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        json.dumps(
            {
                "final_category": "goods_blocking_road",
                "final_confidence": 0.88,
                "evidence_basis_match": True,
                "violation_relation_confirmed": True,
                "exception_excluded": True,
                "archive_readiness": True,
                "review_required": False,
                "rejection_reason": None,
                "violation_relation_summary": "goods remain on the sidewalk and obstruct passage",
            }
        ),
        encoding="utf-8",
    )
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
                f"  preliminary_fixture: {prelim_fixture}",
                f"  segmentation_fixture: {sam_fixture}",
                f"  evidence_judge_fixture: {judge_fixture}",
                "review:",
                "  enable_manual_review: true",
            ]
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app(config_path=config_path, callback_sender=fake_sender))
    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-002.jpg",
            "frame_id": "frame-002",
            "device_id": "dog-18",
            "task_id": "patrol-sh-002",
            "occur_time": "2026-03-09T10:10:00Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["refined_feedback"]["final_category"] == "goods_blocking_road"
    assert body["judgment"]["final_confidence"] == 0.88
    assert [payload["stage"] for payload in callback_payloads] == ["preliminary", "refined"]


def test_create_app_requires_explicit_workflow_or_config_for_custom_bootstrap() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
