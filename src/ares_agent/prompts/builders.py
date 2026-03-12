"""Prompt builders used by the HTTP-style VLM clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ares_agent.domain.events import EventSeed
from ares_agent.prompts.scene_activation import SceneActivationContext


class PromptBuilder:
    """Protocol-like base class for inspection prompt builders."""

    def build_preliminary_messages(
        self,
        seed: EventSeed,
        scene_activation_context: SceneActivationContext | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def build_judge_messages(
        self,
        *,
        category_code: str,
        overlay_image: str | None,
        mask_labels: list[str],
        relation_hint: str,
        evidence_basis_summary: str,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class DefaultInspectionPromptBuilder(PromptBuilder):
    """Default prompt builder for preliminary and evidence-judge VLM calls."""

    def build_preliminary_messages(
        self,
        seed: EventSeed,
        scene_activation_context: SceneActivationContext | None = None,
    ) -> list[dict[str, Any]]:
        del scene_activation_context
        return [
            {"role": "system", "content": "You are a visual preliminary inspection model."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze inspection image for violations.",
                    },
                    {"type": "image_url", "image_url": {"url": seed.image_uri}},
                ],
            },
        ]

    def build_judge_messages(
        self,
        *,
        category_code: str,
        overlay_image: str | None,
        mask_labels: list[str],
        relation_hint: str,
        evidence_basis_summary: str,
    ) -> list[dict[str, Any]]:
        user_text = (
            f"category_code={category_code}; "
            f"mask_labels={', '.join(mask_labels)}; "
            f"relation_hint={relation_hint}; "
            f"evidence_basis_summary={evidence_basis_summary}"
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        if overlay_image:
            content.append({"type": "image_url", "image_url": {"url": overlay_image}})
        return [
            {"role": "system", "content": "You are an evidence judge for visual inspection."},
            {
                "role": "user",
                "content": content,
            },
        ]


@dataclass
class ConfigurableInspectionPromptBuilder(PromptBuilder):
    """Prompt builder backed by YAML-configured template strings."""

    preliminary_role_block: str
    preliminary_scene_activation_block_template: str
    preliminary_category_focus_block_template: str
    preliminary_reasoning_block: str
    preliminary_output_contract_block: str
    preliminary_user_template: str
    judge_system_template: str
    judge_user_template: str
    category_registry: dict[str, Any]
    open_risk_guidance_default: str
    scene_activation_resolver: Any | None = None

    def build_preliminary_messages(
        self,
        seed: EventSeed,
        scene_activation_context: SceneActivationContext | None = None,
    ) -> list[dict[str, Any]]:
        if scene_activation_context is None:
            if self.scene_activation_resolver is not None:
                resolved_context = self.scene_activation_resolver.resolve(
                    camera_id=seed.camera_id,
                    location=seed.location,
                )
            else:
                resolved_context = SceneActivationContext(
                    camera_id=seed.camera_id,
                    location=seed.location,
                    open_risk_guidance=self.open_risk_guidance_default,
                )
        else:
            resolved_context = scene_activation_context
        open_risk_guidance = resolved_context.open_risk_guidance or self.open_risk_guidance_default
        category_definitions = self._render_category_definitions(resolved_context.priority_categories)
        system_prompt = "\n\n".join(
            [
                self.preliminary_role_block.strip(),
                self.preliminary_scene_activation_block_template.format(
                    scene_hint=resolved_context.scene_hint,
                    priority_categories=", ".join(resolved_context.priority_categories),
                    open_risk_guidance=open_risk_guidance,
                ).strip(),
                self.preliminary_category_focus_block_template.format(
                    category_definitions=category_definitions,
                ).strip(),
                self.preliminary_reasoning_block.strip(),
                self.preliminary_output_contract_block.strip(),
            ]
        )
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": self.preliminary_user_template.strip(),
                    },
                    {"type": "image_url", "image_url": {"url": seed.image_uri}},
                ],
            },
        ]

    def build_judge_messages(
        self,
        *,
        category_code: str,
        overlay_image: str | None,
        mask_labels: list[str],
        relation_hint: str,
        evidence_basis_summary: str,
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self.judge_user_template.format(
                    category_code=category_code,
                    mask_labels=", ".join(mask_labels),
                    relation_hint=relation_hint,
                    evidence_basis_summary=evidence_basis_summary,
                ).strip(),
            }
        ]
        if overlay_image:
            content.append({"type": "image_url", "image_url": {"url": overlay_image}})
        return [
            {"role": "system", "content": self.judge_system_template.strip()},
            {
                "role": "user",
                "content": content,
            },
        ]

    def _render_category_definitions(self, priority_categories: list[str]) -> str:
        rendered_rules: list[str] = []
        for code in priority_categories:
            rule = self.category_registry.get(code)
            if rule is None:
                continue
            definition = _rule_value(rule, "definition")
            common_objects = _rule_list(rule, "common_objects")
            relation_focus = _rule_list(rule, "relation_focus")
            exceptions = _rule_list(rule, "exceptions")
            rendered_rules.append(
                "\n".join(
                    [
                        f"- {code}",
                        f"  definition: {definition}",
                        f"  common_objects: {', '.join(common_objects) if common_objects else 'none'}",
                        f"  relation_focus: {', '.join(relation_focus) if relation_focus else 'none'}",
                        f"  exceptions: {', '.join(exceptions) if exceptions else 'none'}",
                    ]
                )
            )
        return "\n".join(rendered_rules) if rendered_rules else "- none"


def _rule_value(rule: Any, key: str) -> str:
    if isinstance(rule, dict):
        return str(rule.get(key, ""))
    return str(getattr(rule, key))


def _rule_list(rule: Any, key: str) -> list[str]:
    if isinstance(rule, dict):
        value = rule.get(key, [])
    else:
        value = getattr(rule, key)
    return [str(item) for item in value]
