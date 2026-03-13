from pathlib import Path

from ares_agent.infra.event_store import FileBackedEventStore, InMemoryEventStore


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


def test_file_backed_event_store_persists_event_for_new_store_instance(tmp_path: Path) -> None:
    store = FileBackedEventStore(base_dir=tmp_path / "event_store")
    payload = {"event_id": "evt_123", "stage": "refined", "final_category": "goods_blocking_road"}

    store.save("evt_123", payload)

    reloaded_store = FileBackedEventStore(base_dir=tmp_path / "event_store")
    assert reloaded_store.get("evt_123") == payload
