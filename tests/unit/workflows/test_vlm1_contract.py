from ares_agent.workflows.inspection_event_workflow import PreliminaryCandidate, PreliminaryResult, SegmentationResult


def _make_candidate(
    *,
    violation_category: str,
    open_risk_type: str = "",
    confidence: float,
    evidence_reasoning: str,
    segmentation_targets: object,
    relation_hint: str,
    sub_event_id: str | None = None,
) -> PreliminaryCandidate:
    return PreliminaryCandidate.model_validate(
        {
            "sub_event_id": sub_event_id,
            "violation_category": violation_category,
            "open_risk_type": open_risk_type,
            "confidence": confidence,
            "evidence_reasoning": evidence_reasoning,
            "segmentation_targets": segmentation_targets,
            "relation_hint": relation_hint,
        }
    )


def test_preliminary_result_includes_downstream_fields_needed_by_vlm2() -> None:
    result = PreliminaryResult(
        environment_analysis="street storefront scene",
        scene_elements=["storefront", "goods", "sidewalk"],
        candidates=[
            _make_candidate(
                violation_category="goods_blocking_road",
                confidence=0.84,
                evidence_reasoning="goods extend onto sidewalk",
                segmentation_targets=["goods", "storefront_entrance", "sidewalk"],
                relation_hint="goods placed outside storefront and block sidewalk",
            )
        ],
    )

    assert result.violation_category == "goods_blocking_road"
    assert result.segmentation_targets == ["goods", "storefront_entrance", "sidewalk"]
    assert result.relation_hint == "goods placed outside storefront and block sidewalk"
    assert result.open_risk_type == ""
    assert result.confidence == 0.84


def test_preliminary_result_supports_multiple_candidates_and_exposes_first_candidate_for_legacy_consumers() -> None:
    result = PreliminaryResult(
        environment_analysis="street storefront scene with multiple issues",
        scene_elements=["storefront", "goods", "staff", "mask", "sidewalk"],
        candidates=[
            _make_candidate(
                sub_event_id="sub_evt_goods",
                violation_category="goods_blocking_road",
                confidence=0.91,
                evidence_reasoning="goods block the sidewalk",
                segmentation_targets=["goods", "sidewalk", "storefront_entrance"],
                relation_hint="goods placed outside storefront and block sidewalk",
            ),
            _make_candidate(
                sub_event_id="sub_evt_mask",
                violation_category="staff_not_wear_mask",
                confidence=0.72,
                evidence_reasoning="staff appears to work without mask",
                segmentation_targets=["staff", "mask", "counter"],
                relation_hint="catering staff visible without mask",
            ),
        ],
    )

    assert result.violation_category == "goods_blocking_road"
    assert result.open_risk_type == ""
    assert result.confidence == 0.91
    assert result.segmentation_targets == ["goods", "sidewalk", "storefront_entrance"]
    assert result.relation_hint == "goods placed outside storefront and block sidewalk"
    assert result.candidates[1].violation_category == "staff_not_wear_mask"


def test_preliminary_result_normalizes_string_segmentation_targets() -> None:
    result = PreliminaryResult(
        environment_analysis="sidewalk scene",
        scene_elements=["yellow_bicycle", "sidewalk"],
        candidates=[
            _make_candidate(
                violation_category="nonmotor_vehicle_illegal_parking",
                confidence=0.95,
                evidence_reasoning="yellow bicycle occupies sidewalk",
                segmentation_targets="yellow_bicycle, sidewalk_area",
                relation_hint="nonmotor_vehicle_occupies_walkway",
            )
        ],
    )

    assert result.segmentation_targets == ["yellow_bicycle", "sidewalk_area"]


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
