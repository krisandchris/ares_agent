"""Minimal event result storage for the mocked MVP."""

from __future__ import annotations

from copy import deepcopy


class InMemoryEventStore:
    """Store the latest workflow result by event id."""

    def __init__(self) -> None:
        self._events: dict[str, dict[str, object]] = {}

    def save(self, event_id: str, payload: dict[str, object]) -> None:
        self._events[event_id] = deepcopy(payload)

    def get(self, event_id: str) -> dict[str, object] | None:
        payload = self._events.get(event_id)
        return deepcopy(payload) if payload is not None else None
