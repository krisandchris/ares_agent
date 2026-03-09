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


def test_post_ingestion_returns_failed_payload_when_callback_fails() -> None:
    event_store = InMemoryEventStore()

    def failing_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        return {
            "status_code": 503,
            "backend_trace_id": "trace-down",
            "error_message": "backend unavailable",
        }

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
            sender=failing_sender,
        ),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )
    client = TestClient(create_app(workflow=workflow, event_store=event_store))

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "frame_id": "frame-001",
            "device_id": "dog-17",
            "task_id": "patrol-sh-001",
            "occur_time": "2026-03-09T10:00:00Z",
        },
    )

    assert response.status_code == 502
    body = response.json()
    assert body["stage"] == "failed"
    assert body["error_type"] == "RuntimeError"
    assert "preliminary callback failed" in body["error_message"]
    assert event_store.get(body["event_id"]) == body


def test_post_ingestion_returns_failed_payload_when_fixture_is_missing() -> None:
    event_store = InMemoryEventStore()
    workflow = build_inspection_event_workflow(
        preliminary_client=MockPreliminaryClient(
            fixture_path=Path("fixtures/mock_vlm_preliminary/missing.json")
        ),
        segmentation_client=MockSegmentationClient(
            fixture_path=Path("fixtures/mock_sam3/road_occupying_vendor.json")
        ),
        evidence_judge_client=MockEvidenceJudgeClient(
            fixture_path=Path("fixtures/mock_vlm_judge/road_occupying_vendor.json")
        ),
        sink_plugin=HttpCallbackPlugin(
            endpoint="https://backend.example/api/v1/events/callback",
            sender=lambda url, headers, payload: {"status_code": 200},
        ),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )
    client = TestClient(create_app(workflow=workflow, event_store=event_store))

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "frame_id": "frame-001",
            "device_id": "dog-17",
            "task_id": "patrol-sh-001",
            "occur_time": "2026-03-09T10:00:00Z",
        },
    )

    assert response.status_code == 500
    body = response.json()
    assert body["stage"] == "failed"
    assert body["error_type"] == "FileNotFoundError"
    assert event_store.get(body["event_id"]) == body
