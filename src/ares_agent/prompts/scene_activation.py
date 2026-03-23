"""Scene activation resolution for camera/location-aware VLM-1 prompting."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ares_agent.infra.config import SceneActivationPolicyConfig, SceneCameraRule, SceneLocationPolicy


class SceneActivationContext(BaseModel):
    camera_id: str
    location: str
    enabled_categories: list[str] = Field(default_factory=list)
    location_constraints: list[str] = Field(default_factory=list)
    open_risk_guidance: str = ""


class ScenePolicyResolver:
    """Resolve scene activation context from camera/location policy config."""

    def __init__(self, config: SceneActivationPolicyConfig) -> None:
        self.config = config

    def resolve(self, *, camera_id: str, location: str) -> SceneActivationContext:
        return resolve_scene_activation_context(
            self.config,
            camera_id=camera_id,
            location=location,
        )


def resolve_scene_activation_context(
    config: SceneActivationPolicyConfig,
    *,
    camera_id: str,
    location: str,
) -> SceneActivationContext:
    location_policy = config.root.get(location)
    camera_rule = _get_camera_rule(location_policy, camera_id)

    return SceneActivationContext(
        camera_id=camera_id,
        location=location,
        enabled_categories=list(camera_rule.enabled_categories),
        location_constraints=list(camera_rule.location_constraints),
    )

def _get_camera_rule(location_policy: SceneLocationPolicy | None, camera_id: str) -> SceneCameraRule:
    if location_policy is None:
        return SceneCameraRule()
    if camera_id == "front":
        return location_policy.front
    if camera_id == "left":
        return location_policy.left
    if camera_id == "right":
        return location_policy.right
    return SceneCameraRule()
