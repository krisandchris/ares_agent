"""Prompt builders used by the HTTP-style VLM clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ares_agent.domain.events import EventSeed
from ares_agent.workflows.inspection_event_workflow import PreliminaryResult


class PromptBuilder:
    """Protocol-like base class for inspection prompt builders."""

    def build_preliminary_messages(self, seed: EventSeed) -> list[dict[str, Any]]:
        raise NotImplementedError

    def build_judge_messages(
        self,
        *,
        event_id: str,
        category_code: str,
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
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
                        "text": f"Analyze frame {seed.frame_id} for inspection violations.",
                    },
                    {"type": "image_url", "image_url": {"url": seed.image_uri}},
                ],
            },
        ]

    def build_judge_messages(
        self,
        *,
        event_id: str,
        category_code: str,
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> list[dict[str, Any]]:
        user_text = (
            f"Judge event {event_id} for category {category_code}. "
            f"risk_level={preliminary.risk_level}; "
            f"prelim_confidence={preliminary.prelim_confidence}; "
            f"need_retake={preliminary.need_retake}; "
            f"evidence_targets={', '.join(preliminary.evidence_targets)}; "
            f"open_risk_hints={', '.join(preliminary.open_risk_hints) if preliminary.open_risk_hints else 'none'}; "
            f"evidence_basis_summary={evidence_basis_summary}"
        )
        return [
            {"role": "system", "content": "You are an evidence judge for visual inspection."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                ],
            },
        ]


@dataclass
class ConfigurableInspectionPromptBuilder(PromptBuilder):
    """Prompt builder backed by YAML-configured template strings."""

    preliminary_system_template: str
    preliminary_user_template: str
    judge_system_template: str

    def build_preliminary_messages(self, seed: EventSeed) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": self.preliminary_system_template.strip()},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": self.preliminary_user_template.format(
                            image_uri=seed.image_uri,
                            frame_id=seed.frame_id,
                            device_id=seed.device_id,
                            task_id=seed.task_id,
                            occur_time=seed.occur_time,
                        ).strip(),
                    },
                    {"type": "image_url", "image_url": {"url": seed.image_uri}},
                ],
            },
        ]

    def build_judge_messages(
        self,
        *,
        event_id: str,
        category_code: str,
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> list[dict[str, Any]]:
        dynamic_user_text = (
            f"event_id={event_id}\n"
            f"candidate_category={category_code}\n"
            f"vlm1_risk_level={preliminary.risk_level}\n"
            f"vlm1_prelim_confidence={preliminary.prelim_confidence}\n"
            f"vlm1_need_retake={preliminary.need_retake}\n"
            f"vlm1_evidence_targets={', '.join(preliminary.evidence_targets)}\n"
            f"vlm1_open_risk_hints={', '.join(preliminary.open_risk_hints) if preliminary.open_risk_hints else 'none'}\n"
            f"evidence_basis_summary={evidence_basis_summary}"
        )
        return [
            {"role": "system", "content": self.judge_system_template.strip()},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": dynamic_user_text,
                    },
                ],
            },
        ]
