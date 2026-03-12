"""Helpers for assembling the final VLM-1 preliminary prompt."""

from __future__ import annotations

from typing import Mapping, TypedDict

from ares_agent.infra.config import CategoryRegistryRule

from ares_agent.prompts.scene_activation import SceneActivationContext


class CategoryRulePayload(TypedDict):
    definition: str
    common_objects: list[str]
    relation_focus: list[str]
    exceptions: list[str]


CategoryRegistryEntry = CategoryRegistryRule | CategoryRulePayload


class CategoryDefinitionRenderer:
    """Render focused category references for prioritized categories only."""

    def __init__(self, category_registry: Mapping[str, CategoryRegistryEntry]) -> None:
        self.category_registry = category_registry

    def render(self, priority_categories: list[str]) -> str:
        rendered_rules: list[str] = []
        for code in priority_categories:
            rule = self.category_registry.get(code)
            if rule is None:
                continue
            rendered_rules.append(
                "\n".join(
                    [
                        f"- {code}",
                        f"  definition: {_rule_value(rule, 'definition')}",
                        f"  common_objects: {_format_list(_rule_list(rule, 'common_objects'))}",
                        f"  relation_focus: {_format_list(_rule_list(rule, 'relation_focus'))}",
                        f"  exceptions: {_format_list(_rule_list(rule, 'exceptions'))}",
                    ]
                )
            )
        return "\n".join(rendered_rules) if rendered_rules else "- none"


class PreliminaryPromptAssembler:
    """Assemble the final preliminary system prompt from structured blocks."""

    def assemble(
        self,
        *,
        role_block: str,
        scene_activation_block_template: str,
        category_focus_block_template: str,
        reasoning_block: str,
        output_contract_block: str,
        scene_activation_context: SceneActivationContext,
        category_definitions: str,
    ) -> str:
        return "\n\n".join(
            [
                role_block.strip(),
                scene_activation_block_template.format(
                    scene_hint=scene_activation_context.scene_hint,
                    priority_categories=", ".join(scene_activation_context.priority_categories),
                    open_risk_guidance=scene_activation_context.open_risk_guidance,
                ).strip(),
                category_focus_block_template.format(
                    category_definitions=category_definitions,
                ).strip(),
                reasoning_block.strip(),
                output_contract_block.strip(),
            ]
        )


def _rule_value(rule: CategoryRegistryEntry, key: str) -> str:
    if isinstance(rule, dict):
        return str(rule.get(key, ""))
    return str(getattr(rule, key))


def _rule_list(rule: CategoryRegistryEntry, key: str) -> list[str]:
    if isinstance(rule, dict):
        value = rule.get(key, [])
    else:
        value = getattr(rule, key)
    return [str(item) for item in value]


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "none"
