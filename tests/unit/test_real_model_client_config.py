from pathlib import Path

from ares_agent.api.app import _build_model_clients_from_config
from ares_agent.infra.config import load_config
from ares_agent.model_clients.http_clients import Sam3FastApiClient, SglangVlmJudgeClient, SglangVlmPreliminaryClient


def test_load_config_reads_real_model_endpoints_and_params(tmp_path: Path) -> None:
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
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture.name}",
                f"  segmentation_fixture: {sam_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /v1/chat/completions",
                "    model_name: qwen2.5-vl",
                "    timeout_ms: 12000",
                "    temperature: 0.1",
                "    max_tokens: 1024",
                "  judge:",
                "    base_url: http://127.0.0.1:30001",
                "    endpoint: /v1/chat/completions",
                "    model_name: qwen2.5-vl",
                "    timeout_ms: 15000",
                "    temperature: 0.0",
                "    max_tokens: 1024",
                "  sam3:",
                "    base_url: http://127.0.0.1:8001",
                "    endpoint: /segment",
                "    timeout_ms: 10000",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.model_clients.preliminary is not None
    assert str(config.model_clients.preliminary.base_url) == "http://127.0.0.1:30000/"
    assert config.model_clients.preliminary.endpoint == "/v1/chat/completions"
    assert config.model_clients.preliminary.timeout_ms == 12000
    assert config.model_clients.preliminary.temperature == 0.1
    assert config.model_clients.preliminary.max_tokens == 1024
    assert config.model_clients.sam3 is not None
    assert str(config.model_clients.sam3.base_url) == "http://127.0.0.1:8001/"
    assert config.model_clients.sam3.endpoint == "/segment"
    assert config.model_clients.sam3.timeout_ms == 10000


def test_build_model_clients_from_config_uses_real_urls_and_params(tmp_path: Path) -> None:
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
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture.name}",
                f"  segmentation_fixture: {sam_fixture.name}",
                f"  evidence_judge_fixture: {judge_fixture.name}",
                "prompts:",
                "  preliminary:",
                "    system: |",
                "      PRELIM SYSTEM",
                "    user: |",
                "      PRELIM USER {frame_id}",
                "  judge:",
                "    system: |",
                "      JUDGE SYSTEM",
                "model_clients:",
                "  mode: http",
                "  preliminary:",
                "    base_url: http://127.0.0.1:30000",
                "    endpoint: /v1/chat/completions",
                "    model_name: qwen2.5-vl",
                "    timeout_ms: 12000",
                "    temperature: 0.1",
                "    max_tokens: 1024",
                "  judge:",
                "    base_url: http://127.0.0.1:30001",
                "    endpoint: /v1/chat/completions",
                "    model_name: qwen2.5-vl",
                "    timeout_ms: 15000",
                "    temperature: 0.0",
                "    max_tokens: 1024",
                "  sam3:",
                "    base_url: http://127.0.0.1:8001",
                "    endpoint: /segment",
                "    timeout_ms: 10000",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    preliminary_client, segmentation_client, judge_client = _build_model_clients_from_config(config)

    assert isinstance(preliminary_client, SglangVlmPreliminaryClient)
    assert isinstance(segmentation_client, Sam3FastApiClient)
    assert isinstance(judge_client, SglangVlmJudgeClient)
    assert preliminary_client.endpoint == "http://127.0.0.1:30000/v1/chat/completions"
    assert preliminary_client.timeout_ms == 12000
    assert preliminary_client.temperature == 0.1
    assert preliminary_client.max_tokens == 1024
    assert judge_client.endpoint == "http://127.0.0.1:30001/v1/chat/completions"
    assert judge_client.timeout_ms == 15000
    assert segmentation_client.endpoint == "http://127.0.0.1:8001/segment"
    assert segmentation_client.timeout_ms == 10000
