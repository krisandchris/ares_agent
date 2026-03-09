from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.domain.events import EventSeed
from ares_agent.model_clients.http_clients import (
    Sam3FastApiClient,
    SglangVlmJudgeClient,
    SglangVlmPreliminaryClient,
)
from ares_agent.plugins.http_callback import HttpCallbackPlugin
from ares_agent.workflows.inspection_event_workflow import build_inspection_event_workflow


def test_workflow_can_run_through_local_stub_http_clients(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"suspected_categories":["motor_vehicle_illegal_parking"],"risk_level":"high","prelim_confidence":0.90,"need_retake":false,"open_risk_hints":[],"evidence_targets":["motor_vehicle","sidewalk_or_bus_stop_or_unmarked_area"]}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"overlay_image":"s3://mock/motor_overlay.png","mask_labels":["motor_vehicle","sidewalk_or_bus_stop_or_unmarked_area"],"relation_hint":"vehicle overlaps sidewalk boundary","segmentation_status":"ok","mask_uri":"s3://mock/motor_mask.png","crop_image_uris":["s3://mock/motor_crop.png"],"overlay_image_uris":["s3://mock/motor_overlay.png"],"evidence_basis_summary":"vehicle overlaps sidewalk boundary"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"motor_vehicle_illegal_parking","final_confidence":0.92,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"vehicle overlaps sidewalk boundary"}',
        encoding="utf-8",
    )
    config_path = tmp_path / "agent_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "callback:",
                "  plugin: http_callback",
                "  endpoint: https://backend.example/api/v1/events/callback",
                "mock_clients:",
                f"  preliminary_fixture: {prelim_fixture}",
                f"  segmentation_fixture: {sam_fixture}",
                f"  evidence_judge_fixture: {judge_fixture}",
            ]
        ),
        encoding="utf-8",
    )
    stub_app = create_app(config_path=config_path)
    stub_client = TestClient(stub_app)

    captured_requests: list[tuple[str, dict[str, object]]] = []

    def local_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        captured_requests.append((url, payload))
        response = stub_client.post(url, json=payload, headers=headers)
        return response.json()

    callback_payloads: list[dict[str, object]] = []

    workflow = build_inspection_event_workflow(
        preliminary_client=SglangVlmPreliminaryClient(
            endpoint="/mock/vlm/preliminary",
            model_name="inspection-vlm",
            requester=local_requester,
        ),
        segmentation_client=Sam3FastApiClient(
            endpoint="/mock/sam3/segment",
            requester=local_requester,
        ),
        evidence_judge_client=SglangVlmJudgeClient(
            endpoint="/mock/vlm/judge",
            model_name="inspection-vlm",
            requester=local_requester,
        ),
        sink_plugin=HttpCallbackPlugin(
            endpoint="https://backend.example/api/v1/events/callback",
            sender=lambda url, headers, payload: callback_payloads.append(payload) or {"status_code": 200},
        ),
        runtime_config={"callback": {"send_preliminary": True, "send_refined": True}},
    )

    output = workflow.run(
        input=EventSeed(
            image_uri="s3://street/frame-005.jpg",
            frame_id="frame-005",
            device_id="dog-22",
            task_id="patrol-sh-006",
            occur_time="2026-03-09T10:50:00Z",
        )
    )

    assert output.content["stage"] == "refined"
    assert output.content["refined_feedback"]["final_category"] == "motor_vehicle_illegal_parking"
    assert [payload["stage"] for payload in callback_payloads] == ["preliminary", "refined"]
    sam_request = next(payload for url, payload in captured_requests if url == "/mock/sam3/segment")
    assert sam_request["image_uri"] == "s3://street/frame-005.jpg"
    judge_request = next(payload for url, payload in captured_requests if url == "/mock/vlm/judge")
    user_content = judge_request["messages"][1]["content"]
    assert user_content[0]["text"].startswith("category_code=motor_vehicle_illegal_parking")
    assert user_content[1]["image_url"]["url"] == "s3://mock/motor_overlay.png"
