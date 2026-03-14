from ares_agent.domain.events import EventSeed, generate_event_id, generate_sub_event_id


def test_generate_event_id_is_stable_for_same_frame_seed() -> None:
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )

    first = generate_event_id(seed)
    second = generate_event_id(seed)

    assert first == second


def test_generate_event_id_changes_when_frame_changes() -> None:
    base = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        camera_id="front",
        location="南山路",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )

    changed = EventSeed(
        image_uri="s3://street/frame-002.jpg",
        camera_id="left",
        location="南山路",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )

    assert generate_event_id(base) != generate_event_id(changed)


def test_generate_sub_event_id_is_stable_and_distinct_per_candidate() -> None:
    first = generate_sub_event_id(
        event_id="evt_root",
        violation_category="goods_blocking_road",
        relation_hint="goods placed outside storefront and block sidewalk",
        candidate_index=0,
    )
    second = generate_sub_event_id(
        event_id="evt_root",
        violation_category="goods_blocking_road",
        relation_hint="goods placed outside storefront and block sidewalk",
        candidate_index=0,
    )
    third = generate_sub_event_id(
        event_id="evt_root",
        violation_category="staff_not_wear_mask",
        relation_hint="catering staff visible without mask",
        candidate_index=1,
    )

    assert first == second
    assert first != third
