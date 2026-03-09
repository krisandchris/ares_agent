from ares_agent.domain.events import EventSeed, generate_event_id


def test_generate_event_id_is_stable_for_same_frame_seed() -> None:
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        frame_id="frame-001",
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
        frame_id="frame-001",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )

    changed = EventSeed(
        image_uri="s3://street/frame-002.jpg",
        frame_id="frame-002",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )

    assert generate_event_id(base) != generate_event_id(changed)
