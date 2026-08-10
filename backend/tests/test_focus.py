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


# --------------------------------------------------- timezone regression tests
# Sessions are stored as UTC, but "today" everywhere else in the app means the
# *local* date. Reading them back in UTC put every session logged after 18:30
# IST on the previous day, so the focus stats silently reset to zero for the
# rest of the evening.

def test_back_to_back_sessions_get_distinct_timestamps():
    """`datetime.now()` on Windows ticks every 15.625 ms.

    Two sessions logged inside one tick used to get byte-identical `started_at`
    values, leaving "most recent first" up to the database's row order — the
    newly logged session appeared *below* the previous one.
    """
    from app.models.base import utcnow

    stamps = [utcnow() for _ in range(50)]
    assert len(set(stamps)) > 1, "clock is too coarse to order same-tick writes"
    assert all(b >= a for a, b in zip(stamps, stamps[1:])), "clock went backwards"


def test_sessions_logged_in_the_same_tick_stay_newest_first(client):
    """The user-visible symptom, reproduced without any artificial delay."""
    for minutes in (15, 25, 50):
        _log_focus(client, minutes)

    listed = client.get(f"{BASE}/focus/sessions").json()
    assert [s["duration_min"] for s in listed] == [50, 25, 15]


def test_local_day_treats_naive_timestamps_as_utc():
    """SQLite returns naive datetimes; they must not be read as local time."""
    from datetime import datetime, timezone

    from app.services.focus_service import _local_day

    naive = datetime(2026, 8, 7, 19, 15)
    aware = naive.replace(tzinfo=timezone.utc)
    assert _local_day(naive) == _local_day(aware)


def test_local_day_resolves_in_local_time_not_utc():
    from datetime import datetime, timedelta, timezone

    from app.services.focus_service import _local_day

    ts = datetime(2026, 8, 7, 19, 15, tzinfo=timezone.utc)
    assert _local_day(ts) == ts.astimezone().date()

    # Documents the trap: in any zone ahead of UTC these genuinely differ, and
    # the UTC reading is the wrong one to compare against date.today().
    ist = timezone(timedelta(hours=5, minutes=30))
    assert ts.astimezone(ist).date() != ts.date()


def test_session_logged_now_always_counts_as_today(client):
    """The user-visible symptom: a session just logged shows under 'today'."""
    _log_focus(client, 30)
    assert client.get(f"{BASE}/focus/stats").json()["sessions_today"] == 1
