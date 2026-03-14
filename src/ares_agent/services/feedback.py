"""Feedback payload builders shared by sync and async chains."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PreliminaryEventFeedback(BaseModel):
    event_id: str
    sub_event_id: str | None = None
    camera_id: str
    location: str
    stage: Literal["preliminary"] = "preliminary"
    violation_category: str
    open_risk_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    async_enqueued: bool


class RefinedEventFeedback(BaseModel):
    event_id: str
    sub_event_id: str | None = None
    camera_id: str
    location: str
    stage: Literal["refined"] = "refined"
    final_category: str
    final_confidence: float = Field(ge=0.0, le=1.0)
    archive_readiness: bool
    review_required: bool
    event_version: int = Field(default=2, ge=1)


def build_preliminary_feedback(
    *,
    event_id: str,
    sub_event_id: str | None = None,
    camera_id: str,
    location: str,
    violation_category: str,
    open_risk_type: str,
    confidence: float,
    async_enqueued: bool,
) -> PreliminaryEventFeedback:
    """Create the fast-path payload shared with the management service."""
    return PreliminaryEventFeedback(
        event_id=event_id,
        sub_event_id=sub_event_id,
        camera_id=camera_id,
        location=location,
        violation_category=violation_category,
        open_risk_type=open_risk_type,
        confidence=confidence,
        async_enqueued=async_enqueued,
    )


def build_refined_feedback(
    *,
    event_id: str,
    sub_event_id: str | None = None,
    camera_id: str,
    location: str,
    final_category: str,
    final_confidence: float,
    archive_readiness: bool,
    review_required: bool,
    event_version: int = 2,
) -> RefinedEventFeedback:
    """Create the refined payload that updates the same logical event."""
    return RefinedEventFeedback(
        event_id=event_id,
        sub_event_id=sub_event_id,
        camera_id=camera_id,
        location=location,
        final_category=final_category,
        final_confidence=final_confidence,
        archive_readiness=archive_readiness,
        review_required=review_required,
        event_version=event_version,
    )
