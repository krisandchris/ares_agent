"""Application configuration loading."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class AgentSettings(BaseModel):
    service_name: str = "street-inspection-agent"


class LoggingSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = True
    level: str = "INFO"
    json_output: bool = Field(default=True, alias="json")
    include_request_id: bool = True
    include_event_id: bool = True
    log_model_payload_summary: bool = True
    log_callback_payload_summary: bool = True
    service_name: str = "street-inspection-agent"


class ConfigFileSettings(BaseModel):
    prompt_config: Path | None = None


class EventStoreSettings(BaseModel):
    backend: Literal["memory", "file"] = "memory"
    base_dir: Path | None = None


class OrchestratorSettings(BaseModel):
    enable_async_refine: bool = True
    chain_mode: Literal["full", "vlm1_only"] = "full"


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

    @model_validator(mode="after")
    def validate_stage_flags(self) -> "CallbackSettings":
        if self.send_refined and not self.send_preliminary:
            raise ValueError("send_refined requires send_preliminary")
        return self


class ReviewSettings(BaseModel):
    enable_manual_review: bool = True


class MinioSettings(BaseModel):
    enabled: bool = False
    endpoint: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    secure: bool = False
    region: str | None = None
    presign_expiry_seconds: int = 3600


class MockClientSettings(BaseModel):
    preliminary_fixture: Path
    segmentation_fixture: Path
    evidence_judge_fixture: Path


class SceneActivationRule(BaseModel):
    enabled_categories: list[str] = Field(default_factory=list)
    disabled_categories: list[str] = Field(default_factory=list)
    priority_categories: list[str] = Field(default_factory=list)
    location_constraints: list[str] = Field(default_factory=list)
    scene_hint: str = ""


class SceneActivationPolicyConfig(BaseModel):
    camera_defaults: dict[str, SceneActivationRule] = Field(default_factory=dict)
    location_defaults: dict[str, SceneActivationRule] = Field(default_factory=dict)
    overrides: dict[str, dict[str, SceneActivationRule]] = Field(default_factory=dict)


class CategoryRegistryRule(BaseModel):
    definition: str
    common_objects: list[str] = Field(default_factory=list)
    relation_focus: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)


class OpenRiskRegistry(BaseModel):
    guidance: str = (
        "If visible evidence strongly suggests a risk outside the prioritized standard categories, "
        'output violation_category="open_risk" with a concise open_risk_type.'
    )
    examples: list[str] = Field(default_factory=list)


class PreliminaryPromptSettings(BaseModel):
    role_block: str
    scene_activation_block_template: str
    category_focus_block_template: str
    reasoning_block: str
    output_contract_block: str
    user: str


class JudgePromptSettings(BaseModel):
    system: str
    user: str


class PromptSettings(BaseModel):
    preliminary: PreliminaryPromptSettings
    judge: JudgePromptSettings


class ModelEndpointSettings(BaseModel):
    base_url: HttpUrl
    endpoint: str
    model_name: str | None = None
    timeout_ms: int = 10000
    temperature: float | None = None
    max_tokens: int | None = None


class ModelClientSettings(BaseModel):
    mode: Literal["mock", "http"] = "mock"
    preliminary: ModelEndpointSettings | None = None
    judge: ModelEndpointSettings | None = None
    sam3: ModelEndpointSettings | None = None


class AppConfig(BaseModel):
    config_files: ConfigFileSettings = ConfigFileSettings()
    agent: AgentSettings = AgentSettings()
    logging: LoggingSettings = LoggingSettings()
    event_store: EventStoreSettings = EventStoreSettings()
    orchestrator: OrchestratorSettings = OrchestratorSettings()
    callback: CallbackSettings
    mock_clients: MockClientSettings
    prompts: PromptSettings | None = None
    scene_policies: SceneActivationPolicyConfig | None = None
    category_registry: dict[str, CategoryRegistryRule] = Field(default_factory=dict)
    open_risk_registry: OpenRiskRegistry = OpenRiskRegistry()
    model_clients: ModelClientSettings = ModelClientSettings()
    minio: MinioSettings = MinioSettings()
    review: ReviewSettings = ReviewSettings()

    @model_validator(mode="after")
    def validate_scene_policy_category_references(self) -> "AppConfig":
        if self.scene_policies is None or not self.category_registry:
            return self

        known_categories = set(self.category_registry)
        unknown_categories: set[str] = set()

        def collect_unknown(rule: SceneActivationRule) -> None:
            for category in (
                *rule.enabled_categories,
                *rule.disabled_categories,
                *rule.priority_categories,
            ):
                if category not in known_categories:
                    unknown_categories.add(category)

        for rule in self.scene_policies.camera_defaults.values():
            collect_unknown(rule)
        for rule in self.scene_policies.location_defaults.values():
            collect_unknown(rule)
        for location_overrides in self.scene_policies.overrides.values():
            for rule in location_overrides.values():
                collect_unknown(rule)

        if unknown_categories:
            categories = ", ".join(sorted(unknown_categories))
            raise ValueError(f"Unknown categories referenced in scene_policies: {categories}")

        return self

    @model_validator(mode="after")
    def validate_chain_mode_settings(self) -> "AppConfig":
        if self.orchestrator.chain_mode == "vlm1_only" and self.callback.send_refined:
            raise ValueError("vlm1_only chain_mode requires send_refined=false")
        return self


def load_config(path: str | Path) -> AppConfig:
    """Load YAML configuration into a validated application config."""
    config_path = Path(path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config_files = data.get("config_files", {})
    if isinstance(config_files, dict) and config_files.get("prompt_config"):
        prompt_config_path = _resolve_path(base_dir=config_path.parent, candidate=Path(config_files["prompt_config"]))
        prompt_data = yaml.safe_load(prompt_config_path.read_text(encoding="utf-8")) or {}
        data = _deep_merge_dicts(data, prompt_data)
    config = AppConfig.model_validate(data)
    base_dir = config_path.parent
    config.callback = _resolve_callback_settings(config.callback)
    if config.config_files.prompt_config is not None:
        config.config_files = ConfigFileSettings(
            prompt_config=_resolve_path(base_dir, config.config_files.prompt_config)
        )
    if config.event_store.base_dir is not None:
        config.event_store = EventStoreSettings(
            backend=config.event_store.backend,
            base_dir=_resolve_path(base_dir, config.event_store.base_dir),
        )
    config.mock_clients = MockClientSettings(
        preliminary_fixture=_resolve_path(base_dir, config.mock_clients.preliminary_fixture),
        segmentation_fixture=_resolve_path(base_dir, config.mock_clients.segmentation_fixture),
        evidence_judge_fixture=_resolve_path(base_dir, config.mock_clients.evidence_judge_fixture),
    )
    return config


def _resolve_path(base_dir: Path, candidate: Path) -> Path:
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def _deep_merge_dicts(base: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in incoming.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(existing, value)
        else:
            merged[key] = value
    return merged


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
