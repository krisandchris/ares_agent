from __future__ import annotations

from typing import Any, TypeVar, cast

from ares_agent.domain.events import EventSeed
from ares_agent.domain.payloads import StoredEventPayload
from ares_agent.services.feedback import PreliminaryEventFeedback, RefinedEventFeedback
from ares_agent.workflows.inspection_event_workflow import (
    EvidenceJudgeResult,
    PreliminaryCandidate,
    PreliminaryResult,
    SegmentationResult,
    build_inspection_event_workflow,
)

CallbackPayload = PreliminaryEventFeedback | RefinedEventFeedback


def _make_candidate(
    *,
    violation_category: str,
    open_risk_type: str = "",
    confidence: float,
    evidence_reasoning: str,
    segmentation_targets: list[str],
    relation_hint: str,
    sub_event_id: str | None = None,
) -> PreliminaryCandidate:
    return PreliminaryCandidate(
        sub_event_id=sub_event_id,
        violation_category=violation_category,
        open_risk_type=open_risk_type,
        confidence=confidence,
        evidence_reasoning=evidence_reasoning,
        segmentation_targets=segmentation_targets,
        relation_hint=relation_hint,
    )


def _make_result(*, candidates: list[PreliminaryCandidate]) -> PreliminaryResult:
    return PreliminaryResult(
        environment_analysis="street storefront scene with sidewalk occupation",
        scene_elements=["storefront", "stall", "sidewalk"],
        candidates=candidates,
    )


def _stored_payload(output: object) -> StoredEventPayload:
    content = getattr(output, "content", None)
    assert isinstance(content, dict)
    return cast(StoredEventPayload, content)


def _summary(payload: StoredEventPayload) -> dict[str, int]:
    summary = payload.get("summary")
    assert summary is not None
    return summary


def _sub_events(payload: StoredEventPayload) -> list[dict[str, Any]]:
    sub_events = payload.get("sub_events")
    assert sub_events is not None
    return cast(list[dict[str, Any]], sub_events)

FeedbackT = TypeVar("FeedbackT", PreliminaryEventFeedback, RefinedEventFeedback)


def _require_feedback(payload: CallbackPayload, expected_type: type[FeedbackT]) -> FeedbackT:
    assert isinstance(payload, expected_type)
    return payload


class FakePreliminaryClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def analyze(self, seed: EventSeed) -> PreliminaryResult:
        self.calls.append(f"preliminary:{seed.camera_id}:{seed.location}")
        return _make_result(
            candidates=[
                _make_candidate(
                    violation_category="road_occupying_vendor",
                    confidence=0.91,
                    evidence_reasoning="stall extends beyond storefront boundary into sidewalk",
                    segmentation_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
                    relation_hint="stall overlaps sidewalk outside storefront boundary",
                )
            ]
        )


class FakeSegmentationClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def segment(self, image_uri: str, targets: list[str]) -> SegmentationResult:
        self.calls.append(f"segmentation:{image_uri}:{','.join(targets)}")
        return SegmentationResult(
            overlay_image="s3://bucket/overlay-1.png",
            mask_labels=["stall", "storefront_boundary", "sidewalk_or_roadway"],
            relation_hint="stall overlaps sidewalk outside storefront boundary",
            segmentation_status="ok",
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
        overlay_image: str | None = None,
        mask_labels: list[str] | None = None,
        relation_hint: str = "",
        segmentation_status: str = "ok",
        evidence_basis_summary: str,
        preliminary: PreliminaryResult,
    ) -> EvidenceJudgeResult:
        assert category_code == "road_occupying_vendor"
        assert overlay_image == "s3://bucket/overlay-1.png"
        assert mask_labels == ["stall", "storefront_boundary", "sidewalk_or_roadway"]
        assert relation_hint == "stall overlaps sidewalk outside storefront boundary"
        assert segmentation_status == "ok"
        assert preliminary.violation_category == category_code
        assert preliminary.segmentation_targets == ["stall", "storefront_boundary", "sidewalk_or_roadway"]
        assert preliminary.relation_hint == relation_hint
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


class FailingSegmentationClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def segment(self, image_uri: str, targets: list[str]) -> SegmentationResult:
        self.calls.append(f"segmentation_failed:{image_uri}:{','.join(targets)}")
        return SegmentationResult(
            overlay_image=None,
            mask_labels=[],
            relation_hint="",
            segmentation_status="failed",
            mask_uri=None,
            crop_image_uris=[],
            overlay_image_uris=[],
            evidence_basis_summary="segmentation produced no usable evidence",
        )


