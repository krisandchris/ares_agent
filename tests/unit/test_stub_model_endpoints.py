from pathlib import Path

from fastapi.testclient import TestClient

from ares_agent.api.app import create_app


def test_mock_vlm_preliminary_endpoint_returns_openai_style_completion(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"suspected_categories":["road_occupying_vendor"],"risk_level":"high","prelim_confidence":0.91,"need_retake":false,"open_risk_hints":[],"evidence_targets":["stall","storefront_boundary","sidewalk_or_roadway"]}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"mask_uri":"s3://mock/mask.png","crop_image_uris":["s3://mock/crop.png"],"overlay_image_uris":["s3://mock/overlay.png"],"evidence_basis_summary":"stall crosses sidewalk"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"road_occupying_vendor","final_confidence":0.96,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"stall crosses sidewalk"}',
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
    client = TestClient(create_app(config_path=config_path))

    response = client.post(
        "/mock/vlm/preliminary",
        json={
            "model": "inspection-vlm",
            "messages": [
                {"role": "system", "content": "preliminary inspection"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "analyze this frame"},
                        {"type": "image_url", "image_url": {"url": "s3://street/frame-001.jpg"}},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"


def test_mock_sam3_segment_endpoint_returns_fastapi_style_json(tmp_path: Path) -> None:
    prelim_fixture = tmp_path / "prelim.json"
    prelim_fixture.write_text(
        '{"suspected_categories":["goods_blocking_road"],"risk_level":"medium","prelim_confidence":0.84,"need_retake":false,"open_risk_hints":[],"evidence_targets":["goods_or_materials","sidewalk","passage_obstruction"]}',
        encoding="utf-8",
    )
    sam_fixture = tmp_path / "sam.json"
    sam_fixture.write_text(
        '{"overlay_image":"s3://mock/goods_overlay.png","mask_labels":["goods","storefront_entrance","sidewalk"],"relation_hint":"goods placed outside storefront and block sidewalk","segmentation_status":"ok","mask_uri":"s3://mock/goods_mask.png","crop_image_uris":["s3://mock/goods_crop.png"],"overlay_image_uris":["s3://mock/goods_overlay.png"],"evidence_basis_summary":"goods block sidewalk"}',
        encoding="utf-8",
    )
    judge_fixture = tmp_path / "judge.json"
    judge_fixture.write_text(
        '{"final_category":"goods_blocking_road","final_confidence":0.89,"evidence_basis_match":true,"violation_relation_confirmed":true,"exception_excluded":true,"archive_readiness":true,"review_required":false,"rejection_reason":null,"violation_relation_summary":"goods block sidewalk"}',
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
    client = TestClient(create_app(config_path=config_path))

    response = client.post(
        "/mock/sam3/segment",
        json={
            "image_uri": "s3://street/frame-002.jpg",
            "targets": ["goods_or_materials", "sidewalk", "passage_obstruction"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mask_uri"] == "s3://mock/goods_mask.png"
    assert body["overlay_image"] == "s3://mock/goods_overlay.png"
    assert body["mask_labels"] == ["goods", "storefront_entrance", "sidewalk"]
    assert body["overlay_image_uris"] == ["s3://mock/goods_overlay.png"]
