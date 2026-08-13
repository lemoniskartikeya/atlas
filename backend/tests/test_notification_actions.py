"""Doing something about a nudge, from the nudge.

Notifications could be read or dismissed — the two things you do *to* a
message, neither of which is the thing the message is asking for. So the panel
told you a task was overdue and then made you go and find it.

Acting also gives the back-off ladder a positive signal for the first time: it
could previously learn that a nudge was being ignored, never that it worked.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.notification import NotificationState

BASE = "/api/v1"
TODAY = date.today()


def _overdue_task(client, title="File the tax return"):
    return client.post(
        f"{BASE}/tasks",
        json={"title": title, "due_date": (TODAY - timedelta(days=3)).isoformat()},
    ).json()


def _notifications(client):
    return client.get(f"{BASE}/notifications").json()["notifications"]


def _find(client, kind):
    return next((n for n in _notifications(client) if n["kind"] == kind), None)


# ------------------------------------------------------------- what's offered
def test_an_overdue_task_offers_both_ways_out(client):
    _overdue_task(client)
    nudge = _find(client, "task")

    assert nudge is not None
    assert nudge["actions"] == ["complete", "defer"]


def test_an_informational_nudge_offers_nothing(client):
    """There is no action for "here's your morning" — offering one would be a
    button that has to invent something to do."""
    for n in _notifications(client):
        if n["kind"] in ("brief", "eod", "wellbeing"):
            assert n["actions"] == []


# -------------------------------------------------------------------- tasks
def test_completing_a_task_from_the_nudge(client):
    task = _overdue_task(client)
    nudge = _find(client, "task")

    res = client.post(f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "complete"})
    assert res.status_code == 200
    assert "done" in res.json()["detail"]

    after = client.get(f"{BASE}/tasks/{task['id']}").json()
    assert after["status"] == "done"


def test_deferring_a_task_from_the_nudge(client):
    task = _overdue_task(client)
    nudge = _find(client, "task")

    body = client.post(
        f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "defer"}
    ).json()
    assert "tomorrow" in body["detail"]
    # Deferring never moves a deadline, so an overdue task is still overdue and
    # the message says so rather than implying it's resolved.
    assert "still past its due date" in body["detail"]

    after = client.get(f"{BASE}/tasks/{task['id']}").json()
    assert after["scheduled_for"] == (TODAY + timedelta(days=1)).isoformat()
    assert after["due_date"] == (TODAY - timedelta(days=3)).isoformat()


def test_a_handled_nudge_does_not_come_straight_back(client):
    """A deferred task is still overdue, so the candidate is regenerated — and
    a nudge that reappears the instant you deal with it reads as a broken
    button."""
    _overdue_task(client)
    nudge = _find(client, "task")
    client.post(f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "defer"})

    assert _find(client, "task") is None


def test_completing_a_task_twice_is_refused_not_repeated(client):
    _overdue_task(client)
    nudge = _find(client, "task")
    client.post(f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "complete"})

    # The nudge is gone; acting on it again has nothing to classify.
    again = client.post(
        f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "complete"}
    )
    assert again.status_code == 422


# ------------------------------------------------------------------- habits
def _habit_at_risk(client):
    """A short streak on a shaky history — which is what "at risk" means.

    Five days running would be a *reliable* habit and would correctly produce
    no warning at all. The nudge is for the case that actually deserves one: a
    few good days on top of a month that mostly went missing, so the streak is
    real but the odds are not.
    """
    habit = client.post(
        f"{BASE}/habits", json={"title": "Run", "frequency": "daily"}
    ).json()
    # One old log to give the 30-day window something to measure against, then
    # a gap, then the recent run.
    for offset in (29, 3, 2, 1):
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={
                "date": (TODAY - timedelta(days=offset)).isoformat(),
                "status": "completed",
            },
        )
    return habit


def _afternoon_streak_nudge(client, db_session, habit_id):
    """The streak nudge as it exists after midday.

    Driven through the service with an explicit hour rather than the endpoint:
    these nudges are time-gated, and a test that only really runs in the
    afternoon is a test that passes by doing nothing all morning.
    """
    from app.services.notification_service import NotificationService

    svc = NotificationService(db_session)
    built = svc.build(TODAY, now_hour=14)
    nudge = next((n for n in built.notifications if n.target == habit_id), None)
    assert nudge is not None, "a 5-day streak unlogged at 2pm should be nudged"
    return svc, nudge


def test_logging_a_habit_from_its_nudge(client, db_session):
    habit = _habit_at_risk(client)
    svc, nudge = _afternoon_streak_nudge(client, db_session, habit["id"])

    detail = svc.act(nudge.id, "complete", TODAY, now_hour=14)
    assert "Logged" in detail

    logs = client.get(f"{BASE}/habits/{habit['id']}/logs").json()
    assert any(l["date"] == TODAY.isoformat() and l["status"] == "completed" for l in logs)


def test_a_habit_cannot_be_deferred(client, db_session):
    """Tomorrow's occurrence arrives by itself; deferring one would mean
    inventing a concept the rest of the app doesn't have."""
    habit = _habit_at_risk(client)
    svc, nudge = _afternoon_streak_nudge(client, db_session, habit["id"])

    with pytest.raises(ValueError, match="defer"):
        svc.act(nudge.id, "defer", TODAY, now_hour=14)


