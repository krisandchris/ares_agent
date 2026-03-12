"""Scene activation resolution for camera/location-aware VLM-1 prompting."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ares_agent.infra.config import SceneActivationPolicyConfig, SceneActivationRule


class SceneActivationContext(BaseModel):
    camera_id: str
    location: str
    enabled_categories: list[str] = Field(default_factory=list)
    disabled_categories: list[str] = Field(default_factory=list)
    priority_categories: list[str] = Field(default_factory=list)
    location_constraints: list[str] = Field(default_factory=list)
    scene_hint: str = ""
    open_risk_guidance: str = (
        "If visible evidence strongly suggests a risk outside the priority standard categories, output open_risk with a concise risk type."
    )


def resolve_scene_activation_context(
    config: SceneActivationPolicyConfig,
    *,
    camera_id: str,
    location: str,
) -> SceneActivationContext:
    camera_default = config.camera_defaults.get(camera_id, SceneActivationRule())
    location_default = config.location_defaults.get(location, SceneActivationRule())
    override = config.overrides.get(location, {}).get(camera_id, SceneActivationRule())

    return SceneActivationContext(
        camera_id=camera_id,
        location=location,
        enabled_categories=_override_or_merge(
            override.enabled_categories,
            camera_default.enabled_categories,
            location_default.enabled_categories,
        ),
        disabled_categories=_override_or_merge(
            override.disabled_categories,
            camera_default.disabled_categories,
            location_default.disabled_categories,
        ),
        priority_categories=_override_or_merge(
            override.priority_categories,
            camera_default.priority_categories,
            location_default.priority_categories,
        ),
        location_constraints=_override_or_merge(
            override.location_constraints,
            camera_default.location_constraints,
            location_default.location_constraints,
        ),
        scene_hint=override.scene_hint or camera_default.scene_hint or location_default.scene_hint,
        open_risk_guidance=(
            "If visible evidence strongly suggests a risk outside the priority standard categories, output open_risk with a concise risk type."
        ),
    )


def _override_or_merge(
    override_values: list[str],
    camera_values: list[str],
    location_values: list[str],
) -> list[str]:
    if override_values:
        return list(override_values)
    merged: list[str] = []
    for value in [*camera_values, *location_values]:
        if value not in merged:
            merged.append(value)
    return merged
