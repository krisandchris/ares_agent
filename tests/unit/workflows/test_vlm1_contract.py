from ares_agent.workflows.inspection_event_workflow import PreliminaryResult, SegmentationResult


def test_preliminary_result_includes_downstream_fields_needed_by_vlm2() -> None:
    result = PreliminaryResult(
        environment_analysis="street storefront scene",
        scene_elements=["storefront", "goods", "sidewalk"],
        evidence_reasoning="goods extend onto sidewalk",
        violation_category="goods_blocking_road",
        open_risk_type="",
        confidence=0.84,
        segmentation_targets=["goods", "storefront_entrance", "sidewalk"],
        relation_hint="goods placed outside storefront and block sidewalk",
    )

    assert result.violation_category == "goods_blocking_road"
    assert result.segmentation_targets == ["goods", "storefront_entrance", "sidewalk"]
    assert result.relation_hint == "goods placed outside storefront and block sidewalk"
    assert result.open_risk_type == ""
    assert result.confidence == 0.84


def test_segmentation_result_includes_fields_consumed_by_vlm2() -> None:
    result = SegmentationResult(
        overlay_image="s3://mock/overlay.png",
        mask_labels=["goods", "storefront_entrance", "sidewalk"],
        relation_hint="goods placed outside storefront and block sidewalk",
        segmentation_status="ok",
        mask_uri="s3://mock/mask.png",
        crop_image_uris=["s3://mock/crop.png"],
        overlay_image_uris=["s3://mock/overlay.png"],
        evidence_basis_summary="goods block sidewalk",
    )

    assert result.overlay_image == "s3://mock/overlay.png"
    assert result.mask_labels == ["goods", "storefront_entrance", "sidewalk"]
    assert result.segmentation_status == "ok"
