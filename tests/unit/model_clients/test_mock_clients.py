from pathlib import Path

import pytest

from ares_agent.model_clients.mock_clients import (
    MockEvidenceJudgeClient,
    MockPreliminaryClient,
    MockSegmentationClient,
)


def test_mock_preliminary_client_loads_json_fixture() -> None:
    client = MockPreliminaryClient(
        fixture_path=Path("fixtures/mock_vlm_preliminary/road_occupying_vendor.json")
    )

    result = client.analyze_from_fixture()

    assert result.violation_category == "road_occupying_vendor"
    assert result.open_risk_type == ""
    assert result.confidence == 0.91
    assert "stall" in result.segmentation_targets


def test_mock_segmentation_client_loads_json_fixture() -> None:
    client = MockSegmentationClient(
        fixture_path=Path("fixtures/mock_sam3/road_occupying_vendor.json")
    )

    result = client.segment_from_fixture()

    assert result.mask_uri.endswith("road_occupying_vendor_mask.png")
    assert result.overlay_image_uris[0].endswith("road_occupying_vendor_overlay.png")
    assert "storefront boundary" in result.evidence_basis_summary


def test_mock_evidence_judge_client_loads_json_fixture() -> None:
    client = MockEvidenceJudgeClient(
        fixture_path=Path("fixtures/mock_vlm_judge/road_occupying_vendor.json")
    )

    result = client.judge_from_fixture()

    assert result.final_category == "road_occupying_vendor"
    assert result.archive_readiness is True
    assert result.exception_excluded is True
    assert result.review_required is False


@pytest.mark.parametrize(
    ("category_code", "confidence", "anchor"),
    [
        ("goods_blocking_road", 0.84, "goods"),
        ("unauthorized_electrical_wiring", 0.93, "wire"),
        ("motor_vehicle_illegal_parking", 0.9, "motor_vehicle"),
    ],
)
def test_mock_preliminary_client_supports_multiple_categories(
    category_code: str,
    confidence: float,
    anchor: str,
) -> None:
    client = MockPreliminaryClient(
        fixture_path=Path(f"fixtures/mock_vlm_preliminary/{category_code}.json")
    )

    result = client.analyze_from_fixture()

    assert result.violation_category == category_code
    assert result.confidence == confidence
    assert anchor in result.segmentation_targets


@pytest.mark.parametrize(
    ("category_code", "mask_suffix"),
    [
        ("goods_blocking_road", "goods_blocking_road_mask.png"),
        ("unauthorized_electrical_wiring", "unauthorized_electrical_wiring_mask.png"),
        ("motor_vehicle_illegal_parking", "motor_vehicle_illegal_parking_mask.png"),
    ],
)
def test_mock_segmentation_client_supports_multiple_categories(
    category_code: str,
    mask_suffix: str,
) -> None:
    client = MockSegmentationClient(
        fixture_path=Path(f"fixtures/mock_sam3/{category_code}.json")
    )

    result = client.segment_from_fixture()

    assert result.mask_uri is not None
    assert result.mask_uri.endswith(mask_suffix)
    assert result.overlay_image_uris


@pytest.mark.parametrize(
    "category_code",
    [
        "goods_blocking_road",
        "unauthorized_electrical_wiring",
        "motor_vehicle_illegal_parking",
    ],
)
def test_mock_evidence_judge_client_supports_multiple_categories(category_code: str) -> None:
    client = MockEvidenceJudgeClient(
        fixture_path=Path(f"fixtures/mock_vlm_judge/{category_code}.json")
    )

    result = client.judge_from_fixture()

    assert result.final_category == category_code
    assert result.archive_readiness is True
