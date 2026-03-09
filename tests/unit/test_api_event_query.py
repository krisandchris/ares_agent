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


def test_get_event_by_id_returns_latest_stored_result() -> None:
    event_store = InMemoryEventStore()
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
            sender=lambda url, headers, payload: {"status_code": 200},
        ),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )
    client = TestClient(create_app(workflow=workflow, event_store=event_store))

    create_response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "frame_id": "frame-001",
            "device_id": "dog-17",
            "task_id": "patrol-sh-001",
            "occur_time": "2026-03-09T10:00:00Z",
        },
    )
    event_id = create_response.json()["event_id"]

    response = client.get(f"/v1/events/{event_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == event_id
    assert body["found"] is True
    assert body["result"]["event_id"] == event_id


def test_get_event_by_id_returns_not_found_when_missing() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/events/evt_missing")

    assert response.status_code == 404
    assert response.json() == {
        "event_id": "evt_missing",
        "found": False,
        "result": None,
    }
