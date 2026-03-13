"""Helpers for request-scoped logging context."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import structlog.contextvars

from ares_agent.domain.events import EventSeed, generate_event_id

_CONTEXT_KEYS = {
    "camera_id",
    "chain_mode",
    "event_id",
    "location",
    "request_id",
}


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()


def bind_log_context(**values: object) -> None:
    filtered = {key: value for key, value in values.items() if value is not None}
    if filtered:
        structlog.contextvars.bind_contextvars(**filtered)


def bind_context_from_fields(fields: Mapping[str, Any] | None) -> None:
    if not fields:
        return
    bind_log_context(**{key: value for key, value in fields.items() if key in _CONTEXT_KEYS})


def bind_event_context(
    *,
    seed: EventSeed | None = None,
    event_id: str | None = None,
    camera_id: str | None = None,
    location: str | None = None,
) -> str | None:
    resolved_event_id = event_id
    resolved_camera_id = camera_id
    resolved_location = location
    if seed is not None:
        resolved_event_id = resolved_event_id or generate_event_id(seed)
        resolved_camera_id = resolved_camera_id or seed.camera_id
        resolved_location = resolved_location or seed.location
    bind_log_context(
        event_id=resolved_event_id,
        camera_id=resolved_camera_id,
        location=resolved_location,
    )
    return resolved_event_id
