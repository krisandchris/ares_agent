from ares_agent.infra.event_store import InMemoryEventStore


def test_in_memory_event_store_saves_and_loads_latest_result() -> None:
    store = InMemoryEventStore()
    payload = {"event_id": "evt_123", "stage": "refined", "final_category": "goods_blocking_road"}

    store.save("evt_123", payload)

    assert store.get("evt_123") == payload


def test_in_memory_event_store_overwrites_existing_event_result() -> None:
    store = InMemoryEventStore()

    store.save("evt_123", {"event_id": "evt_123", "stage": "preliminary"})
    store.save("evt_123", {"event_id": "evt_123", "stage": "refined"})

    assert store.get("evt_123") == {"event_id": "evt_123", "stage": "refined"}
