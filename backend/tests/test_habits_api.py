"""API tests for habit CRUD, logging upsert, and stats."""
from __future__ import annotations

from datetime import date

BASE = "/api/v1"


def test_health(client):
    body = client.get(f"{BASE}/health").json()
    assert body["status"] == "ok"


def test_create_log_and_stats(client):
    created = client.post(f"{BASE}/habits", json={"title": "Test Habit", "frequency": "daily"})
    assert created.status_code == 201
    habit_id = created.json()["id"]

    logged = client.post(f"{BASE}/habits/{habit_id}/logs", json={})
    assert logged.status_code == 201
    assert logged.json()["status"] == "completed"

    stats = client.get(f"{BASE}/habits/{habit_id}/stats").json()
    assert stats["current_streak"] == 1
    assert stats["total_completions"] == 1


def test_log_is_upserted_not_duplicated(client):
    habit_id = client.post(f"{BASE}/habits", json={"title": "Upsert"}).json()["id"]

    client.post(f"{BASE}/habits/{habit_id}/logs", json={"status": "completed"})
    client.post(f"{BASE}/habits/{habit_id}/logs", json={"status": "skipped", "reason": "busy"})

    logs = client.get(f"{BASE}/habits/{habit_id}/logs").json()
    assert len(logs) == 1  # same day -> updated in place
    assert logs[0]["status"] == "skipped"

    stats = client.get(f"{BASE}/habits/{habit_id}/stats").json()
    assert stats["current_streak"] == 0  # a skip is not a success


def test_unlog_removes_todays_entry(client):
    habit_id = client.post(f"{BASE}/habits", json={"title": "Unlog"}).json()["id"]
    client.post(f"{BASE}/habits/{habit_id}/logs", json={})

    resp = client.delete(f"{BASE}/habits/{habit_id}/logs/{date.today().isoformat()}")
    assert resp.status_code == 204
    assert client.get(f"{BASE}/habits/{habit_id}/logs").json() == []


def test_archive_hides_from_default_list(client):
    habit_id = client.post(f"{BASE}/habits", json={"title": "Archive me"}).json()["id"]
    client.patch(f"{BASE}/habits/{habit_id}", json={"archived": True})

    assert client.get(f"{BASE}/habits").json() == []
    assert len(client.get(f"{BASE}/habits", params={"include_archived": True}).json()) == 1


def test_missing_habit_returns_404(client):
    assert client.get(f"{BASE}/habits/does-not-exist").status_code == 404
