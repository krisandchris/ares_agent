"""HTTP-style clients that mimic real VLM and SAM3 services."""

from __future__ import annotations

import json
from typing import Callable, TypedDict, cast
from urllib import request
from urllib.parse import urlparse

from ares_agent.domain.events import EventSeed, generate_event_id
from ares_agent.domain.json_types import JsonObject
from ares_agent.infra.log_decorators import log_external_call
from ares_agent.prompts.builders import PromptBuilder, PromptMessage
from ares_agent.workflows.inspection_event_workflow import (
    EvidenceJudgeResult,
    PreliminaryResult,
    SegmentationResult,
)


class PreliminaryRequestPayload(TypedDict, total=False):
    model: str
    messages: list[PromptMessage]
    temperature: float
    max_tokens: int


class Sam3RequestPayload(TypedDict):
    image_uri: str
    targets: list[str]


Requester = Callable[
    [str, dict[str, str], PreliminaryRequestPayload | Sam3RequestPayload],
    JsonObject,
]


class ChatMessage(TypedDict):
    content: str | JsonObject


class ChatChoice(TypedDict):
    message: ChatMessage


class ChatCompletionResponse(TypedDict):
    choices: list[ChatChoice]


def _default_requester(
    url: str,
    headers: dict[str, str],
    payload: PreliminaryRequestPayload | Sam3RequestPayload,
    *,
    timeout_ms: int,
) -> JsonObject:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout_ms / 1000) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _extract_chat_message_content(response: JsonObject) -> str | JsonObject:
    typed_response = cast(ChatCompletionResponse, response)
    return typed_response["choices"][0]["message"]["content"]


class SglangVlmPreliminaryClient:
    """OpenAI-compatible preliminary VLM client for SGLang/vLLM style servers."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        timeout_ms: int = 10000,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        requester: Requester | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout_ms = timeout_ms
        self.temperature = temperature
        self.max_tokens = max_tokens
        if prompt_builder is None:
            raise ValueError("SglangVlmPreliminaryClient requires an explicit prompt_builder")
        self.requester = requester or (
            lambda url, headers, payload: _default_requester(
                url,
                headers,
                payload,
                timeout_ms=self.timeout_ms,
            )
        )
        self.prompt_builder = prompt_builder

    @log_external_call(
        "vlm_preliminary",
        field_extractor=lambda self, seed: {
            "event_id": generate_event_id(seed),
            "camera_id": seed.camera_id,
            "location": seed.location,
            "endpoint_host": urlparse(self.endpoint).netloc,
            "model_name": self.model_name,
        },
    )
    def analyze(self, seed: EventSeed) -> PreliminaryResult:
        payload: PreliminaryRequestPayload = {
            "model": self.model_name,
            "messages": self.prompt_builder.build_preliminary_messages(seed),
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        content = _extract_chat_message_content(response)
        data = json.loads(content) if isinstance(content, str) else content
        return PreliminaryResult.model_validate(data)


class SglangVlmJudgeClient:
    """OpenAI-compatible evidence judge client for SGLang/vLLM style servers."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        timeout_ms: int = 10000,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        requester: Requester | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout_ms = timeout_ms
        self.temperature = temperature
        self.max_tokens = max_tokens
        if prompt_builder is None:
            raise ValueError("SglangVlmJudgeClient requires an explicit prompt_builder")
        self.requester = requester or (
            lambda url, headers, payload: _default_requester(
                url,
                headers,
                payload,
                timeout_ms=self.timeout_ms,
            )
        )
        self.prompt_builder = prompt_builder

    @log_external_call(
        "vlm_judge",
        field_extractor=lambda self, **kwargs: {
            "event_id": kwargs.get("event_id"),
            "endpoint_host": urlparse(self.endpoint).netloc,
            "model_name": self.model_name,
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
        del event_id, segmentation_status, preliminary
        payload: PreliminaryRequestPayload = {
            "model": self.model_name,
            "messages": self.prompt_builder.build_judge_messages(
                category_code=category_code,
                overlay_image=overlay_image,
                mask_labels=mask_labels or [],
                relation_hint=relation_hint,
                evidence_basis_summary=evidence_basis_summary,
            ),
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        content = _extract_chat_message_content(response)
        data = json.loads(content) if isinstance(content, str) else content
        return EvidenceJudgeResult.model_validate(data)


class Sam3FastApiClient:
    """FastAPI-style SAM3 client."""

    def __init__(
        self,
        *,
        endpoint: str,
        timeout_ms: int = 10000,
        requester: Requester | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_ms = timeout_ms
        self.requester = requester or (
            lambda url, headers, payload: _default_requester(
                url,
                headers,
                payload,
                timeout_ms=self.timeout_ms,
            )
        )

    @log_external_call(
        "sam3",
        field_extractor=lambda self, image_uri, targets: {
            "image_uri_scheme": image_uri.split("://", 1)[0] if "://" in image_uri else "local",
            "target_count": len(targets),
            "endpoint_host": urlparse(self.endpoint).netloc,
        },
    )
    def segment(self, image_uri: str, targets: list[str]) -> SegmentationResult:
        payload: Sam3RequestPayload = {
            "image_uri": image_uri,
            "targets": targets,
        }
        response = self.requester(self.endpoint, {"Content-Type": "application/json"}, payload)
        return SegmentationResult.model_validate(response)
