"""Tests for the weekly review (deterministic windows via a fixed Sunday)."""
from __future__ import annotations

from datetime import date, timedelta

from app.services.review_service import WeeklyReviewService

BASE = "/api/v1"

# A Sunday, so build(today=SUNDAY) reviews a full Mon–Sun week.
SUNDAY = date(2026, 8, 9)
MONDAY = SUNDAY - timedelta(days=6)


def _habit(client, **body):
    body.setdefault("title", "Habit")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


def _log(client, habit_id, d: date):
    client.post(f"{BASE}/habits/{habit_id}/logs", json={"date": d.isoformat()})


def test_review_endpoint_shape(client):
    hid = _habit(client, title="Meditate")
    client.post(f"{BASE}/habits/{hid}/logs", json={})  # today

    r = client.get(f"{BASE}/review").json()
    for key in ("start", "end", "label", "completion_rate", "metrics", "wins", "watchouts", "focus", "narrative"):
        assert key in r
    keys = {m["key"] for m in r["metrics"]}
    assert {"completion", "mood", "energy", "sleep", "tasks"} <= keys
    assert r["narrative"]


def test_flawless_week_is_a_win(client, db_session):
    hid = _habit(client, title="Journal")
    for i in range(7):  # every day Mon..Sun
        _log(client, hid, MONDAY + timedelta(days=i))

    review = WeeklyReviewService(db_session).build(offset=0, today=SUNDAY)
    assert review.completion_rate == 1.0
    assert review.completions == 7 and review.due == 7
    completion = next(m for m in review.metrics if m.key == "completion")
    assert completion.value == "100%"
    assert any("Flawless" in w.detail for w in review.wins)


def test_low_week_is_a_watchout(client, db_session):
    hid = _habit(client, title="Exercise")
    _log(client, hid, MONDAY)  # 1 of 7

    review = WeeklyReviewService(db_session).build(offset=0, today=SUNDAY)
    assert review.completion_rate < 0.2
    assert any(w.habit_id == hid for w in review.watchouts)
    assert review.focus  # a next-week suggestion is produced


def test_offset_selects_previous_week(client, db_session):
    hid = _habit(client, title="Read")
    # Log in the *previous* week (Mon..Sun before MONDAY).
    for i in range(7):
        _log(client, hid, MONDAY - timedelta(days=7) + timedelta(days=i))

    svc = WeeklyReviewService(db_session)
    this_week = svc.build(offset=0, today=SUNDAY)
    last_week = svc.build(offset=1, today=SUNDAY)

    assert this_week.completions == 0
    assert last_week.completions == 7
    assert last_week.label == "Last week"
    assert last_week.is_current is False
    assert last_week.can_go_forward is True
