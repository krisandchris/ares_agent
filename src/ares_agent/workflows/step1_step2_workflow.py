"""Step1 -> Step2 workflow (no SAM3), with result gate for category filtering.

Data flow:
  Step1 VLM → Stage1Output (validated) → passed raw to Step2
  Step2 VLM → Stage2Output (validated) → result gate → callback
"""

from __future__ import annotations

import json
from typing import Any, Callable, Protocol, cast

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from ares_agent.domain.events import EventSeed, generate_event_id
from ares_agent.domain.stage1_output import Stage1Output
from ares_agent.domain.stage2_output import Stage2Output
from ares_agent.infra.log_decorators import log_stage
from ares_agent.infra.logging import get_logger
from ares_agent.prompts.data_engine_prompts import (
    DataEngineStep1PromptBuilder,
    DataEngineStep2PromptBuilder,
)
from ares_agent.services.feedback import RefinedEventFeedback, build_refined_feedback
from ares_agent.services.image_uri_resolver import ImageUriResolver, resolve_image_uri
from ares_agent.services.result_gate import ResultGate
from ares_agent.workflows.inspection_event_workflow import (
    SinkPlugin,
    WorkflowStageError,
    _ensure_callback_success,
    _should_send_callback,
    _wrap_stage_error,
)


Requester = Callable[[str, dict[str, str], dict], dict]


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.index("\n")
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-len("```")]
    return text.strip()


def _call_vlm(
    *,
    endpoint: str,
    model_name: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int | None,
    requester: Requester,
) -> str:
    """Call VLM and return the raw assistant content text."""
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    response = requester(endpoint, {"Content-Type": "application/json"}, payload)
    content = response["choices"][0]["message"]["content"]
    return _strip_json_fence(content) if isinstance(content, str) else json.dumps(content)


def _step1_factory(
    *,
    step1_prompt_builder: DataEngineStep1PromptBuilder,
    endpoint: str,
    model_name: str,
    temperature: float,
    max_tokens: int | None,
    requester: Requester,
    sink_plugin: SinkPlugin,
    runtime_config: object,
    image_uri_resolver: ImageUriResolver | None = None,
) -> Step:
    """Step1: scene parsing. Calls VLM, validates Stage1Output, passes raw to step2."""

    @log_stage(
        "step1_scene_parsing",
        field_extractor=lambda step_input: {
            "event_id": generate_event_id(EventSeed.model_validate(step_input.input)),
            "camera_id": EventSeed.model_validate(step_input.input).camera_id,
            "location": EventSeed.model_validate(step_input.input).location,
        },
    )
    def run(step_input: StepInput) -> StepOutput:
        try:
            seed = EventSeed.model_validate(step_input.input)
            event_id = generate_event_id(seed)
            image_uri = resolve_image_uri(seed.image_uri, resolver=image_uri_resolver)
            if image_uri != seed.image_uri:
                get_logger(__name__).info(
                    "step1.image_uri_resolved",
                    event_id=event_id,
                    original_uri=seed.image_uri[:80],
                )

            messages = step1_prompt_builder.build_messages(
                image_uri=image_uri,
                image_hint=seed.camera_id,
            )
            raw_text = _call_vlm(
                endpoint=endpoint,
                model_name=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                requester=requester,
            )
            stage1 = Stage1Output.model_validate_json(raw_text)
            get_logger(__name__).info(
                "step1.parsed",
                event_id=event_id,
                relation_count=len(stage1.key_relations),
                anchor_count=len(stage1.key_anchors),
            )

            return StepOutput(content={
                "event_id": event_id,
                "stage": "step1",
                "frame_seed": seed.model_dump(),
                "stage1_output": stage1.model_dump(),
            })
        except Exception as exc:
            raise _wrap_stage_error(exc) from exc

    return Step(name="step1_scene_parsing", executor=run, max_retries=0)


