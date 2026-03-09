"""API request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class InspectionIngestRequest(BaseModel):
    """HTTP request contract for one inspection input."""

    image_uri: str
    frame_id: str
    device_id: str
    task_id: str
    occur_time: str


class EventQueryResponse(BaseModel):
    """Response for event lookup by event id."""

    event_id: str
    found: bool
    result: dict[str, Any] | None = None


class EventFailureResponse(BaseModel):
    """Structured failure payload returned by the HTTP ingress."""

    event_id: str
    frame_id: str
    stage: str
    failed_step: str | None = None
    error_type: str
    error_message: str
