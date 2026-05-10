"""Post-inference result gate for location+camera category filtering."""

from __future__ import annotations

from typing import Any

from ares_agent.domain.stage2_output import Stage2Candidate
from ares_agent.infra.logging import get_logger

logger = __name__


class ResultGate:
    """Filter violation candidates by location+camera rules.

    Unlike the scene_policy pre-filter (which limits what the model sees),
    this gate runs AFTER inference and filters what the model outputs.
    The model reasons over all categories; the gate keeps only those
    allowed for the given location+camera pair.
    """

    def __init__(self, scene_policies: dict[str, Any]) -> None:
        self._policies = scene_policies

    def filter(
        self,
        location: str,
        camera_id: str,
        candidates: list[Stage2Candidate],
    ) -> list[Stage2Candidate]:
        allowed = self._get_allowed_categories(location, camera_id)
        if allowed is None:
            return candidates
        filtered = [c for c in candidates if self._is_allowed(c.violation_category, allowed)]
        if not filtered:
            get_logger(logger).info(
                "result_gate.all_filtered",
                location=location,
                camera_id=camera_id,
                original_count=len(candidates),
            )
        return filtered

    def _get_allowed_categories(self, location: str, camera_id: str) -> set[str] | None:
        loc_policies = self._policies.get(location)
        if not loc_policies:
            return None
        camera_rule = loc_policies.get(camera_id)
        if not camera_rule:
            return None
        cats = camera_rule.get("enabled_categories")
        if not cats:
            return None
        return set(cats)

    def _is_allowed(self, violation_categories: list[str] | str, allowed: set[str]) -> bool:
        if isinstance(violation_categories, str):
            return violation_categories in allowed
        return any(cat in allowed for cat in violation_categories)

    def is_category_allowed(self, location: str, camera_id: str, category: str) -> bool:
        """Check if a single category is allowed for the given location+camera."""
        allowed = self._get_allowed_categories(location, camera_id)
        if allowed is None:
            return True
        return category in allowed
