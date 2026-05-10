"""Prompt builders backed by data_engine templates and registry YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ares_agent.prompts.builders import MessageContentPart, PromptMessage


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _render_named_blocks(mapping: dict[str, Any]) -> str:
    lines: list[str] = []
    for name, value in mapping.items():
        lines.append(f"[{name}]")
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                if isinstance(inner_value, list):
                    lines.append(f"{inner_key}:")
                    lines.extend(f"- {item}" for item in inner_value)
                else:
                    lines.append(f"{inner_key}: {inner_value}")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines).strip()


def _render_output_limits(output_limits: dict[str, Any]) -> str:
    lines: list[str] = []
    for tier, config in output_limits.items():
        lines.append(f"[{tier}]")
        if isinstance(config, dict):
            for key, value in config.items():
                lines.append(f"{key}: {value}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_scalar_or_list_blocks(mapping: dict[str, Any]) -> str:
    lines: list[str] = []
    for name, value in mapping.items():
        lines.append(f"[{name}]")
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines).strip()


@dataclass(frozen=True)
class _Stage1Registry:
    raw: dict[str, Any]

    @classmethod
    def from_file(cls, path: Path) -> _Stage1Registry:
        return cls(raw=_load_yaml(path))

    def build_prompt_context(self) -> dict[str, str]:
        return {
            "{{CATEGORY_BLOCK}}": _render_bullets(self.raw["violation_categories"]),
            "{{SPATIAL_ATTENTION_BLOCK}}": _render_named_blocks(self.raw["spatial_attention_policy"]),
            "{{ANCHOR_BLOCK}}": _render_bullets(self.raw["anchor_enum"]),
            "{{RELATION_BLOCK}}": _render_bullets(self.raw["relation_enum"]),
            "{{RELATION_DESCRIPTION_RULES_BLOCK}}": _render_scalar_or_list_blocks(self.raw["relation_description_rules"]),
            "{{RELATION_SELECTION_RULES_BLOCK}}": _render_bullets(self.raw["relation_selection_rules"]),
            "{{OBSERVATION_POLICY_BLOCK}}": _render_named_blocks(self.raw["observation_policy"]),
            "{{OUTPUT_LIMITS_BLOCK}}": _render_output_limits(self.raw["output_limits"]),
        }


@dataclass(frozen=True)
class _Stage2Registry:
    raw: dict[str, Any]

    @classmethod
    def from_file(cls, path: Path) -> _Stage2Registry:
        return cls(raw=_load_yaml(path))

    def build_prompt_context(self) -> dict[str, str]:
        return {
            "{{VIOLATION_CATEGORIES_BLOCK}}": _render_bullets(self.raw["violation_categories"]),
            "{{BBOX_POLICY_BLOCK}}": _render_scalar_or_list_blocks(self.raw["bbox_policy"]),
            "{{VISIBILITY_LEVEL_ENUM_BLOCK}}": _render_bullets(self.raw["visibility_level_enum"]),
            "{{INFORMATION_LOSS_TYPE_ENUM_BLOCK}}": _render_bullets(self.raw["information_loss_type_enum"]),
            "{{VERIFICATION_RESULT_ENUM_BLOCK}}": _render_bullets(self.raw["verification_result_enum"]),
            "{{SAMPLE_CATEGORY_ENUM_BLOCK}}": _render_bullets(self.raw["sample_category_enum"]),
            "{{CONFIDENCE_RULES_BLOCK}}": _render_scalar_or_list_blocks(self.raw["confidence_rules"]),
            "{{ATTRIBUTE_RULES_BLOCK}}": _render_scalar_or_list_blocks(self.raw["attribute_rules"]),
        }


@dataclass
class DataEngineStep1PromptBuilder:
    """Builds Step1 system/user prompts from data_engine templates."""

    registry: _Stage1Registry
    system_template: str
    user_template: str

    @classmethod
    def from_files(
        cls,
        registry_path: Path,
        system_template_path: Path,
        user_template_path: Path,
    ) -> DataEngineStep1PromptBuilder:
        return cls(
            registry=_Stage1Registry.from_file(registry_path),
            system_template=system_template_path.read_text(encoding="utf-8"),
            user_template=user_template_path.read_text(encoding="utf-8"),
        )

    def build_messages(self, image_uri: str, image_hint: str = "") -> list[PromptMessage]:
        context = self.registry.build_prompt_context()
        system_prompt = self.system_template
        for placeholder, value in context.items():
            system_prompt = system_prompt.replace(placeholder, value)
        user_prompt = self.user_template.replace("{{IMAGE_HINT}}", image_hint)
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_uri}},
                ],
            },
        ]


@dataclass
class DataEngineStep2PromptBuilder:
    """Builds Step2 system/user prompts from data_engine templates."""

    registry: _Stage2Registry
    system_template: str
    user_template: str

    @classmethod
    def from_files(
        cls,
        registry_path: Path,
        system_template_path: Path,
        user_template_path: Path,
    ) -> DataEngineStep2PromptBuilder:
        return cls(
            registry=_Stage2Registry.from_file(registry_path),
            system_template=system_template_path.read_text(encoding="utf-8"),
            user_template=user_template_path.read_text(encoding="utf-8"),
        )

    def build_messages(
        self,
        image_uri: str,
        stage1_json: str,
        sample_id: str,
    ) -> list[PromptMessage]:
        context = self.registry.build_prompt_context()
        system_prompt = self.system_template
        for placeholder, value in context.items():
            system_prompt = system_prompt.replace(placeholder, value)
        user_prompt = (
            self.user_template
            .replace("{{stage1_json}}", stage1_json)
            .replace("{{sample_id}}", sample_id)
        )
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_uri}},
                ],
            },
        ]
