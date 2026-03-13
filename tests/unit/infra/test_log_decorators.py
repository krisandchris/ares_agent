from __future__ import annotations

import json

import pytest

from ares_agent.infra.log_context import clear_log_context
from ares_agent.infra.log_decorators import log_stage
from ares_agent.infra.logging import configure_logging


def _parse_json_lines(output: str) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        parsed.append(json.loads(line))
    return parsed


def test_log_stage_emits_started_and_succeeded_with_bound_event_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(force=True)
    clear_log_context()

    @log_stage(
        "preliminary",
        field_extractor=lambda seed: {
            "event_id": "evt_test_123",
            "camera_id": seed["camera_id"],
            "location": seed["location"],
        },
    )
    def run(seed: dict[str, str]) -> str:
        return "ok"

    assert run({"camera_id": "front", "location": "南山路"}) == "ok"

    logs = _parse_json_lines(capsys.readouterr().out)

    assert [entry["event"] for entry in logs] == [
        "workflow.stage.started",
        "workflow.stage.succeeded",
    ]
    assert all(entry["event_id"] == "evt_test_123" for entry in logs)
    assert logs[0]["stage"] == "preliminary"
    assert logs[1]["duration_ms"] >= 0


def test_log_stage_emits_failed_and_reraises(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(force=True)
    clear_log_context()

    @log_stage("segmentation", field_extractor=lambda *_args, **_kwargs: {"event_id": "evt_test_456"})
    def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        fail()

    logs = _parse_json_lines(capsys.readouterr().out)

    assert [entry["event"] for entry in logs] == [
        "workflow.stage.started",
        "workflow.stage.failed",
    ]
    assert logs[-1]["event_id"] == "evt_test_456"
    assert logs[-1]["error_type"] == "RuntimeError"
    assert logs[-1]["error_message"] == "boom"
