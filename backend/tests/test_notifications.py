"""Tests for smart notifications: time-gating + read/dismiss state.

Time-gated rules are tested against the service directly (with an explicit
``now_hour``); the HTTP read/dismiss/read-all flow is tested through the client
using overdue-task notifications, which are time-independent. The model path is
pinned off for determinism.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.notification_service import NotificationService

BASE = "/api/v1"


@pytest.fixture(autouse=True)
def _no_model(monkeypatch):
    monkeypatch.setattr(
        "app.services.ml_gateway.habit_predictions", lambda session, today=None: (None, None)
    )


def _kinds(resp):
    return {n["id"].split(":")[0] if isinstance(n, dict) else n.kind for n in resp}


def _new_habit(client, **body):
    body.setdefault("title", "Habit")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


# --------------------------------------------------------------- time gating

def test_morning_brief_only_in_the_morning(client, db_session):
    _new_habit(client, title="Meditate")
    _new_habit(client, title="Read")
    svc = NotificationService(db_session)
    today = date.today()

    morning = svc.build(today, now_hour=8)
    assert any(n.kind == "brief" for n in morning.notifications)

    midday = svc.build(today, now_hour=14)
    assert not any(n.kind == "brief" for n in midday.notifications)


def test_end_of_day_wrap_after_eight(client, db_session):
    _new_habit(client, title="Journal")
    svc = NotificationService(db_session)
    today = date.today()

    assert not any(n.kind == "eod" for n in svc.build(today, now_hour=14).notifications)
    assert any(n.kind == "eod" for n in svc.build(today, now_hour=21).notifications)


# ------------------------------------------------------- read / dismiss (HTTP)

def _overdue_task(client, title="Ship it"):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return client.post(
        f"{BASE}/tasks", json={"title": title, "priority": "high", "due_date": yesterday}
    ).json()["id"]


def test_overdue_task_notification_can_be_dismissed(client):
    task_id = _overdue_task(client)
    nid = f"task:{task_id}"

    body = client.get(f"{BASE}/notifications").json()
    ids = [n["id"] for n in body["notifications"]]
    assert nid in ids
    assert body["unread"] >= 1

    assert client.post(f"{BASE}/notifications/dismiss", json={"id": nid}).status_code == 204

    after = client.get(f"{BASE}/notifications").json()
    assert nid not in [n["id"] for n in after["notifications"]]


def test_read_and_read_all(client):
    task_id = _overdue_task(client, title="Pay invoice")
    nid = f"task:{task_id}"

    before = client.get(f"{BASE}/notifications").json()
    unread_before = before["unread"]
    assert unread_before >= 1

    assert client.post(f"{BASE}/notifications/read", json={"id": nid}).status_code == 204
    mid = client.get(f"{BASE}/notifications").json()
    marked = next(n for n in mid["notifications"] if n["id"] == nid)
    assert marked["read"] is True
    assert mid["unread"] == unread_before - 1

    _overdue_task(client, title="Second thing")
    assert client.post(f"{BASE}/notifications/read-all").status_code == 204
    done = client.get(f"{BASE}/notifications").json()
    assert done["unread"] == 0
    assert all(n["read"] for n in done["notifications"])
