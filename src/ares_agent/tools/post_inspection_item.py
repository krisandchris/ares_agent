"""CLI helper to post one inspection item request to the running service."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from urllib import request


@dataclass(frozen=True)
class InspectionRequest:
    image_uri: str
    camera_id: str
    location: str
    device_id: str
    task_id: str
    occur_time: str


def build_request_payload(payload: InspectionRequest) -> bytes:
    return json.dumps(asdict(payload), ensure_ascii=False).encode("utf-8")


def parse_response_body(body: bytes) -> str:
    text = body.decode("utf-8")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def post_inspection_item(service_url: str, payload: InspectionRequest, timeout_seconds: float = 60.0) -> tuple[int, str]:
    endpoint = f"{service_url.rstrip('/')}/v1/inspection-items"
    req = request.Request(
        url=endpoint,
        data=build_request_payload(payload),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            return response.getcode(), parse_response_body(response.read())
    except request.HTTPError as exc:
        return exc.code, parse_response_body(exc.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="POST one inspection item to the running Ares service.")
    parser.add_argument("--service-url", default="http://127.0.0.1:8000", help="Base URL of the running service.")
    parser.add_argument("--image-uri", required=True, help="Image URI, including s3://bucket/object if MinIO resolving is enabled.")
    parser.add_argument("--camera-id", default="front", help="Camera id, e.g. front/left/right.")
    parser.add_argument("--location", default="南山路", help="Patrol location name.")
    parser.add_argument("--device-id", default="dog-17", help="Device id.")
    parser.add_argument("--task-id", default="patrol-s3-001", help="Task id.")
    parser.add_argument("--occur-time", default="2026-03-13T10:00:00Z", help="ISO8601 occur time.")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    status_code, response_body = post_inspection_item(
        service_url=args.service_url,
        payload=InspectionRequest(
            image_uri=args.image_uri,
            camera_id=args.camera_id,
            location=args.location,
            device_id=args.device_id,
            task_id=args.task_id,
            occur_time=args.occur_time,
        ),
        timeout_seconds=args.timeout,
    )
    print(f"HTTP {status_code}")
    print(response_body)
    if status_code >= 400:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
