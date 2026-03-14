from __future__ import annotations

from typing import Any, cast

from ares_agent.domain.json_types import JsonObject
from ares_agent.domain.payloads import StoredEventPayload
from ares_agent.model_clients.http_clients import PreliminaryRequestPayload, Sam3RequestPayload
from ares_agent.prompts.builders import MessageContentPart, PromptMessage
from ares_agent.workflows.inspection_event_workflow import PreliminaryCandidate, PreliminaryResult

RequesterPayload = PreliminaryRequestPayload | Sam3RequestPayload


def make_candidate(
    *,
    violation_category: str,
    confidence: float,
    evidence_reasoning: str,
    segmentation_targets: object,
    relation_hint: str,
    open_risk_type: str = "",
    sub_event_id: str | None = None,
) -> PreliminaryCandidate:
    return PreliminaryCandidate.model_validate(
        {
            "sub_event_id": sub_event_id,
            "violation_category": violation_category,
            "open_risk_type": open_risk_type,
            "confidence": confidence,
            "evidence_reasoning": evidence_reasoning,
            "segmentation_targets": segmentation_targets,
            "relation_hint": relation_hint,
        }
    )


def make_preliminary_result(
    *,
    environment_analysis: str,
    scene_elements: list[str],
    candidates: list[PreliminaryCandidate],
) -> PreliminaryResult:
    return PreliminaryResult(
        environment_analysis=environment_analysis,
        scene_elements=scene_elements,
        candidates=candidates,
    )


def message_parts(message: PromptMessage) -> list[MessageContentPart]:
    content = message["content"]
    assert isinstance(content, list)
    return content


def text_part(part: MessageContentPart) -> str:
    text = part.get("text")
    assert isinstance(text, str)
    return text


def image_url_part(part: MessageContentPart) -> str:
    image_url = part.get("image_url")
    assert image_url is not None
    return image_url["url"]


def stored_payload(output: object) -> StoredEventPayload:
    content = getattr(output, "content", None)
    assert isinstance(content, dict)
    return cast(StoredEventPayload, content)


def json_object(data: dict[str, Any]) -> JsonObject:
    return cast(JsonObject, data)
