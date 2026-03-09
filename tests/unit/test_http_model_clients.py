from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app
from ares_agent.domain.events import EventSeed
from ares_agent.model_clients.http_clients import (
    Sam3FastApiClient,
    SglangVlmJudgeClient,
    SglangVlmPreliminaryClient,
)


def test_http_model_clients_parse_local_stub_responses(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"suspected_categories":["unauthorized_electrical_wiring"],"risk_level":"high","prelim_confidence":0.93,"need_retake":false,"open_risk_hints":[],"evidence_targets":["wire","charger","electric_vehicle","outdoor_connection"]}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"mask_uri":"s3://mock/wiring_mask.png","crop_image_uris":["s3://mock/wiring_crop.png"],"overlay_image_uris":["s3://mock/wiring_overlay.png"],"evidence_basis_summary":"wire connects storefront charger to electric vehicle"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"unauthorized_electrical_wiring","final_confidence":0.95,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"wire connects storefront charger to electric vehicle"}',
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
    app = create_app(config_path=config_path)
    client = TestClient(app)

    def local_requester(url: str, headers: dict[str, str], payload: dict[str, object]) -> dict[str, object]:
        response = client.post(url, json=payload, headers=headers)
        return response.json()

    prelim_client = SglangVlmPreliminaryClient(
        endpoint="/mock/vlm/preliminary",
        model_name="inspection-vlm",
        requester=local_requester,
    )
    sam3_client = Sam3FastApiClient(
        endpoint="/mock/sam3/segment",
        requester=local_requester,
    )
    judge_client = SglangVlmJudgeClient(
        endpoint="/mock/vlm/judge",
        model_name="inspection-vlm",
        requester=local_requester,
    )

    prelim = prelim_client.analyze(
        EventSeed(
            image_uri="s3://street/frame-003.jpg",
            frame_id="frame-003",
            device_id="dog-21",
            task_id="patrol-sh-005",
            occur_time="2026-03-09T10:40:00Z",
        )
    )
    sam = sam3_client.segment("s3://street/frame-003.jpg", prelim.evidence_targets)
    judge = judge_client.judge(
        category_code=prelim.suspected_categories[0],
        overlay_image=sam.overlay_image,
        mask_labels=sam.mask_labels,
        relation_hint=sam.relation_hint,
        evidence_basis_summary=sam.evidence_basis_summary,
        preliminary=prelim,
    )

    assert prelim.suspected_categories == ["unauthorized_electrical_wiring"]
    assert sam.mask_uri == "s3://mock/wiring_mask.png"
    assert judge.final_category == "unauthorized_electrical_wiring"
