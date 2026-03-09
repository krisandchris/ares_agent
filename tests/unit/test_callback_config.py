from pathlib import Path

from ares_agent.infra.config import load_config


def test_load_config_reads_callback_timeout_retry_and_auth_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARES_CALLBACK_TOKEN", "env-secret")
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text("{}", encoding="utf-8")
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text("{}", encoding="utf-8")
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  auth_token_env: ARES_CALLBACK_TOKEN",
                "  timeout_ms: 3500",
                "  retry:",
                "    max_attempts: 4",
                "    backoff_ms: 1200",
                "  send_preliminary: true",
                "  send_refined: true",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture.name}",
                f"  segmentation_fixture: {sam_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.callback.auth_token_env == "ARES_CALLBACK_TOKEN"
    assert config.callback.auth_token == "env-secret"
    assert config.callback.timeout_ms == 3500
    assert config.callback.retry.max_attempts == 4
    assert config.callback.retry.backoff_ms == 1200
