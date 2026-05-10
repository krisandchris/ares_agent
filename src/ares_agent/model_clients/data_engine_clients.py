"""VLM clients using data_engine Step1/Step2 prompt flow."""

from __future__ import annotations

import json
from typing import Callable, NotRequired, TypedDict, cast
from urllib import request as urllib_request

from ares_agent.domain.events import EventSeed, generate_event_id
from ares_agent.domain.stage1_output import Stage1Output
from ares_agent.domain.stage2_output import Stage2Output
from ares_agent.infra.log_decorators import log_external_call
from ares_agent.infra.log_context import get_bound_log_context_value
from ares_agent.infra.logging import get_logger
from ares_agent.prompts.data_engine_prompts import (
    DataEngineStep1PromptBuilder,
    DataEngineStep2PromptBuilder,
)
from ares_agent.prompts.stage_mapping import (
    map_stage1_to_preliminary,
    map_stage2_to_evidence_judge,
    reconstruct_stage1_json,
)
from ares_agent.workflows.inspection_event_workflow import (
    EvidenceJudgeResult,
    PreliminaryResult,
)

logger = __name__


class _ChatMessage(TypedDict):
    content: str | dict


class _ChatChoice(TypedDict):
    message: _ChatMessage


class _ChatCompletionResponse(TypedDict):
    choices: list[_ChatChoice]


class _RequestPayload(TypedDict):
    model: str
    messages: list[dict]
    temperature: float
    max_tokens: NotRequired[int]


def _strip_json_fence(text: str) -> str:
    """Strip ```json ... ``` fences from model output."""
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1 :]
    if text.endswith("```"):
        text = text[: -len("```")]
    return text.strip()


def _default_requester(
    url: str,
    headers: dict[str, str],
    payload: dict,
    *,
    timeout_ms: int,
) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url=url, data=body, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=timeout_ms / 1000) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except urllib_request.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        get_logger(logger).error(
            "vlm.http_error",
            url=url,
            status_code=exc.code,
            error_body=error_body[:500],
        )
        raise


Requester = Callable[[str, dict[str, str], dict], dict]


class DataEngineStep1Client:
    """VLM client using data_engine Step1 prompt. Implements PreliminaryClient."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        prompt_builder: DataEngineStep1PromptBuilder,
        timeout_ms: int = 30000,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        requester: Requester | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.prompt_builder = prompt_builder
        self.timeout_ms = timeout_ms
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.requester = requester or (
            lambda url, headers, payload: _default_requester(
                url, headers, payload, timeout_ms=self.timeout_ms,
            )
        )

    @log_external_call(
        "data_engine_step1",
        field_extractor=lambda self, seed: {
            "event_id": cast(str, get_bound_log_context_value("event_id")) or generate_event_id(seed),
            "camera_id": seed.camera_id,
            "location": seed.location,
        },
    )
    def analyze(self, seed: EventSeed) -> PreliminaryResult:
        messages = self.prompt_builder.build_messages(
            image_uri=seed.image_uri,
            image_hint=seed.camera_id,
        )
        payload: _RequestPayload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        content = response["choices"][0]["message"]["content"]
        raw_text = _strip_json_fence(content) if isinstance(content, str) else json.dumps(content)
        stage1 = Stage1Output.model_validate_json(raw_text)
        get_logger(logger).info(
            "data_engine_step1.parsed",
            relation_count=len(stage1.key_relations),
            anchor_count=len(stage1.key_anchors),
        )
        return map_stage1_to_preliminary(stage1)


class DataEngineStep2Client:
    """VLM client using data_engine Step2 prompt. Implements EvidenceJudgeClient."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        prompt_builder: DataEngineStep2PromptBuilder,
        timeout_ms: int = 30000,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        requester: Requester | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.prompt_builder = prompt_builder
        self.timeout_ms = timeout_ms
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.requester = requester or (
            lambda url, headers, payload: _default_requester(
                url, headers, payload, timeout_ms=self.timeout_ms,
            )
        )

    @log_external_call(
        "data_engine_step2",
        field_extractor=lambda self, **kwargs: {
            "event_id": kwargs.get("event_id"),
            "category_code": kwargs.get("category_code"),
        },
    )
    def judge(
        self,
        *,
        event_id: str | None = None,
        category_code: str,
        overlay_image: str | None = None,
        mask_labels: list[str] | None = None,
        relation_hint: str = "",
        segmentation_status: str = "ok",
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> EvidenceJudgeResult:
        del category_code, mask_labels, relation_hint, segmentation_status, evidence_basis_summary
        stage1_json = reconstruct_stage1_json(preliminary)
        sample_id = event_id or "unknown"
        image_uri = overlay_image or ""
        messages = self.prompt_builder.build_messages(
            image_uri=image_uri,
            stage1_json=stage1_json,
            sample_id=sample_id,
        )
        payload: _RequestPayload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        content = response["choices"][0]["message"]["content"]
        raw_text = _strip_json_fence(content) if isinstance(content, str) else json.dumps(content)
        stage2 = Stage2Output.model_validate_json(raw_text)
        get_logger(logger).info(
            "data_engine_step2.parsed",
            candidate_count=len(stage2.candidates),
            verification_count=len(stage2.fact_verifications),
        )
        return map_stage2_to_evidence_judge(stage2)
