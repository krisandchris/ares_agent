"""HTTP-style clients that mimic real VLM and SAM3 services."""

from __future__ import annotations

import json
from typing import Callable
from urllib import request

from ares_agent.domain.events import EventSeed
from ares_agent.prompts.builders import DefaultInspectionPromptBuilder
from ares_agent.workflows.inspection_event_workflow import (
    EvidenceJudgeResult,
    PreliminaryResult,
    SegmentationResult,
)


Requester = Callable[[str, dict[str, str], dict[str, object]], dict[str, object]]


def _default_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, headers=headers, method="POST")
    with request.urlopen(req) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


class SglangVlmPreliminaryClient:
    """OpenAI-compatible preliminary VLM client for SGLang/vLLM style servers."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        requester: Requester | None = None,
        prompt_builder: DefaultInspectionPromptBuilder | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.requester = requester or _default_requester
        self.prompt_builder = prompt_builder or DefaultInspectionPromptBuilder()

    def analyze(self, seed: EventSeed) -> PreliminaryResult:
        payload = {
            "model": self.model_name,
            "messages": self.prompt_builder.build_preliminary_messages(seed),
            "temperature": 0,
        }
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        content = response["choices"][0]["message"]["content"]
        data = json.loads(content) if isinstance(content, str) else content
        return PreliminaryResult.model_validate(data)


class SglangVlmJudgeClient:
    """OpenAI-compatible evidence judge client for SGLang/vLLM style servers."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        requester: Requester | None = None,
        prompt_builder: DefaultInspectionPromptBuilder | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.requester = requester or _default_requester
        self.prompt_builder = prompt_builder or DefaultInspectionPromptBuilder()

    def judge(
        self,
        *,
        event_id: str,
        category_code: str,
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> EvidenceJudgeResult:
        payload = {
            "model": self.model_name,
            "messages": self.prompt_builder.build_judge_messages(
                event_id=event_id,
                category_code=category_code,
                evidence_basis_summary=evidence_basis_summary,
                preliminary=preliminary,
            ),
            "temperature": 0,
        }
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        content = response["choices"][0]["message"]["content"]
        data = json.loads(content) if isinstance(content, str) else content
        return EvidenceJudgeResult.model_validate(data)


class Sam3FastApiClient:
    """FastAPI-style SAM3 client."""

    def __init__(
        self,
        *,
        endpoint: str,
        requester: Requester | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.requester = requester or _default_requester

    def segment(self, event_id: str, targets: list[str]) -> SegmentationResult:
        payload = {
            "event_id": event_id,
            "targets": targets,
        }
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        return SegmentationResult.model_validate(response)