def _step2_evidence_judge_factory(
    *,
    step2_prompt_builder: DataEngineStep2PromptBuilder,
    endpoint: str,
    model_name: str,
    temperature: float,
    max_tokens: int | None,
    requester: Requester,
    result_gate: ResultGate,
    sink_plugin: SinkPlugin,
    runtime_config: object,
    image_uri_resolver: ImageUriResolver | None = None,
) -> Step:
    """Step2: violation judgment. Uses Stage1Output directly, applies result gate."""

    @log_stage(
        "step2_evidence_judge",
        field_extractor=lambda step_input: {
            "event_id": cast(
                dict[str, Any],
                step_input.get_step_content("step1_scene_parsing"),
            ).get("event_id"),
        },
    )
    def run(step_input: StepInput) -> StepOutput:
        try:
            step1_content = cast(
                dict[str, Any],
                step_input.get_step_content("step1_scene_parsing"),
            )
            event_id = step1_content["event_id"]
            frame_seed = cast(dict[str, Any], step1_content["frame_seed"])
            raw_image_uri = cast(str, frame_seed["image_uri"])
            image_uri = resolve_image_uri(raw_image_uri, resolver=image_uri_resolver)
            if image_uri != raw_image_uri:
                get_logger(__name__).info(
                    "step2.image_uri_resolved",
                    event_id=event_id,
                    original_uri=raw_image_uri[:80],
                )
            location = cast(str, frame_seed["location"])
            camera_id = cast(str, frame_seed["camera_id"])

            # Use Stage1Output directly — no lossy conversion
            stage1_dict = cast(dict[str, Any], step1_content["stage1_output"])
            stage1_json = json.dumps(stage1_dict, ensure_ascii=False)

            messages = step2_prompt_builder.build_messages(
                image_uri=image_uri,
                stage1_json=stage1_json,
                sample_id=event_id,
            )
            raw_text = _call_vlm(
                endpoint=endpoint,
                model_name=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                requester=requester,
            )
            stage2 = Stage2Output.model_validate_json(raw_text)
            get_logger(__name__).info(
                "step2.parsed",
                event_id=event_id,
                candidate_count=len(stage2.candidates),
                verification_count=len(stage2.fact_verifications),
            )

            # Result gate: filter candidates by location+camera allowed categories
            filtered_candidates = result_gate.filter(location, camera_id, stage2.candidates)
            gate_filtered = len(filtered_candidates) < len(stage2.candidates)
            if gate_filtered:
                get_logger(__name__).info(
                    "step2.result_gate.filtered",
                    event_id=event_id,
                    location=location,
                    camera_id=camera_id,
                    original_count=len(stage2.candidates),
                    filtered_count=len(filtered_candidates),
                )

            # Callback: extract category/confidence directly from Stage2 candidate
            violation_candidates = [
                c for c in filtered_candidates
                if "no_violation" not in c.violation_category
            ]
            if violation_candidates:
                top = violation_candidates[0]
                final_category = top.violation_category[0]
                final_confidence = top.confidence
                archive_readiness = final_confidence >= 0.7
                review_required = final_confidence < 0.5
            else:
                final_category = "none"
                final_confidence = 0.0
                archive_readiness = False
                review_required = False

            refined_feedback = build_refined_feedback(
                event_id=event_id,
                sub_event_id=event_id,
                camera_id=camera_id,
                location=location,
                final_category=final_category,
                final_confidence=final_confidence,
                archive_readiness=archive_readiness,
                review_required=review_required,
                event_version=2,
            )
            if _should_send_callback(runtime_config, "refined"):
                callback_result = sink_plugin.send(refined_feedback, runtime_config)
                _ensure_callback_success("refined", callback_result)

            # Output: raw Stage1 + Stage2 + event metadata, no intermediate mapping
            stage2_dict = stage2.model_dump()
            if gate_filtered:
                stage2_dict["candidates"] = [c.model_dump() for c in filtered_candidates]

            # Top-level candidates for downstream compatibility
            candidates = [
                c.model_dump() for c in filtered_candidates
                if "no_violation" not in c.violation_category
            ]

            return StepOutput(content={
                "event_id": event_id,
                "stage": "refined",
                "frame_seed": frame_seed,
                "stage1_output": stage1_dict,
                "stage2_output": stage2_dict,
                "candidates": candidates,
                "event_version": 2,
            })
        except Exception as exc:
            raise _wrap_stage_error(exc) from exc

    return Step(name="step2_evidence_judge", executor=run, max_retries=0)


def build_step1_step2_workflow(
    *,
    step1_prompt_builder: DataEngineStep1PromptBuilder,
    step2_prompt_builder: DataEngineStep2PromptBuilder,
    endpoint: str,
    model_name: str,
    step1_temperature: float,
    step2_temperature: float,
    max_tokens: int | None,
    step1_requester: Requester,
    step2_requester: Requester,
    result_gate: ResultGate,
    sink_plugin: SinkPlugin,
    runtime_config: object,
    image_uri_resolver: ImageUriResolver | None = None,
) -> Workflow:
    """Create Step1 -> Step2 workflow (no SAM3 segmentation).

    Step1 VLM → Stage1Output (validated, passed raw)
    Step2 VLM → Stage2Output (validated) → result gate → callback
    """
    return Workflow(
        name="Inspection Step1-Step2 Workflow",
        input_schema=EventSeed,
        telemetry=False,
        steps=[
            _step1_factory(
                step1_prompt_builder=step1_prompt_builder,
                endpoint=endpoint,
                model_name=model_name,
                temperature=step1_temperature,
                max_tokens=max_tokens,
                requester=step1_requester,
                sink_plugin=sink_plugin,
                runtime_config=runtime_config,
                image_uri_resolver=image_uri_resolver,
            ),
            _step2_evidence_judge_factory(
                step2_prompt_builder=step2_prompt_builder,
                endpoint=endpoint,
                model_name=model_name,
                temperature=step2_temperature,
                max_tokens=max_tokens,
                requester=step2_requester,
                result_gate=result_gate,
                sink_plugin=sink_plugin,
                runtime_config=runtime_config,
                image_uri_resolver=image_uri_resolver,
            ),
        ],
    )
