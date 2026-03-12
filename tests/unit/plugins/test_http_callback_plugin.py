import pytest

import ares_agent.plugins.http_callback as http_callback
from ares_agent.plugins.http_callback import HttpCallbackPlugin, _default_sender
from ares_agent.services.feedback import build_preliminary_feedback, build_refined_feedback


def test_http_callback_plugin_sends_serialized_preliminary_payload() -> None:
    sent: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def fake_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        sent.append((url, headers, payload))
        return {"status_code": 200, "backend_trace_id": "trace-prelim"}

    plugin = HttpCallbackPlugin(
        endpoint="https://backend.example/api/v1/events/callback",
        auth_token="secret-token",
        sender=fake_sender,
    )
    feedback = build_preliminary_feedback(
        event_id="evt_123",
        camera_id="front",
        location="南山路",
        violation_category="road_occupying_vendor",
        open_risk_type="",
        confidence=0.91,
        async_enqueued=True,
    )

    result = plugin.send(feedback, runtime_config={"callback": {"send_preliminary": True}})

    assert sent == [
        (
            "https://backend.example/api/v1/events/callback",
            {
                "Authorization": "Bearer secret-token",
                "Content-Type": "application/json",
            },
            {
                "event_id": "evt_123",
                "camera_id": "front",
                "location": "南山路",
                "stage": "preliminary",
                "violation_category": "road_occupying_vendor",
                "open_risk_type": "",
                "confidence": 0.91,
                "async_enqueued": True,
            },
        )
    ]
    assert result.success is True
    assert result.status_code == 200
    assert result.backend_trace_id == "trace-prelim"


def test_http_callback_plugin_sends_serialized_refined_payload() -> None:
    sent: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def fake_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        sent.append((url, headers, payload))
        return {"status_code": 202, "backend_trace_id": "trace-refined"}

    plugin = HttpCallbackPlugin(
        endpoint="https://backend.example/api/v1/events/callback",
        sender=fake_sender,
    )
    feedback = build_refined_feedback(
        event_id="evt_123",
        camera_id="front",
        location="南山路",
        final_category="road_occupying_vendor",
        final_confidence=0.96,
        archive_readiness=True,
        review_required=False,
        event_version=2,
    )

    result = plugin.send(feedback, runtime_config={"callback": {"send_refined": True}})

    assert sent == [
        (
            "https://backend.example/api/v1/events/callback",
            {"Content-Type": "application/json"},
            {
                "event_id": "evt_123",
                "camera_id": "front",
                "location": "南山路",
                "stage": "refined",
                "final_category": "road_occupying_vendor",
                "final_confidence": 0.96,
                "archive_readiness": True,
                "review_required": False,
                "event_version": 2,
            },
        )
    ]
    assert result.success is True
    assert result.status_code == 202
    assert result.backend_trace_id == "trace-refined"


def test_http_callback_plugin_retries_retryable_failures_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    def flaky_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        attempts.append(1)
        if len(attempts) < 3:
            return {"status_code": 503, "error_message": "backend unavailable"}
        return {"status_code": 200, "backend_trace_id": "trace-recovered"}

    monkeypatch.setattr(http_callback.time, "sleep", lambda seconds: sleeps.append(seconds))

    plugin = HttpCallbackPlugin(
        endpoint="https://backend.example/api/v1/events/callback",
        sender=flaky_sender,
        max_attempts=3,
        backoff_ms=250,
    )
    feedback = build_preliminary_feedback(
        event_id="evt_123",
        camera_id="front",
        location="南山路",
        violation_category="road_occupying_vendor",
        open_risk_type="",
        confidence=0.91,
        async_enqueued=True,
    )

    result = plugin.send(feedback, runtime_config={"callback": {"send_preliminary": True}})

    assert len(attempts) == 3
    assert sleeps == [0.25, 0.25]
    assert result.success is True
    assert result.status_code == 200
    assert result.backend_trace_id == "trace-recovered"


def test_http_callback_plugin_returns_failed_result_after_retry_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    def failing_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        attempts.append(1)
        return {"status_code": 503, "error_message": "backend unavailable"}

    monkeypatch.setattr(http_callback.time, "sleep", lambda seconds: sleeps.append(seconds))

    plugin = HttpCallbackPlugin(
        endpoint="https://backend.example/api/v1/events/callback",
        sender=failing_sender,
        max_attempts=3,
        backoff_ms=100,
    )
    feedback = build_refined_feedback(
        event_id="evt_123",
        camera_id="front",
        location="南山路",
        final_category="road_occupying_vendor",
        final_confidence=0.96,
        archive_readiness=True,
        review_required=False,
        event_version=2,
    )

    result = plugin.send(feedback, runtime_config={"callback": {"send_refined": True}})

    assert len(attempts) == 3
    assert sleeps == [0.1, 0.1]
    assert result.success is False
    assert result.status_code == 503
    assert result.retryable is True
    assert result.error_message == "backend unavailable"


def test_default_sender_passes_timeout_to_urlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    class FakeResponse:
        headers = {"X-Trace-Id": "trace-id"}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def getcode(self) -> int:
            return 200

        def read(self) -> bytes:
            return b""

    def fake_urlopen(req, timeout):
        observed["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("ares_agent.plugins.http_callback.request.urlopen", fake_urlopen)

    result = _default_sender(
        "https://backend.example/api/v1/events/callback",
        {"Content-Type": "application/json"},
        {"event_id": "evt_123"},
        timeout_ms=2500,
    )

    assert observed["timeout"] == 2.5
    assert result["status_code"] == 200
    assert result["backend_trace_id"] == "trace-id"
