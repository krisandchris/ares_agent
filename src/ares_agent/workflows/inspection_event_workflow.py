"""Agno workflow for one inspection event."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict, cast

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from ares_agent.domain.events import EventSeed, generate_event_id, generate_sub_event_id
from ares_agent.domain.evidence import EvidencePackage
from ares_agent.infra.log_decorators import log_stage
from ares_agent.infra.logging import get_logger
from ares_agent.services.feedback import build_preliminary_feedback, build_refined_feedback


class PreliminaryCandidate(BaseModel):
    """One candidate violation extracted from the first VLM pass."""

    sub_event_id: str | None = None
    violation_category: str
    open_risk_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_reasoning: str
    segmentation_targets: list[str]
    relation_hint: str

    @field_validator("open_risk_type", mode="before")
    @classmethod
    def normalize_open_risk_type(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    @field_validator("segmentation_targets", mode="before")
    @classmethod
    def normalize_segmentation_targets(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",")]
            return [item for item in parts if item]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("segmentation_targets must be a list or comma-separated string")

    @model_validator(mode="after")
    def validate_open_risk_type(self) -> "PreliminaryCandidate":
        if self.violation_category == "open_risk" and not self.open_risk_type:
            raise ValueError("open_risk_type must be non-empty when violation_category is open_risk")
        if self.violation_category != "open_risk" and self.open_risk_type != "":
            raise ValueError("open_risk_type must be empty unless violation_category is open_risk")
        return self


class PreliminaryResult(BaseModel):
    """Output from the first VLM pass."""

    environment_analysis: str
    scene_elements: list[str]
    candidates: list[PreliminaryCandidate] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_single_candidate_shape(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if "candidates" in value:
            return value
        if "violation_category" not in value:
            return value
        return {
            "environment_analysis": value.get("environment_analysis", ""),
            "scene_elements": value.get("scene_elements", []),
            "candidates": [
                {
                    "violation_category": value.get("violation_category"),
                    "open_risk_type": value.get("open_risk_type"),
                    "confidence": value.get("confidence"),
                    "evidence_reasoning": value.get("evidence_reasoning"),
                    "segmentation_targets": value.get("segmentation_targets"),
                    "relation_hint": value.get("relation_hint"),
                }
            ],
        }

    def _primary_candidate(self) -> PreliminaryCandidate | None:
        return self.candidates[0] if self.candidates else None

    @computed_field(return_type=str)
    @property
    def evidence_reasoning(self) -> str:
        candidate = self._primary_candidate()
        return candidate.evidence_reasoning if candidate is not None else ""

    @computed_field(return_type=list[str])
    @property
    def segmentation_targets(self) -> list[str]:
        candidate = self._primary_candidate()
        return list(candidate.segmentation_targets) if candidate is not None else []

    @computed_field(return_type=str)
    @property
    def relation_hint(self) -> str:
        candidate = self._primary_candidate()
        return candidate.relation_hint if candidate is not None else ""

    @computed_field(return_type=str)
    @property
    def violation_category(self) -> str:
        candidate = self._primary_candidate()
        return candidate.violation_category if candidate is not None else "none"

    @computed_field(return_type=str)
    @property
    def open_risk_type(self) -> str:
        candidate = self._primary_candidate()
        return candidate.open_risk_type if candidate is not None else ""

    @computed_field(return_type=float)
    @property
    def confidence(self) -> float:
        candidate = self._primary_candidate()
        return candidate.confidence if candidate is not None else 0.0


class SegmentationResult(BaseModel):
    """Evidence extraction output from SAM3."""

    overlay_image: str | None = None
    mask_labels: list[str] = Field(default_factory=list)
    relation_hint: str = ""
    segmentation_status: str = "ok"
    mask_uri: str | None = None
    crop_image_uris: list[str] = Field(default_factory=list)
    overlay_image_uris: list[str] = Field(default_factory=list)
    evidence_basis_summary: str


class EvidenceJudgeResult(BaseModel):
    """Rule-grounded evidence validation from the second VLM."""

    final_category: str
    final_confidence: float = Field(ge=0.0, le=1.0)
    evidence_basis_match: bool
    violation_relation_confirmed: bool
    exception_excluded: bool
    archive_readiness: bool
    review_required: bool
    rejection_reason: str | None = None
    violation_relation_summary: str | None = None


class PreliminaryClient(Protocol):
    """Client for the synchronous VLM pass."""

    def analyze(self, seed: EventSeed) -> PreliminaryResult:
        """Perform the initial classification pass."""
        ...


class SegmentationClient(Protocol):
    """Client for evidence segmentation."""

    def segment(self, image_uri: str, targets: list[str]) -> SegmentationResult:
        """Extract evidence material for the event."""
        ...


class EvidenceJudgeClient(Protocol):
    """Client for post-segmentation evidence judgment."""

    def judge(
        self,
        *,
        event_id: str,
        category_code: str,
        overlay_image: str | None = None,
        mask_labels: list[str] | None = None,
        relation_hint: str = "",
        segmentation_status: str = "ok",
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> EvidenceJudgeResult:
        """Judge whether the evidence supports the candidate category."""
        ...


class SinkPlugin(Protocol):
    """Callback adapter for the backend management service."""

    def send(self, event_payload: object, runtime_config: object) -> object:
        """Deliver a workflow result payload."""
        ...


@dataclass
class WorkflowStageError(RuntimeError):
    """Wrap a step failure so the API layer can recover structured details."""

    cause_type: str
    message: str

    def __str__(self) -> str:
        return f"{self.cause_type}: {self.message}"


class PreliminarySubEventContent(TypedDict):
    sub_event_id: str
    stage: str
    preliminary_candidate: dict[str, Any]
    preliminary_feedback: dict[str, Any]


class SegmentedSubEventContent(PreliminarySubEventContent):
    segmentation: dict[str, Any]


class FailedSubEventContent(SegmentedSubEventContent):
    failed_step: str
    error_type: str
    error_message: str


class RefinedSubEventContent(SegmentedSubEventContent):
    refined_feedback: dict[str, Any]
    evidence_package: dict[str, Any]
    judgment: dict[str, Any]


SubEventResultContent = FailedSubEventContent | RefinedSubEventContent


class PreliminaryStepContent(TypedDict):
    event_id: str
    stage: str
    frame_seed: dict[str, Any]
    preliminary: dict[str, Any]
    preliminary_feedback: dict[str, Any]
    sub_events: list[PreliminarySubEventContent]


class SegmentationStepContent(TypedDict):
    event_id: str
    stage: str
    frame_seed: dict[str, Any]
    preliminary: dict[str, Any]
    preliminary_feedback: dict[str, Any]
    sub_events: list[SegmentedSubEventContent]


def _wrap_stage_error(exc: Exception) -> WorkflowStageError:
    if isinstance(exc, WorkflowStageError):
        return exc
    return WorkflowStageError(cause_type=exc.__class__.__name__, message=str(exc))


def _dump_preliminary_for_response(preliminary: PreliminaryResult) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        preliminary.model_dump(
            exclude={
                "evidence_reasoning",
                "segmentation_targets",
                "relation_hint",
                "violation_category",
                "open_risk_type",
                "confidence",
            }
        ),
    )


def _build_sub_events_summary(sub_events: list[SubEventResultContent]) -> dict[str, int]:
    candidate_count = len(sub_events)
    refined_count = sum(1 for item in sub_events if item["stage"] == "refined")
    failed_count = sum(1 for item in sub_events if item["stage"] == "failed")
    return {
        "candidate_count": candidate_count,
        "refined_count": refined_count,
        "failed_count": failed_count,
    }


def _require_step_content(content: object, step_name: str) -> dict[str, Any]:
    if not isinstance(content, dict):
        raise WorkflowStageError(
            cause_type="TypeError",
            message=f"{step_name} step content must be a dictionary",
        )
    return cast(dict[str, Any], content)


def _ensure_callback_success(stage_name: str, callback_result: object) -> None:
    success = getattr(callback_result, "success", True)
    if success:
        return
    status_code = getattr(callback_result, "status_code", "unknown")
    error_message = getattr(callback_result, "error_message", None)
    suffix = f": {error_message}" if error_message else ""
    raise WorkflowStageError(
        cause_type="RuntimeError",
        message=f"{stage_name} callback failed with status {status_code}{suffix}",
    )


def _should_send_callback(runtime_config: object, stage_name: str) -> bool:
    callback_config = runtime_config if isinstance(runtime_config, dict) else {}
    callback_config = callback_config.get("callback", {}) if isinstance(callback_config, dict) else {}
    if not isinstance(callback_config, dict):
        return True
    if stage_name == "preliminary":
        return bool(callback_config.get("send_preliminary", True))
    if stage_name == "refined":
        return bool(callback_config.get("send_refined", True))
    return True


def _should_block_callback_failure(runtime_config: object, stage_name: str) -> bool:
    callback_config = runtime_config if isinstance(runtime_config, dict) else {}
    callback_config = callback_config.get("callback", {}) if isinstance(callback_config, dict) else {}
    if not isinstance(callback_config, dict):
        return True
    if stage_name == "preliminary":
        return bool(callback_config.get("block_on_preliminary_failure", True))
    return True


def _preliminary_step_factory(
    *,
    preliminary_client: PreliminaryClient,
    sink_plugin: SinkPlugin,
    runtime_config: object,
    async_enqueued: bool,
) -> Step:
    @log_stage(
        "preliminary",
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
            preliminary = preliminary_client.analyze(seed)
            candidates = preliminary.candidates
            if not candidates:
                candidates = [
                    PreliminaryCandidate(
                        violation_category="none",
                        open_risk_type="",
                        confidence=0.0,
                        evidence_reasoning="no candidate produced",
                        segmentation_targets=[],
                        relation_hint="",
                    )
                ]
            sub_events: list[PreliminarySubEventContent] = []
            normalized_candidates: list[PreliminaryCandidate] = []
            for candidate_index, candidate in enumerate(candidates):
                sub_event_id = candidate.sub_event_id or generate_sub_event_id(
                    event_id=event_id,
                    violation_category=candidate.violation_category,
                    relation_hint=candidate.relation_hint,
                    candidate_index=candidate_index,
                )
                normalized_candidate = candidate.model_copy(update={"sub_event_id": sub_event_id})
                normalized_candidates.append(normalized_candidate)
                feedback = build_preliminary_feedback(
                    event_id=event_id,
                    sub_event_id=sub_event_id,
                    camera_id=seed.camera_id,
                    location=seed.location,
                    violation_category=normalized_candidate.violation_category,
                    open_risk_type=normalized_candidate.open_risk_type,
                    confidence=normalized_candidate.confidence,
                    async_enqueued=async_enqueued,
                )
                if _should_send_callback(runtime_config, "preliminary"):
                    try:
                        callback_result = sink_plugin.send(feedback, runtime_config)
                        _ensure_callback_success("preliminary", callback_result)
                    except Exception as exc:
                        if _should_block_callback_failure(runtime_config, "preliminary"):
                            raise
                        get_logger(__name__).warning(
                            "callback.ignored_failure",
                            stage="preliminary",
                            event_id=event_id,
                            sub_event_id=sub_event_id,
                            error_type=exc.__class__.__name__,
                            error_message=str(exc),
                        )
                sub_events.append(
                    {
                        "sub_event_id": sub_event_id,
                        "stage": "preliminary",
                        "preliminary_candidate": normalized_candidate.model_dump(),
                        "preliminary_feedback": feedback.model_dump(exclude_none=True),
                    }
                )
            preliminary = preliminary.model_copy(update={"candidates": normalized_candidates})
            feedback = sub_events[0]["preliminary_feedback"]
            if not async_enqueued and not _should_send_callback(runtime_config, "preliminary"):
                return StepOutput(
                    content={
                        "event_id": event_id,
                        "stage": "preliminary",
                        "frame_seed": seed.model_dump(),
                        "preliminary": _dump_preliminary_for_response(preliminary),
                    }
                )
            return StepOutput(
                content={
                    "event_id": event_id,
                    "stage": "preliminary",
                    "frame_seed": seed.model_dump(),
                    "preliminary": preliminary.model_dump(),
                    "preliminary_feedback": feedback,
                    "sub_events": sub_events,
                }
            )
        except Exception as exc:
            raise _wrap_stage_error(exc) from exc

    return Step(name="preliminary", executor=run, max_retries=0)


def _segmentation_step_factory(*, segmentation_client: SegmentationClient) -> Step:
    @log_stage(
        "segmentation",
        field_extractor=lambda step_input: {
            "event_id": cast(
                dict[str, Any],
                step_input.get_step_content("preliminary"),
            ).get("event_id"),
        },
    )
    def run(step_input: StepInput) -> StepOutput:
        try:
            preliminary_content = cast(
                PreliminaryStepContent,
                _require_step_content(step_input.get_step_content("preliminary"), "preliminary"),
            )
            frame_seed = cast(dict[str, Any], preliminary_content["frame_seed"])
            image_uri = cast(str, frame_seed["image_uri"])
            sub_events: list[SegmentedSubEventContent] = []
            for sub_event in preliminary_content["sub_events"]:
                candidate = cast(dict[str, Any], sub_event["preliminary_candidate"])
                segmentation_targets = cast(list[str], candidate["segmentation_targets"])
                segmentation = segmentation_client.segment(image_uri, segmentation_targets)
                sub_events.append(
                    {
                        **sub_event,
                        "segmentation": segmentation.model_dump(),
                    }
                )
            return StepOutput(
                content={
                    **preliminary_content,
                    "sub_events": sub_events,
                }
            )
        except Exception as exc:
            raise _wrap_stage_error(exc) from exc

    return Step(name="segmentation", executor=run, max_retries=0)


def _evidence_judge_step_factory(
    *,
    evidence_judge_client: EvidenceJudgeClient,
    sink_plugin: SinkPlugin,
    runtime_config: object,
) -> Step:
    @log_stage(
        "evidence_judge",
        field_extractor=lambda step_input: {
            "event_id": cast(
                dict[str, Any],
                step_input.get_step_content("segmentation"),
            ).get("event_id"),
        },
    )
    def run(step_input: StepInput) -> StepOutput:
        try:
            segmentation_content = cast(
                SegmentationStepContent,
                _require_step_content(step_input.get_step_content("segmentation"), "segmentation"),
            )
            event_id = segmentation_content["event_id"]
            preliminary = cast(dict[str, Any], segmentation_content["preliminary"])
            frame_seed = cast(dict[str, Any], segmentation_content["frame_seed"])
            finalized_sub_events: list[SubEventResultContent] = []
            all_failed = True
            first_failure: FailedSubEventContent | None = None
            for sub_event in segmentation_content["sub_events"]:
                candidate = cast(dict[str, Any], sub_event["preliminary_candidate"])
                segmentation = cast(dict[str, Any], sub_event["segmentation"])
                segmentation_status = cast(str, segmentation.get("segmentation_status", "ok"))
                sub_event_id = cast(str, sub_event["sub_event_id"])
                if segmentation_status == "failed":
                    failure: FailedSubEventContent = {
                        **sub_event,
                        "stage": "failed",
                        "failed_step": "segmentation",
                        "error_type": "SegmentationFailed",
                        "error_message": cast(str, segmentation["evidence_basis_summary"]),
                    }
                    finalized_sub_events.append(failure)
                    if first_failure is None:
                        first_failure = failure
                    continue
                judgment = evidence_judge_client.judge(
                    event_id=event_id,
                    category_code=cast(str, candidate["violation_category"]),
                    overlay_image=segmentation.get("overlay_image")
                    or (segmentation.get("overlay_image_uris") or [None])[0],
                    mask_labels=segmentation.get("mask_labels") or [],
                    relation_hint=segmentation.get("relation_hint") or candidate.get("relation_hint", ""),
                    segmentation_status=segmentation_status,
                    evidence_basis_summary=segmentation["evidence_basis_summary"],
                    preliminary=PreliminaryResult.model_validate(
                        {
                            "environment_analysis": preliminary["environment_analysis"],
                            "scene_elements": preliminary["scene_elements"],
                            "candidates": [candidate],
                        }
                    ),
                )
                refined_feedback = build_refined_feedback(
                    event_id=event_id,
                    sub_event_id=sub_event_id,
                    camera_id=cast(str, frame_seed["camera_id"]),
                    location=cast(str, frame_seed["location"]),
                    final_category=judgment.final_category,
                    final_confidence=judgment.final_confidence,
                    archive_readiness=judgment.archive_readiness,
                    review_required=judgment.review_required,
                    event_version=2,
                )
                if _should_send_callback(runtime_config, "refined"):
                    callback_result = sink_plugin.send(refined_feedback, runtime_config)
                    _ensure_callback_success("refined", callback_result)
                evidence_package = EvidencePackage(
                    event_id=event_id,
                    crop_image_uris=segmentation["crop_image_uris"],
                    overlay_image_uris=segmentation["overlay_image_uris"],
                    mask_uri=segmentation["mask_uri"],
                    evidence_basis_summary=segmentation["evidence_basis_summary"],
                    archive_readiness=judgment.archive_readiness,
                    rejection_reason=judgment.rejection_reason,
                )
                finalized: RefinedSubEventContent = {
                    **sub_event,
                    "stage": "refined",
                    "refined_feedback": refined_feedback.model_dump(exclude_none=True),
                    "evidence_package": evidence_package.model_dump(),
                    "judgment": judgment.model_dump(),
                }
                finalized_sub_events.append(finalized)
                all_failed = False
            if all_failed and first_failure is not None:
                return StepOutput(
                    content={
                        "event_id": event_id,
                        "stage": "failed",
                        "failed_step": first_failure["failed_step"],
                        "error_type": first_failure["error_type"],
                        "error_message": first_failure["error_message"],
                        "preliminary": preliminary,
                        "frame_seed": frame_seed,
                        "summary": _build_sub_events_summary(finalized_sub_events),
                        "sub_events": finalized_sub_events,
                    }
                )
            return StepOutput(
                content={
                    "event_id": event_id,
                    "stage": "refined",
                    "preliminary": preliminary,
                    "frame_seed": frame_seed,
                    "summary": _build_sub_events_summary(finalized_sub_events),
                    "sub_events": finalized_sub_events,
                }
            )
        except Exception as exc:
            raise _wrap_stage_error(exc) from exc

    return Step(name="evidence_judge", executor=run, max_retries=0)


def build_inspection_event_workflow(
    *,
    preliminary_client: PreliminaryClient,
    segmentation_client: SegmentationClient,
    evidence_judge_client: EvidenceJudgeClient,
    sink_plugin: SinkPlugin,
    runtime_config: object,
) -> Workflow:
    """Create the Agno workflow for one inspection event."""
    return Workflow(
        name="Inspection Event Workflow",
        input_schema=EventSeed,
        telemetry=False,
        steps=[
            _preliminary_step_factory(
                preliminary_client=preliminary_client,
                sink_plugin=sink_plugin,
                runtime_config=runtime_config,
                async_enqueued=True,
            ),
            _segmentation_step_factory(segmentation_client=segmentation_client),
            _evidence_judge_step_factory(
                evidence_judge_client=evidence_judge_client,
                sink_plugin=sink_plugin,
                runtime_config=runtime_config,
            ),
        ],
    )


def build_preliminary_only_workflow(
    *,
    preliminary_client: PreliminaryClient,
    sink_plugin: SinkPlugin,
    runtime_config: object,
) -> Workflow:
    """Create a single-node VLM-1-only workflow."""
    return Workflow(
        name="Inspection Preliminary Workflow",
        input_schema=EventSeed,
        telemetry=False,
        steps=[
            _preliminary_step_factory(
                preliminary_client=preliminary_client,
                sink_plugin=sink_plugin,
                runtime_config=runtime_config,
                async_enqueued=False,
            )
        ],
    )
