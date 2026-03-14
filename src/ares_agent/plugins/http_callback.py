"""HTTP callback sink plugin."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable, NotRequired, TypedDict, cast
from urllib import request
from urllib.parse import urlparse

from pydantic import BaseModel

from ares_agent.domain.json_types import JsonObject
from ares_agent.infra.logging import get_logger


Sender = Callable[[str, dict[str, str], JsonObject], JsonObject]


class CallbackResponsePayload(TypedDict):
    status_code: int | str
    backend_trace_id: NotRequired[object]
    error_message: NotRequired[object]


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
    payload: JsonObject,
    *,
    timeout_ms: int,
) -> JsonObject:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout_ms / 1000) as response:  # noqa: S310
        trace_id = response.headers.get("X-Trace-Id")
        return {
            "status_code": response.getcode(),
            "backend_trace_id": trace_id,
        }


def _parse_callback_response(response: JsonObject) -> CallbackResult:
    typed_response = cast(CallbackResponsePayload, response)
    status_code = int(typed_response["status_code"])
    backend_trace_id_raw = typed_response.get("backend_trace_id")
    error_message_raw = typed_response.get("error_message")
    backend_trace_id = str(backend_trace_id_raw) if backend_trace_id_raw is not None else None
    error_message = str(error_message_raw) if error_message_raw is not None else None
    return CallbackResult(
        success=200 <= status_code < 300,
        status_code=status_code,
        backend_trace_id=backend_trace_id,
        retryable=status_code >= 500,
        error_message=error_message,
    )


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
        event_id = payload.get("event_id")
        stage = payload.get("stage")
        endpoint_host = urlparse(self.endpoint).netloc
        get_logger(__name__).info(
            "callback.started",
            event_id=event_id,
            stage=stage,
            endpoint_host=endpoint_host,
        )
        for attempt in range(1, self.max_attempts + 1):
            response = self.sender(self.endpoint, headers, payload)
            last_result = _parse_callback_response(response)
            get_logger(__name__).info(
                "callback.attempt",
                event_id=event_id,
                stage=stage,
                endpoint_host=endpoint_host,
                retry_attempt=attempt,
                callback_status_code=last_result.status_code,
                retryable=last_result.retryable,
                backend_trace_id=last_result.backend_trace_id,
            )
            if last_result.success or not last_result.retryable or attempt == self.max_attempts:
                get_logger(__name__).info(
                    "callback.succeeded" if last_result.success else "callback.failed",
                    event_id=event_id,
                    stage=stage,
                    endpoint_host=endpoint_host,
                    callback_status_code=last_result.status_code,
                    retry_attempt=attempt,
                    retryable=last_result.retryable,
                    backend_trace_id=last_result.backend_trace_id,
                    error_message=last_result.error_message,
                )
                return last_result
            time.sleep(self.backoff_ms / 1000)
        assert last_result is not None
        return last_result

    @staticmethod
    def _serialize_payload(event_payload: object) -> JsonObject:
        if isinstance(event_payload, BaseModel):
            return cast(JsonObject, dict(event_payload.model_dump(mode="json", exclude_none=True)))
        if isinstance(event_payload, dict):
            return cast(JsonObject, dict(event_payload))
        raise TypeError(f"Unsupported payload type: {type(event_payload)!r}")