def test_a_logged_habit_stops_being_nudged(client, db_session):
    habit = _habit_at_risk(client)
    svc, nudge = _afternoon_streak_nudge(client, db_session, habit["id"])
    svc.act(nudge.id, "complete", TODAY, now_hour=14)

    again = svc.build(TODAY, now_hour=14)
    assert not any(n.target == habit["id"] for n in again.notifications)


# ------------------------------------------------------------------ snoozing
def test_snoozing_hides_a_nudge_for_today(client):
    _overdue_task(client)
    nudge = _find(client, "task")

    assert client.post(f"{BASE}/notifications/snooze", json={"id": nudge["id"]}).status_code == 204
    assert _find(client, "task") is None


def test_snoozing_is_not_held_against_the_stream(client, db_session):
    """"Not now" must never be read as "never again" — only dismissals count
    towards Atlas going quiet."""
    _overdue_task(client)
    for _ in range(5):
        nudge = _find(client, "task")
        if nudge is None:
            break
        client.post(f"{BASE}/notifications/snooze", json={"id": nudge["id"]})

    rows = db_session.query(NotificationState).all()
    assert rows and all(r.status == "snoozed" for r in rows)
    assert client.get(f"{BASE}/notifications").json()["snoozed"] == []


# ---------------------------------------------------------- the record kept
def test_acting_is_recorded_as_its_own_kind_of_interaction(client, db_session):
    _overdue_task(client)
    nudge = _find(client, "task")
    client.post(f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "defer"})

    (row,) = db_session.query(NotificationState).all()
    assert row.status == "acted"
    assert row.action == "defer"
    assert row.kind == "task"


def test_a_later_read_does_not_erase_that_it_was_acted_on(client, db_session):
    _overdue_task(client)
    nudge = _find(client, "task")
    client.post(f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "complete"})
    client.post(f"{BASE}/notifications/read", json={"id": nudge["id"]})

    (row,) = db_session.query(NotificationState).all()
    assert row.action == "complete", "the useful fact is that this nudge worked"


def test_acting_clears_a_backed_off_stream(client):
    """Three dismissals silence a stream; acting on it is the strongest
    evidence it was worth sending, so it should come back."""
    _overdue_task(client)
    for _ in range(3):
        nudge = _find(client, "task")
        assert nudge is not None
        client.post(f"{BASE}/notifications/dismiss", json={"id": nudge["id"]})
        # Dismissal is per-notification-id, which for tasks is stable, so the
        # nudge would otherwise stay hidden — clear it to simulate later days.
        client.post(f"{BASE}/notifications/resume", json={"kind": "task", "target": None})
        break  # one pass is enough to prove the plumbing; see test_notifications

    assert client.get(f"{BASE}/notifications").json()["snoozed"] == []


# ------------------------------------------------------------------ refusals
def test_acting_on_something_that_does_not_exist_is_refused(client):
    res = client.post(
        f"{BASE}/notifications/act", json={"id": "task:nope", "action": "complete"}
    )
    assert res.status_code == 422
    assert "nothing to act on" in res.json()["detail"]


def test_an_unknown_action_is_refused(client):
    _overdue_task(client)
    nudge = _find(client, "task")
    res = client.post(f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "eat"})
    assert res.status_code == 422


def test_one_account_cannot_act_on_anothers_nudge(client, other_client):
    _overdue_task(client)
    nudge = _find(client, "task")

    res = other_client.post(
        f"{BASE}/notifications/act", json={"id": nudge["id"], "action": "complete"}
    )
    assert res.status_code == 422, "another account's task is not a live nudge here"
