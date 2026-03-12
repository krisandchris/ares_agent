"""Prompt builders used by the HTTP-style VLM clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, TypedDict

from ares_agent.domain.events import EventSeed
from ares_agent.prompts.preliminary_prompt import (
    CategoryDefinitionRenderer,
    CategoryRegistryEntry,
    PreliminaryPromptAssembler,
)
from ares_agent.prompts.scene_activation import SceneActivationContext


class ImageUrlPayload(TypedDict):
    url: str


class MessageContentPart(TypedDict, total=False):
    type: str
    text: str
    image_url: ImageUrlPayload


class PromptMessage(TypedDict):
    role: str
    content: str | list[MessageContentPart]


class SceneActivationResolver(Protocol):
    def resolve(self, *, camera_id: str, location: str) -> SceneActivationContext: ...


class PromptBuilder:
    """Protocol-like base class for inspection prompt builders."""

    def build_preliminary_messages(
        self,
        seed: EventSeed,
        scene_activation_context: SceneActivationContext | None = None,
    ) -> list[PromptMessage]:
        raise NotImplementedError

    def build_judge_messages(
        self,
        *,
        category_code: str,
        overlay_image: str | None,
        mask_labels: list[str],
        relation_hint: str,
        evidence_basis_summary: str,
    ) -> list[PromptMessage]:
        raise NotImplementedError


class DefaultInspectionPromptBuilder(PromptBuilder):
    """Default prompt builder for preliminary and evidence-judge VLM calls."""

    def build_preliminary_messages(
        self,
        seed: EventSeed,
        scene_activation_context: SceneActivationContext | None = None,
    ) -> list[PromptMessage]:
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
    ) -> list[PromptMessage]:
        user_text = (
            f"category_code={category_code}; "
            f"mask_labels={', '.join(mask_labels)}; "
            f"relation_hint={relation_hint}; "
            f"evidence_basis_summary={evidence_basis_summary}"
        )
        content: list[MessageContentPart] = [{"type": "text", "text": user_text}]
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
    category_registry: Mapping[str, CategoryRegistryEntry]
    open_risk_guidance_default: str
    scene_activation_resolver: SceneActivationResolver | None = None
    preliminary_prompt_assembler: PreliminaryPromptAssembler | None = None

    def build_preliminary_messages(
        self,
        seed: EventSeed,
        scene_activation_context: SceneActivationContext | None = None,
    ) -> list[PromptMessage]:
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
        resolved_context = resolved_context.model_copy(
            update={"open_risk_guidance": open_risk_guidance},
        )
        category_definitions = CategoryDefinitionRenderer(self.category_registry).render(
            resolved_context.priority_categories
        )
        assembler = self.preliminary_prompt_assembler or PreliminaryPromptAssembler()
        system_prompt = assembler.assemble(
            role_block=self.preliminary_role_block,
            scene_activation_block_template=self.preliminary_scene_activation_block_template,
            category_focus_block_template=self.preliminary_category_focus_block_template,
            reasoning_block=self.preliminary_reasoning_block,
            output_contract_block=self.preliminary_output_contract_block,
            scene_activation_context=resolved_context,
            category_definitions=category_definitions,
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
    ) -> list[PromptMessage]:
        content: list[MessageContentPart] = [
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
