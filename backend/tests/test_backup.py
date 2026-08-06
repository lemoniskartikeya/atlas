"""Tests for backup export/import (round-trip restore)."""
from __future__ import annotations

from datetime import date

BASE = "/api/v1"


def _seed(client):
    hid = client.post(f"{BASE}/habits", json={"title": "Meditate", "category": "mind"}).json()["id"]
    client.post(f"{BASE}/habits/{hid}/logs", json={"date": "2026-08-01", "status": "completed"})
    client.post(f"{BASE}/tasks", json={"title": "Ship backups", "priority": "high"})
    client.put(f"{BASE}/journal/2026-08-01", json={"mood": 4, "energy": 3})
    client.post(f"{BASE}/focus/sessions", json={"duration_min": 25, "distractions": 1})


def test_export_shape(client):
    _seed(client)
    doc = client.get(f"{BASE}/backup/export").json()
    assert doc["atlas_backup"] is True
    assert doc["version"] >= 1
    assert doc["exported_at"]
    data = doc["data"]
    assert len(data["habits"]) == 1
    assert len(data["habit_logs"]) == 1
    assert len(data["tasks"]) == 1
    assert len(data["journal_entries"]) == 1
    assert len(data["focus_sessions"]) == 1


def test_round_trip_restore(client):
    _seed(client)
    backup = client.get(f"{BASE}/backup/export").json()

    # Mutate state after the backup: add a habit + task that should be wiped.
    client.post(f"{BASE}/habits", json={"title": "Extra habit"})
    client.post(f"{BASE}/tasks", json={"title": "Extra task"})
    assert len(client.get(f"{BASE}/habits").json()) == 2

    res = client.post(f"{BASE}/backup/import", json=backup)
    assert res.status_code == 200
    counts = res.json()["imported"]
    assert counts["habits"] == 1 and counts["tasks"] == 1

    # State matches the backup exactly — extras gone, originals restored.
    habits = client.get(f"{BASE}/habits").json()
    assert len(habits) == 1 and habits[0]["title"] == "Meditate"
    assert len(client.get(f"{BASE}/tasks").json()) == 1
    # Nested data survived (enum + date columns coerced correctly).
    logs = client.get(f"{BASE}/habits/{habits[0]['id']}/logs").json()
    assert len(logs) == 1 and logs[0]["date"] == "2026-08-01" and logs[0]["status"] == "completed"


def test_rejects_non_atlas_document(client):
    r = client.post(f"{BASE}/backup/import", json={"atlas_backup": False, "data": {}})
    assert r.status_code == 400
