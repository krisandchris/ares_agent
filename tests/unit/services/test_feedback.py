from ares_agent.domain.events import EventSeed, generate_event_id
from ares_agent.services.feedback import build_preliminary_feedback, build_refined_feedback


def test_refined_feedback_reuses_preliminary_event_id() -> None:
    seed = EventSeed(
        image_uri="s3://street/frame-001.jpg",
        frame_id="frame-001",
        device_id="dog-17",
        task_id="patrol-sh-001",
        occur_time="2026-03-09T10:00:00Z",
    )
    event_id = generate_event_id(seed)

    preliminary = build_preliminary_feedback(
        event_id=event_id,
        frame_id=seed.frame_id,
        violation_category="road_occupying_vendor",
        open_risk_type="",
        confidence=0.91,
        async_enqueued=True,
    )

    refined = build_refined_feedback(
        event_id=event_id,
        frame_id=seed.frame_id,
        final_category="road_occupying_vendor",
        final_confidence=0.96,
        archive_readiness=True,
        review_required=False,
        event_version=2,
    )

    assert preliminary.event_id == refined.event_id
    assert preliminary.stage == "preliminary"
    assert preliminary.violation_category == "road_occupying_vendor"
    assert refined.stage == "refined"
    assert refined.event_version == 2
