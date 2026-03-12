from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.infra.event_store import InMemoryEventStore
from ares_agent.plugins.http_callback import HttpCallbackPlugin
from ares_agent.workflows.inspection_event_workflow import build_inspection_event_workflow
from ares_agent.model_clients.mock_clients import (
    MockEvidenceJudgeClient,
    MockPreliminaryClient,
    MockSegmentationClient,
)


def test_post_ingestion_runs_mock_workflow_and_returns_shared_event_payload() -> None:
    callback_payloads: list[dict[str, object]] = []
    event_store = InMemoryEventStore()

    def fake_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        callback_payloads.append(payload)
        return {"status_code": 200, "backend_trace_id": "trace-api"}

    workflow = build_inspection_event_workflow(
        preliminary_client=MockPreliminaryClient(
            fixture_path=Path("fixtures/mock_vlm_preliminary/road_occupying_vendor.json")
        ),
        segmentation_client=MockSegmentationClient(
            fixture_path=Path("fixtures/mock_sam3/road_occupying_vendor.json")
        ),
        evidence_judge_client=MockEvidenceJudgeClient(
            fixture_path=Path("fixtures/mock_vlm_judge/road_occupying_vendor.json")
        ),
        sink_plugin=HttpCallbackPlugin(
            endpoint="https://backend.example/api/v1/events/callback",
            auth_token="secret-token",
            sender=fake_sender,
        ),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )
    app = create_app(workflow=workflow, event_store=event_store)
    client = TestClient(app)

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
    body = response.json()
    assert body["event_id"].startswith("evt_")
    assert body["stage"] == "refined"
    assert body["preliminary_feedback"]["event_id"] == body["refined_feedback"]["event_id"]
    assert body["refined_feedback"]["final_category"] == "road_occupying_vendor"
    assert body["evidence_package"]["archive_readiness"] is True
    assert len(callback_payloads) == 2
    assert callback_payloads[0]["stage"] == "preliminary"
    assert callback_payloads[1]["stage"] == "refined"
    assert event_store.get(body["event_id"]) == body


def test_post_ingestion_rejects_invalid_request_body() -> None:
    client = TestClient(create_app(workflow=None))

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "camera_id": "front",
            "device_id": "dog-17",
        },
    )

    assert response.status_code == 422
