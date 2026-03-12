from pathlib import Path

from fastapi import FastAPI

from ares_agent.tools.run_service import build_service_app


def test_build_service_app_loads_configured_chain_mode(tmp_path: Path) -> None:
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
                "orchestrator:",
                "  chain_mode: vlm1_only",
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "  send_preliminary: true",
                "  send_refined: false",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture.name}",
                f"  segmentation_fixture: {sam_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
            ]
        ),
        encoding="utf-8",
    )

    app = build_service_app(config_path)

    assert isinstance(app, FastAPI)
    assert app.state.app_config.orchestrator.chain_mode == "vlm1_only"
