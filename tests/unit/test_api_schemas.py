from ares_agent.api.schemas import EventFailureResponse, EventQueryResponse, InspectionIngestRequest


def test_inspection_ingest_request_requires_image_uri_and_metadata() -> None:
    request = InspectionIngestRequest(
        image_uri="s3://street/frame-001.jpg",
        frame_id="frame-001",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )

    assert request.image_uri == "s3://street/frame-001.jpg"
    assert request.frame_id == "frame-001"


def test_event_query_response_wraps_latest_event_payload() -> None:
    response = EventQueryResponse(
        event_id="evt_123",
        found=True,
        result={"event_id": "evt_123", "stage": "refined"},
    )

    assert response.event_id == "evt_123"
    assert response.found is True
    assert response.result == {"event_id": "evt_123", "stage": "refined"}


def test_event_failure_response_tracks_failed_stage_and_reason() -> None:
    response = EventFailureResponse(
        event_id="evt_123",
        frame_id="frame-001",
        stage="failed",
        failed_step="preliminary",
        error_type="RuntimeError",
        error_message="preliminary callback failed with status 503",
    )

    assert response.failed_step == "preliminary"
    assert response.error_type == "RuntimeError"
