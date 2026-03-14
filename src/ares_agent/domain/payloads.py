"""Shared payload typing for stored/queryable event results."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class StoredEventPayload(TypedDict):
    event_id: str
    stage: str
    summary: NotRequired[dict[str, int]]
    sub_events: NotRequired[list[dict[str, Any]]]
    preliminary_feedback: NotRequired[dict[str, Any]]
    refined_feedback: NotRequired[dict[str, Any]]
    evidence_package: NotRequired[dict[str, Any]]
    judgment: NotRequired[dict[str, Any]]
    preliminary: NotRequired[dict[str, Any]]
    frame_seed: NotRequired[dict[str, Any]]
    failed_step: NotRequired[str | None]
    error_type: NotRequired[str]
    error_message: NotRequired[str]
