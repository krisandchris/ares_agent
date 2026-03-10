"""HTTP callback sink plugin."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib import request

from pydantic import BaseModel


Sender = Callable[[str, dict[str, str], dict[str, object]], dict[str, object]]


@dataclass(frozen=True)
class CallbackResult:
    success: bool
    status_code: int
    backend_trace_id: str | None = None
    retryable: bool = False
    error_message: str | None = None


def _default_sender(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    *,
    timeout_ms: int,
) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout_ms / 1000) as response:  # noqa: S310
        trace_id = response.headers.get("X-Trace-Id")
        return {
            "status_code": response.getcode(),
            "backend_trace_id": trace_id,
        }


class HttpCallbackPlugin:
    """Serialize feedback payloads and deliver them to the backend management service."""

    def __init__(
        self,
        *,
        endpoint: str,
        auth_token: str | None = None,
        timeout_ms: int = 3000,
        max_attempts: int = 3,
        backoff_ms: int = 1000,
        sender: Sender | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.timeout_ms = timeout_ms
        self.max_attempts = max_attempts
        self.backoff_ms = backoff_ms
        self.sender = sender or (
            lambda url, headers, payload: _default_sender(
                url,
                headers,
                payload,
                timeout_ms=self.timeout_ms,
            )
        )

    def send(self, event_payload: object, runtime_config: object) -> CallbackResult:
        del runtime_config
        payload = self._serialize_payload(event_payload)
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        last_result: CallbackResult | None = None
        for attempt in range(1, self.max_attempts + 1):
            response = self.sender(self.endpoint, headers, payload)
            status_code = int(response["status_code"])
            last_result = CallbackResult(
                success=200 <= status_code < 300,
                status_code=status_code,
                backend_trace_id=response.get("backend_trace_id"),
                retryable=status_code >= 500,
                error_message=response.get("error_message"),
            )
            if last_result.success or not last_result.retryable or attempt == self.max_attempts:
                return last_result
            time.sleep(self.backoff_ms / 1000)
        assert last_result is not None
        return last_result

    @staticmethod
    def _serialize_payload(event_payload: object) -> dict[str, object]:
        if isinstance(event_payload, BaseModel):
            return dict(event_payload.model_dump(mode="json"))
        if isinstance(event_payload, dict):
            return dict(event_payload)
        raise TypeError(f"Unsupported payload type: {type(event_payload)!r}")
