"""Prompt builders used by the HTTP-style VLM clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ares_agent.domain.events import EventSeed


class PromptBuilder:
    """Protocol-like base class for inspection prompt builders."""

    def build_preliminary_messages(self, seed: EventSeed) -> list[dict[str, Any]]:
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

    def build_preliminary_messages(self, seed: EventSeed) -> list[dict[str, Any]]:
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

    preliminary_system_template: str
    preliminary_user_template: str
    judge_system_template: str
    judge_user_template: str

    def build_preliminary_messages(self, seed: EventSeed) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": self.preliminary_system_template.strip()},
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
