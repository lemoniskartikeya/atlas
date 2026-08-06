"""Tests for the activity timeline (aggregation, streak milestones, paging)."""
from __future__ import annotations

from datetime import date, timedelta

BASE = "/api/v1"


def _habit(client, **body):
    body.setdefault("title", "Habit")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


def test_timeline_aggregates_all_sources(client):
    hid = _habit(client, title="Meditate")
    client.post(f"{BASE}/habits/{hid}/logs", json={})  # habit + habit_created

    task_id = client.post(f"{BASE}/tasks", json={"title": "Ship"}).json()["id"]
    client.post(f"{BASE}/tasks/{task_id}/complete")  # task

    client.put(f"{BASE}/journal/{date.today().isoformat()}", json={"mood": 4, "energy": 3})  # journal

    body = client.get(f"{BASE}/timeline").json()
    kinds = {e["kind"] for e in body["events"]}
    assert {"habit", "habit_created", "task", "journal"} <= kinds

    stamps = [e["timestamp"] for e in body["events"]]
    assert stamps == sorted(stamps, reverse=True)  # reverse-chronological


def test_streak_milestone_appears(client):
    hid = _habit(client, title="Deep work")
    today = date.today()
    for i in range(7):  # seven consecutive days
        client.post(
            f"{BASE}/habits/{hid}/logs",
            json={"date": (today - timedelta(days=6 - i)).isoformat()},
        )

    events = client.get(f"{BASE}/timeline", params={"kinds": "streak"}).json()["events"]
    assert any(e["kind"] == "streak" and "7-day streak" in e["title"] for e in events)


def test_kinds_filter(client):
    hid = _habit(client, title="Read")
    client.post(f"{BASE}/habits/{hid}/logs", json={})
    client.put(f"{BASE}/journal/{date.today().isoformat()}", json={"mood": 5})

    events = client.get(f"{BASE}/timeline", params={"kinds": "journal"}).json()["events"]
    assert events
    assert all(e["kind"] == "journal" for e in events)


def test_offset_pagination(client):
    hid = _habit(client, title="Water")
    today = date.today()
    for i in range(3):
        client.post(
            f"{BASE}/habits/{hid}/logs", json={"date": (today - timedelta(days=i)).isoformat()}
        )
    # events: 1 habit_created + 3 logs = 4

    first = client.get(f"{BASE}/timeline", params={"limit": 2, "offset": 0}).json()
    assert first["total"] == 4
    assert len(first["events"]) == 2
    assert first["has_more"] is True

    second = client.get(f"{BASE}/timeline", params={"limit": 2, "offset": 2}).json()
    assert len(second["events"]) == 2
    assert second["has_more"] is False
    ids_first = {e["id"] for e in first["events"]}
    ids_second = {e["id"] for e in second["events"]}
    assert ids_first.isdisjoint(ids_second)  # no overlap across pages
