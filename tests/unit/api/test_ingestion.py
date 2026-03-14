from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.infra.event_store import InMemoryEventStore
from ares_agent.plugins.http_callback import HttpCallbackPlugin
from ares_agent.workflows.inspection_event_workflow import build_inspection_event_workflow
from ares_agent.model_clients.mock_clients import (
    MockEvidenceJudgeClient,
    MockPreliminaryClient,
    MockSegmentationClient,
)


def test_post_ingestion_runs_mock_workflow_and_returns_shared_event_payload() -> None:
    callback_payloads: list[dict[str, object]] = []
    event_store = InMemoryEventStore()

    def fake_sender(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        callback_payloads.append(payload)
        return {"status_code": 200, "backend_trace_id": "trace-api"}

    workflow = build_inspection_event_workflow(
        preliminary_client=MockPreliminaryClient(
            fixture_path=Path("fixtures/mock_vlm_preliminary/road_occupying_vendor.json")
        ),
        segmentation_client=MockSegmentationClient(
            fixture_path=Path("fixtures/mock_sam3/road_occupying_vendor.json")
        ),
        evidence_judge_client=MockEvidenceJudgeClient(
            fixture_path=Path("fixtures/mock_vlm_judge/road_occupying_vendor.json")
        ),
        sink_plugin=HttpCallbackPlugin(
            endpoint="https://backend.example/api/v1/events/callback",
            auth_token="secret-token",
            sender=fake_sender,
        ),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )
    app = create_app(workflow=workflow, event_store=event_store)
    client = TestClient(app)

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "camera_id": "front",
            "location": "南山路",
            "device_id": "dog-17",
            "task_id": "patrol-sh-001",
            "occur_time": "2026-03-09T10:00:00Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"].startswith("evt_")
    assert body["stage"] == "refined"
    assert set(body) == {"event_id", "stage", "frame_seed", "preliminary", "summary", "sub_events"}
    assert body["summary"] == {"candidate_count": 1, "refined_count": 1, "failed_count": 0}
    assert len(body["sub_events"]) == 1
    assert body["sub_events"][0]["preliminary_feedback"]["event_id"] == body["event_id"]
    assert body["sub_events"][0]["refined_feedback"]["final_category"] == "road_occupying_vendor"
    assert body["sub_events"][0]["evidence_package"]["archive_readiness"] is True
    assert len(callback_payloads) == 2
    assert callback_payloads[0]["stage"] == "preliminary"
    assert callback_payloads[1]["stage"] == "refined"
    assert event_store.get(body["event_id"]) == body


def test_post_ingestion_rejects_invalid_request_body() -> None:
    client = TestClient(create_app(workflow=None))

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "camera_id": "front",
            "device_id": "dog-17",
        },
    )

    assert response.status_code == 422


def test_post_ingestion_returns_sub_events_when_preliminary_has_multiple_candidates() -> None:
    class MultiCandidatePreliminaryClient:
        def analyze(self, seed):
            from ares_agent.workflows.inspection_event_workflow import PreliminaryResult

            return PreliminaryResult(
                environment_analysis="street storefront scene with two issues",
                scene_elements=["storefront", "goods", "staff", "sidewalk"],
                candidates=[
                    {
                        "violation_category": "goods_blocking_road",
                        "open_risk_type": "",
                        "confidence": 0.91,
                        "evidence_reasoning": "goods block sidewalk",
                        "segmentation_targets": ["goods", "sidewalk", "storefront_entrance"],
                        "relation_hint": "goods placed outside storefront and block sidewalk",
                    },
                    {
                        "violation_category": "staff_not_wear_mask",
                        "open_risk_type": "",
                        "confidence": 0.72,
                        "evidence_reasoning": "staff visible without mask",
                        "segmentation_targets": ["staff", "mask", "counter"],
                        "relation_hint": "catering staff visible without mask",
                    },
                ],
            )

    class SimpleJudgeClient:
        def judge(
            self,
            *,
            event_id,
            category_code,
            overlay_image,
            mask_labels,
            relation_hint,
            segmentation_status,
            evidence_basis_summary,
            preliminary,
        ):
            from ares_agent.workflows.inspection_event_workflow import EvidenceJudgeResult

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

    callback_payloads: list[dict[str, object]] = []
    event_store = InMemoryEventStore()
    workflow = build_inspection_event_workflow(
        preliminary_client=MultiCandidatePreliminaryClient(),
        segmentation_client=MockSegmentationClient(
            fixture_path=Path("fixtures/mock_sam3/road_occupying_vendor.json")
        ),
        evidence_judge_client=SimpleJudgeClient(),
        sink_plugin=HttpCallbackPlugin(
            endpoint="https://backend.example/api/v1/events/callback",
            auth_token="secret-token",
            sender=lambda url, headers, payload: callback_payloads.append(payload) or {"status_code": 200},
        ),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )
    app = create_app(workflow=workflow, event_store=event_store)
    client = TestClient(app)

    response = client.post(
        "/v1/inspection-items",
        json={
            "image_uri": "s3://street/frame-001.jpg",
            "camera_id": "front",
            "location": "南山路",
            "device_id": "dog-17",
            "task_id": "patrol-sh-001",
            "occur_time": "2026-03-09T10:00:00Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {"candidate_count": 2, "refined_count": 2, "failed_count": 0}
    assert len(body["sub_events"]) == 2
    assert len(callback_payloads) == 4