class FakeSinkPlugin:
    def __init__(self, calls: list[CallbackPayload]) -> None:
        self.calls = calls

    def send(self, event_payload: object, runtime_config: object) -> dict[str, object]:
        assert isinstance(event_payload, (PreliminaryEventFeedback, RefinedEventFeedback))
        self.calls.append(event_payload)
        return {"success": True, "runtime_config": runtime_config}


def test_inspection_workflow_runs_two_callbacks_with_shared_event_id() -> None:
    order: list[str] = []
    callback_payloads: list[CallbackPayload] = []
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id="front",
        location="南山路",
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
    payload = _stored_payload(output)

    assert order == [
        "preliminary:front:南山路",
        "segmentation:s3://street/frame-001.jpg:stall,storefront_boundary,sidewalk_or_roadway",
        f"judge:{callback_payloads[0].event_id}:road_occupying_vendor",
    ]
    assert len(callback_payloads) == 2
    assert callback_payloads[0].event_id == callback_payloads[1].event_id
    assert payload["event_id"] == callback_payloads[0].event_id
    assert payload["stage"] == "refined"
    assert _summary(payload) == {"candidate_count": 1, "refined_count": 1, "failed_count": 0}
    assert _sub_events(payload)[0]["refined_feedback"]["final_category"] == "road_occupying_vendor"


def test_inspection_workflow_passes_same_event_id_into_refined_stage() -> None:
    callback_payloads: list[CallbackPayload] = []
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id="front",
        location="南山路",
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
    payload = _stored_payload(output)

    refined = callback_payloads[1]
    assert refined.event_id == callback_payloads[0].event_id
    assert payload["event_id"] == refined.event_id
    assert _sub_events(payload)[0]["refined_feedback"]["event_id"] == refined.event_id


def test_inspection_workflow_stops_before_judge_when_segmentation_failed() -> None:
    order: list[str] = []
    callback_payloads: list[CallbackPayload] = []
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )
    workflow = build_inspection_event_workflow(
        preliminary_client=FakePreliminaryClient(order),
        segmentation_client=FailingSegmentationClient(order),
        evidence_judge_client=FakeJudgeClient(order),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config={"callback": {"plugin": "http_callback"}},
    )

    output = workflow.run(input=seed)
    payload = _stored_payload(output)

    assert order == [
        "preliminary:front:南山路",
        "segmentation_failed:s3://street/frame-001.jpg:stall,storefront_boundary,sidewalk_or_roadway",
    ]
    assert len(callback_payloads) == 1
    assert payload["stage"] == "failed"
    assert payload.get("error_type") == "SegmentationFailed"
    assert payload.get("failed_step") == "segmentation"


def test_inspection_workflow_can_skip_refined_callback_via_runtime_config() -> None:
    callback_payloads: list[CallbackPayload] = []
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )
    workflow = build_inspection_event_workflow(
        preliminary_client=FakePreliminaryClient([]),
        segmentation_client=FakeSegmentationClient([]),
        evidence_judge_client=FakeJudgeClient([]),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": False}},
    )

    output = workflow.run(input=seed)
    payload = _stored_payload(output)

    assert payload["stage"] == "refined"
    assert len(callback_payloads) == 1
    assert isinstance(callback_payloads[0], PreliminaryEventFeedback)


def test_inspection_workflow_can_skip_all_callbacks_via_runtime_config() -> None:
    callback_payloads: list[CallbackPayload] = []
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )
    workflow = build_inspection_event_workflow(
        preliminary_client=FakePreliminaryClient([]),
        segmentation_client=FakeSegmentationClient([]),
        evidence_judge_client=FakeJudgeClient([]),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config={"callback": {"send_preliminary": False, "send_refined": False}},
    )

    output = workflow.run(input=seed)
    payload = _stored_payload(output)

    assert payload["stage"] == "refined"
    assert callback_payloads == []


