"""Tests for focus mode: session logging, stats, and timeline integration."""
from __future__ import annotations

BASE = "/api/v1"


def _log_focus(client, duration_min, distractions=0, note=None):
    body = {"duration_min": duration_min, "distractions": distractions}
    if note:
        body["note"] = note
    return client.post(f"{BASE}/focus/sessions", json=body)


def test_create_and_list_sessions(client):
    r = _log_focus(client, 25, distractions=2, note="Deep work on Atlas")
    assert r.status_code == 201
    created = r.json()
    assert created["duration_min"] == 25
    assert created["distractions"] == 2
    assert created["started_at"]

    _log_focus(client, 50)
    listed = client.get(f"{BASE}/focus/sessions").json()
    assert len(listed) == 2
    # Most recent first.
    assert listed[0]["duration_min"] == 50


def test_stats_today_and_week(client):
    _log_focus(client, 25, distractions=1)
    _log_focus(client, 50, distractions=3)

    s = client.get(f"{BASE}/focus/stats").json()
    assert s["sessions_today"] == 2
    assert s["minutes_today"] == 75
    assert s["sessions_week"] == 2
    assert s["minutes_week"] == 75
    assert s["avg_distractions"] == 2.0  # (1 + 3) / 2
    assert s["best_day_minutes"] == 75


def test_focus_appears_in_timeline(client):
    _log_focus(client, 40, distractions=1)
    events = client.get(f"{BASE}/timeline", params={"kinds": "focus"}).json()["events"]
    assert events
    assert events[0]["kind"] == "focus"
    assert "40 min" in events[0]["title"]
