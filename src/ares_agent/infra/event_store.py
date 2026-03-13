"""Minimal event result storage for the mocked MVP."""

from __future__ import annotations

from copy import deepcopy

from ares_agent.domain.payloads import StoredEventPayload
from ares_agent.infra.logging import get_logger


class InMemoryEventStore:
    """Store the latest workflow result by event id."""

    def __init__(self) -> None:
        self._events: dict[str, StoredEventPayload] = {}

    def save(self, event_id: str, payload: StoredEventPayload) -> None:
        self._events[event_id] = deepcopy(payload)
        get_logger(__name__).info(
            "event_store.saved",
            event_id=event_id,
            stage=payload.get("stage"),
        )

    def get(self, event_id: str) -> StoredEventPayload | None:
        payload = self._events.get(event_id)
        get_logger(__name__).info(
            "event_store.loaded",
            event_id=event_id,
            found=payload is not None,
            stage=payload.get("stage") if payload is not None else None,
        )
        return deepcopy(payload) if payload is not None else None
