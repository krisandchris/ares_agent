from ares_agent.plugins.http_callback import HttpCallbackPlugin
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
        frame_id="frame-001",
        suspected_categories=["road_occupying_vendor"],
        risk_level="high",
        prelim_confidence=0.91,
        need_retake=False,
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
                "frame_id": "frame-001",
                "stage": "preliminary",
                "suspected_categories": ["road_occupying_vendor"],
                "risk_level": "high",
                "prelim_confidence": 0.91,
                "need_retake": False,
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
        frame_id="frame-001",
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
                "frame_id": "frame-001",
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
