import json

from ares_agent.tools.post_inspection_item import (
    InspectionRequest,
    build_request_payload,
    parse_response_body,
)


def test_build_request_payload_serializes_inspection_request() -> None:
    payload = build_request_payload(
        InspectionRequest(
            image_uri="s3://test-bucket/folder/image.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-17",
            task_id="patrol-s3-001",
            occur_time="2026-03-13T10:00:00Z",
        )
    )

    assert json.loads(payload.decode("utf-8")) == {
        "image_uri": "s3://test-bucket/folder/image.jpg",
        "camera_id": "front",
        "location": "南山路",
        "device_id": "dog-17",
        "task_id": "patrol-s3-001",
        "occur_time": "2026-03-13T10:00:00Z",
    }


def test_parse_response_body_pretty_formats_json() -> None:
    body = b'{"event_id":"evt_123","stage":"preliminary"}'

    parsed = parse_response_body(body)

    assert parsed == '{\n  "event_id": "evt_123",\n  "stage": "preliminary"\n}'


def test_parse_response_body_falls_back_to_text_for_non_json() -> None:
    body = b"internal error"

    parsed = parse_response_body(body)

    assert parsed == "internal error"