def test_inspection_workflow_consumes_first_preliminary_candidate_when_multiple_candidates_exist() -> None:
    class MultiCandidatePreliminaryClient(FakePreliminaryClient):
        def analyze(self, seed: EventSeed) -> PreliminaryResult:
            self.calls.append(f"preliminary:{seed.camera_id}:{seed.location}")
            return PreliminaryResult(
                environment_analysis="street storefront scene with two issues",
                scene_elements=["storefront", "stall", "staff", "sidewalk"],
                candidates=[
                    _make_candidate(
                        sub_event_id="sub_evt_vendor",
                        violation_category="road_occupying_vendor",
                        confidence=0.91,
                        evidence_reasoning="stall extends into sidewalk",
                        segmentation_targets=["stall", "storefront_boundary", "sidewalk_or_roadway"],
                        relation_hint="stall overlaps sidewalk outside storefront boundary",
                    ),
                    _make_candidate(
                        sub_event_id="sub_evt_mask",
                        violation_category="staff_not_wear_mask",
                        confidence=0.70,
                        evidence_reasoning="staff appears without mask",
                        segmentation_targets=["staff", "mask", "counter"],
                        relation_hint="catering staff visible without mask",
                    ),
                ],
            )

    class CompatJudgeClient:
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
            return EvidenceJudgeResult(
                final_category=category_code,
                final_confidence=0.95,
                evidence_basis_match=True,
                violation_relation_confirmed=True,
                exception_excluded=True,
                archive_readiness=True,
                review_required=False,
                rejection_reason=None,
                violation_relation_summary=evidence_basis_summary,
            )

    callback_payloads: list[CallbackPayload] = []
    workflow = build_inspection_event_workflow(
        preliminary_client=MultiCandidatePreliminaryClient([]),
        segmentation_client=FakeSegmentationClient([]),
        evidence_judge_client=CompatJudgeClient(),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config={"callback": {"plugin": "http_callback"}},
    )

    output = workflow.run(
        input=EventSeed(
            image_uri="s3://street/frame-001.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-17",
            task_id="patrol-sh-001",
            occur_time="2026-03-09T10:00:00Z",
        )
    )
    payload = _stored_payload(output)

    first_feedback = _require_feedback(callback_payloads[0], PreliminaryEventFeedback)
    assert first_feedback.violation_category == "road_occupying_vendor"
    assert _summary(payload) == {"candidate_count": 2, "refined_count": 2, "failed_count": 0}
    assert _sub_events(payload)[0]["preliminary_feedback"]["violation_category"] == "road_occupying_vendor"
    assert _sub_events(payload)[0]["refined_feedback"]["final_category"] == "road_occupying_vendor"


def test_inspection_workflow_fans_out_multiple_candidates_with_shared_event_id_and_distinct_sub_event_ids() -> None:
    class MultiCandidatePreliminaryClient(FakePreliminaryClient):
        def analyze(self, seed: EventSeed) -> PreliminaryResult:
            self.calls.append(f"preliminary:{seed.camera_id}:{seed.location}")
            return PreliminaryResult(
                environment_analysis="street storefront scene with two issues",
                scene_elements=["storefront", "goods", "staff", "sidewalk"],
                candidates=[
                    _make_candidate(
                        violation_category="goods_blocking_road",
                        confidence=0.91,
                        evidence_reasoning="goods block sidewalk",
                        segmentation_targets=["goods", "sidewalk", "storefront_entrance"],
                        relation_hint="goods placed outside storefront and block sidewalk",
                    ),
                    _make_candidate(
                        violation_category="staff_not_wear_mask",
                        confidence=0.72,
                        evidence_reasoning="staff visible without mask",
                        segmentation_targets=["staff", "mask", "counter"],
                        relation_hint="catering staff visible without mask",
                    ),
                ],
            )

    class MultiJudgeClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

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
            self.calls.append(f"{event_id}:{category_code}")
            return EvidenceJudgeResult(
                final_category=category_code,
                final_confidence=0.9,
                evidence_basis_match=True,
                violation_relation_confirmed=True,
                exception_excluded=True,
                archive_readiness=True,
                review_required=False,
                rejection_reason=None,
                violation_relation_summary=evidence_basis_summary,
            )

    callback_payloads: list[CallbackPayload] = []
    workflow = build_inspection_event_workflow(
        preliminary_client=MultiCandidatePreliminaryClient([]),
        segmentation_client=FakeSegmentationClient([]),
        evidence_judge_client=MultiJudgeClient(),
        sink_plugin=FakeSinkPlugin(callback_payloads),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )

    output = workflow.run(
        input=EventSeed(
            image_uri="s3://street/frame-001.jpg",
            camera_id="front",
            location="南山路",
            device_id="dog-17",
            task_id="patrol-sh-001",
            occur_time="2026-03-09T10:00:00Z",
        )
    )
    payload = _stored_payload(output)

    assert payload["event_id"].startswith("evt_")
    assert len(_sub_events(payload)) == 2
    assert {item["refined_feedback"]["final_category"] for item in _sub_events(payload)} == {
        "goods_blocking_road",
        "staff_not_wear_mask",
    }
    sub_event_ids = [item["sub_event_id"] for item in _sub_events(payload)]
    assert len(set(sub_event_ids)) == 2
    assert len(callback_payloads) == 4
    assert [payload.stage for payload in callback_payloads] == [
        "preliminary",
        "preliminary",
        "refined",
        "refined",
    ]
    assert len({payload.sub_event_id for payload in callback_payloads}) == 2
