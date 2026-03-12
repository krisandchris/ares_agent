"""Event models and identifiers."""

from __future__ import annotations

from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field


class EventSeed(BaseModel):
    """The immutable fields used to derive a stable event identifier."""

    model_config = ConfigDict(frozen=True)

    image_uri: str
    camera_id: str
    location: str
    device_id: str
    task_id: str
    occur_time: str


class ViolationEvent(BaseModel):
    """Stable event envelope shared by preliminary and refined stages."""

    event_id: str
    camera_id: str
    location: str
    stage: str
    event_version: int = Field(default=1, ge=1)


def generate_event_id(seed: EventSeed) -> str:
    """Generate a stable event id so sync and async chains share one key."""
    raw = f"{seed.image_uri}|{seed.camera_id}|{seed.location}|{seed.device_id}|{seed.task_id}|{seed.occur_time}"
    digest = sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"evt_{digest}"
