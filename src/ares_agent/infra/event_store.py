"""Minimal event result storage for the mocked MVP."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Protocol, cast

from ares_agent.domain.payloads import StoredEventPayload
from ares_agent.infra.logging import get_logger


class EventStore(Protocol):
    def save(self, event_id: str, payload: StoredEventPayload) -> None: ...

    def get(self, event_id: str) -> StoredEventPayload | None: ...


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
            backend="memory",
        )

    def get(self, event_id: str) -> StoredEventPayload | None:
        payload = self._events.get(event_id)
        get_logger(__name__).info(
            "event_store.loaded",
            event_id=event_id,
            found=payload is not None,
            stage=payload.get("stage") if payload is not None else None,
            backend="memory",
        )
        return deepcopy(payload) if payload is not None else None


class FileBackedEventStore:
    """Persist latest workflow result per event id to local disk."""

    def __init__(self, *, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._events: dict[str, StoredEventPayload] = {}

    def save(self, event_id: str, payload: StoredEventPayload) -> None:
        copied = deepcopy(payload)
        self._events[event_id] = copied
        path = self._path_for_event(event_id)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(json.dumps(copied, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)
        get_logger(__name__).info(
            "event_store.saved",
            event_id=event_id,
            stage=payload.get("stage"),
            backend="file",
            storage_path=str(path),
        )

    def get(self, event_id: str) -> StoredEventPayload | None:
        payload = self._events.get(event_id)
        if payload is None:
            path = self._path_for_event(event_id)
            if path.exists():
                payload = cast(StoredEventPayload, json.loads(path.read_text(encoding="utf-8")))
                self._events[event_id] = deepcopy(payload)
        get_logger(__name__).info(
            "event_store.loaded",
            event_id=event_id,
            found=payload is not None,
            stage=payload.get("stage") if payload is not None else None,
            backend="file",
        )
        return deepcopy(payload) if payload is not None else None

    def _path_for_event(self, event_id: str) -> Path:
        return self.base_dir / f"{event_id}.json"
