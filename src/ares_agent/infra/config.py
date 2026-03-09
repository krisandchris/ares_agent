"""Application configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, HttpUrl


class AgentSettings(BaseModel):
    service_name: str = "street-inspection-agent"


class OrchestratorSettings(BaseModel):
    enable_async_refine: bool = True


class RetrySettings(BaseModel):
    max_attempts: int = 3
    backoff_ms: int = 1000


class CallbackSettings(BaseModel):
    plugin: str
    endpoint: HttpUrl
    auth_token: str | None = None
    auth_token_env: str | None = None
    timeout_ms: int = 3000
    send_preliminary: bool = True
    send_refined: bool = True
    retry: RetrySettings = RetrySettings()


class ReviewSettings(BaseModel):
    enable_manual_review: bool = True


class MockClientSettings(BaseModel):
    preliminary_fixture: Path
    segmentation_fixture: Path
    evidence_judge_fixture: Path


class PromptTemplatePair(BaseModel):
    system: str
    user: str


class JudgePromptSettings(BaseModel):
    system: str


class PromptSettings(BaseModel):
    preliminary: PromptTemplatePair
    judge: JudgePromptSettings


class ModelEndpointSettings(BaseModel):
    endpoint: str
    model_name: str | None = None


class ModelClientSettings(BaseModel):
    mode: Literal["mock", "http"] = "mock"
    preliminary: ModelEndpointSettings | None = None
    judge: ModelEndpointSettings | None = None
    sam3: ModelEndpointSettings | None = None


class AppConfig(BaseModel):
    agent: AgentSettings = AgentSettings()
    orchestrator: OrchestratorSettings = OrchestratorSettings()
    callback: CallbackSettings
    mock_clients: MockClientSettings
    prompts: PromptSettings | None = None
    model_clients: ModelClientSettings = ModelClientSettings()
    review: ReviewSettings = ReviewSettings()


def load_config(path: str | Path) -> AppConfig:
    """Load YAML configuration into a validated application config."""
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(data)
    base_dir = config_path.parent
    config.callback = _resolve_callback_settings(config.callback)
    config.mock_clients = MockClientSettings(
        preliminary_fixture=_resolve_path(base_dir, config.mock_clients.preliminary_fixture),
        segmentation_fixture=_resolve_path(base_dir, config.mock_clients.segmentation_fixture),
        evidence_judge_fixture=_resolve_path(base_dir, config.mock_clients.evidence_judge_fixture),
    )
    return config


def _resolve_path(base_dir: Path, candidate: Path) -> Path:
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def _resolve_callback_settings(settings: CallbackSettings) -> CallbackSettings:
    token = settings.auth_token
    if token is None and settings.auth_token_env:
        token = os.getenv(settings.auth_token_env)
    retry = settings.retry
    return CallbackSettings(
        plugin=settings.plugin,
        endpoint=settings.endpoint,
        auth_token=token,
        auth_token_env=settings.auth_token_env,
        timeout_ms=settings.timeout_ms,
        send_preliminary=settings.send_preliminary,
        send_refined=settings.send_refined,
        retry=retry,
    )
