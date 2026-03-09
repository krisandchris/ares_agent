from __future__ import annotations

from ares_agent.domain.events import EventSeed
from ares_agent.services.feedback import PreliminaryEventFeedback, RefinedEventFeedback
from ares_agent.workflows.inspection_event_workflow import (
    EvidenceJudgeResult,
    PreliminaryResult,
    SegmentationResult,
    build_inspection_event_workflow,
)


class FakePreliminaryClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def analyze(self, seed: EventSeed) -> PreliminaryResult:
        self.calls.append(f"preliminary:{seed.frame_id}")
        return PreliminaryResult(
            suspected_categories=["road_occupying_vendor"],
            risk_level="high",
            prelim_confidence=0.91,
            need_retake=False,
            open_risk_hints=[],
            evidence_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
        )


class FakeSegmentationClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def segment(self, event_id: str, targets: list[str]) -> SegmentationResult:
        self.calls.append(f"segmentation:{event_id}:{','.join(targets)}")
        return SegmentationResult(
            mask_uri="s3://bucket/mask.png",
            crop_image_uris=["s3://bucket/crop-1.png"],
            overlay_image_uris=["s3://bucket/overlay-1.png"],
            evidence_basis_summary="stall overlaps sidewalk outside storefront boundary",
        )


class FakeJudgeClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def judge(
        self,
        *,
        event_id: str,
        category_code: str,
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> EvidenceJudgeResult:
        assert preliminary.suspected_categories == [category_code]
        self.calls.append(f"judge:{event_id}:{category_code}")
        return EvidenceJudgeResult(
            final_category=category_code,
            final_confidence=0.96,
            evidence_basis_match=True,
            violation_relation_confirmed=True,
            exception_excluded=True,
            archive_readiness=True,
            review_required=False,
            rejection_reason=None,
            violation_relation_summary=evidence_basis_summary,
        )


class FakeSinkPlugin:
    def __init__(self, calls: list[object]) -> None:
        self.calls = calls

    def send(self, event_payload: object, runtime_config: object) -> dict[str, object]:
        self.calls.append(event_payload)
        return {"success": True, "runtime_config": runtime_config}


def test_inspection_workflow_runs_two_callbacks_with_shared_event_id() -> None:
    order: list[str] = []
    callback_payloads: list[object] = []
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        frame_id="frame-001",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )
    workflow = build_inspection_event_workflow(
        preliminary_client=FakePreliminaryClient(order),
        segmentation_client=FakeSegmentationClient(order),
        evidence_judge_client=FakeJudgeClient(order),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config={"callback": {"plugin": "http_callback"}},
    )

    output = workflow.run(input=seed)

    assert order == [
        "preliminary:frame-001",
        f"segmentation:{callback_payloads[0].event_id}:stall,storefront_boundary,sidewalk_or_roadway",
        f"judge:{callback_payloads[0].event_id}:road_occupying_vendor",
    ]
    assert len(callback_payloads) == 2
    assert isinstance(callback_payloads[0], PreliminaryEventFeedback)
    assert isinstance(callback_payloads[1], RefinedEventFeedback)
    assert callback_payloads[0].event_id == callback_payloads[1].event_id
    assert output.content["event_id"] == callback_payloads[0].event_id
    assert output.content["stage"] == "refined"


def test_inspection_workflow_passes_same_event_id_into_refined_stage() -> None:
    callback_payloads: list[object] = []
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        frame_id="frame-001",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )
    workflow = build_inspection_event_workflow(
        preliminary_client=FakePreliminaryClient([]),
        segmentation_client=FakeSegmentationClient([]),
        evidence_judge_client=FakeJudgeClient([]),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config={"callback": {"plugin": "http_callback"}},
    )

    output = workflow.run(input=seed)

    refined = callback_payloads[1]
    assert isinstance(refined, RefinedEventFeedback)
    assert refined.event_id == callback_payloads[0].event_id
    assert output.content["event_id"] == refined.event_id
