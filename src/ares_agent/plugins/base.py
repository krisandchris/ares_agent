"""Base callback plugin contract."""

from __future__ import annotations

from typing import Protocol


class SinkPlugin(Protocol):
    """Interface for management-service callback adapters."""

    def send(self, event_payload: object, runtime_config: object) -> object:
        """Send an event payload to the backend management service."""

