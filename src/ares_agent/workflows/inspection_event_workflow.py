"""Agno workflow for one inspection event."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel, Field, model_validator

from ares_agent.domain.events import EventSeed, generate_event_id
from ares_agent.domain.evidence import EvidencePackage
from ares_agent.services.feedback import build_preliminary_feedback, build_refined_feedback


class PreliminaryResult(BaseModel):
    """Output from the first VLM pass."""

    environment_analysis: str
    scene_elements: list[str]
    evidence_reasoning: str
    segmentation_targets: list[str]
    relation_hint: str
    violation_category: str
    open_risk_type: str
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_open_risk_type(self) -> "PreliminaryResult":
        if self.violation_category == "open_risk" and not self.open_risk_type:
            raise ValueError("open_risk_type must be non-empty when violation_category is open_risk")
        if self.violation_category != "open_risk" and self.open_risk_type != "":
            raise ValueError("open_risk_type must be empty unless violation_category is open_risk")
        return self


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


class SegmentationClient(Protocol):
    """Client for evidence segmentation."""

    def segment(self, image_uri: str, targets: list[str]) -> SegmentationResult:
        """Extract evidence material for the event."""


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


class SinkPlugin(Protocol):
    """Callback adapter for the backend management service."""

    def send(self, event_payload: object, runtime_config: object) -> object:
        """Deliver a workflow result payload."""


@dataclass
class WorkflowStageError(RuntimeError):
    """Wrap a step failure so the API layer can recover structured details."""

    cause_type: str
    message: str

    def __str__(self) -> str:
        return f"{self.cause_type}: {self.message}"


def _wrap_stage_error(exc: Exception) -> WorkflowStageError:
    if isinstance(exc, WorkflowStageError):
        return exc
    return WorkflowStageError(cause_type=exc.__class__.__name__, message=str(exc))


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


def _preliminary_step_factory(
    *,
    preliminary_client: PreliminaryClient,
    sink_plugin: SinkPlugin,
    runtime_config: object,
) -> Step:
    def run(step_input: StepInput) -> StepOutput:
        try:
            seed = EventSeed.model_validate(step_input.input)
            event_id = generate_event_id(seed)
            preliminary = preliminary_client.analyze(seed)
            feedback = build_preliminary_feedback(
                event_id=event_id,
                frame_id=seed.frame_id,
                violation_category=preliminary.violation_category,
                open_risk_type=preliminary.open_risk_type,
                confidence=preliminary.confidence,
                async_enqueued=True,
            )
            callback_result = sink_plugin.send(feedback, runtime_config)
            _ensure_callback_success("preliminary", callback_result)
            return StepOutput(
                content={
                    "event_id": event_id,
                    "frame_seed": seed.model_dump(),
                    "preliminary": preliminary.model_dump(),
                    "preliminary_feedback": feedback.model_dump(),
                }
            )
        except Exception as exc:
            raise _wrap_stage_error(exc) from exc

    return Step(name="preliminary", executor=run, max_retries=0)


def _segmentation_step_factory(*, segmentation_client: SegmentationClient) -> Step:
    def run(step_input: StepInput) -> StepOutput:
        try:
            preliminary_content = step_input.get_step_content("preliminary") or {}
            image_uri = preliminary_content["frame_seed"]["image_uri"]
            preliminary = preliminary_content["preliminary"]
            segmentation_targets = preliminary["segmentation_targets"]
            segmentation = segmentation_client.segment(image_uri, segmentation_targets)
            return StepOutput(
                content={
                    **preliminary_content,
                    "segmentation": segmentation.model_dump(),
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
    def run(step_input: StepInput) -> StepOutput:
        try:
            segmentation_content = step_input.get_step_content("segmentation") or {}
            event_id = segmentation_content["event_id"]
            preliminary = segmentation_content["preliminary"]
            segmentation = segmentation_content["segmentation"]
            segmentation_status = segmentation.get("segmentation_status", "ok")
            if segmentation_status == "failed":
                return StepOutput(
                    content={
                        "event_id": event_id,
                        "stage": "failed",
                        "failed_step": "segmentation",
                        "error_type": "SegmentationFailed",
                        "error_message": segmentation["evidence_basis_summary"],
                        "preliminary_feedback": segmentation_content["preliminary_feedback"],
                    }
                )
            final_category = preliminary["violation_category"]
            judgment = evidence_judge_client.judge(
                event_id=event_id,
                category_code=final_category,
                overlay_image=segmentation.get("overlay_image")
                or (segmentation.get("overlay_image_uris") or [None])[0],
                mask_labels=segmentation.get("mask_labels") or [],
                relation_hint=segmentation.get("relation_hint") or preliminary.get("relation_hint", ""),
                segmentation_status=segmentation_status,
                evidence_basis_summary=segmentation["evidence_basis_summary"],
                preliminary=PreliminaryResult.model_validate(preliminary),
            )
            refined_feedback = build_refined_feedback(
                event_id=event_id,
                frame_id=segmentation_content["frame_seed"]["frame_id"],
                final_category=judgment.final_category,
                final_confidence=judgment.final_confidence,
                archive_readiness=judgment.archive_readiness,
                review_required=judgment.review_required,
                event_version=2,
            )
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
            return StepOutput(
                content={
                    "event_id": event_id,
                    "stage": "refined",
                    "preliminary_feedback": segmentation_content["preliminary_feedback"],
                    "refined_feedback": refined_feedback.model_dump(),
                    "evidence_package": evidence_package.model_dump(),
                    "judgment": judgment.model_dump(),
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
            ),
            _segmentation_step_factory(segmentation_client=segmentation_client),
            _evidence_judge_step_factory(
                evidence_judge_client=evidence_judge_client,
                sink_plugin=sink_plugin,
                runtime_config=runtime_config,
            ),
        ],
    )
