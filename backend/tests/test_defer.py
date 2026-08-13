"""Pushing a task to another day.

The rule that matters most here is what deferring does *not* do: it never
touches the due date. "I'll do it tomorrow" must not quietly become "this was
never late" — a task tracker that resolves your overdue items by moving the
goalposts is worse than one with no defer button at all.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.models.plan_interaction import PlanInteraction

BASE = "/api/v1"
TODAY = date.today()


def _task(client, **kw):
    body = {"title": "File the tax return", "priority": "high"}
    return client.post(f"{BASE}/tasks", json={**body, **kw}).json()


def _defer(client, task_id, **kw):
    return client.post(f"{BASE}/planner/defer", json={"task_id": task_id, **kw})


def test_deferring_moves_when_you_plan_to_do_it(client):
    task = _task(client)
    res = _defer(client, task["id"])

    assert res.status_code == 200
    body = res.json()
    assert body["scheduled_for"] == (TODAY + timedelta(days=1)).isoformat()
    assert body["detail"] == "Moved to tomorrow."


def test_deferring_never_moves_the_deadline(client):
    """The whole point. Deferring is about your plan, not your commitment."""
    due = TODAY + timedelta(days=2)
    task = _task(client, due_date=due.isoformat())

    _defer(client, task["id"], days=5)

    after = client.get(f"{BASE}/tasks/{task['id']}").json()
    assert after["due_date"] == due.isoformat(), "the deadline is not yours to move"
    assert after["scheduled_for"] == (TODAY + timedelta(days=5)).isoformat()


def test_an_overdue_task_stays_overdue_and_says_so(client):
    task = _task(client, due_date=(TODAY - timedelta(days=3)).isoformat())
    body = _defer(client, task["id"]).json()

    assert body["still_overdue"] is True
    assert "stays overdue" in body["detail"]


def test_a_task_deferred_within_its_deadline_is_not_flagged(client):
    task = _task(client, due_date=(TODAY + timedelta(days=10)).isoformat())
    assert _defer(client, task["id"]).json()["still_overdue"] is False


def test_deferring_takes_it_off_todays_plan(client):
    """Otherwise the button looks like it did nothing."""
    task = _task(client)

    plan = client.get(f"{BASE}/planner/today").json()
    assert any(
        i["id"] == task["id"] for b in plan["blocks"] for i in b["items"]
    ), "the task should start on today's plan"

    _defer(client, task["id"])

    plan = client.get(f"{BASE}/planner/today").json()
    assert not any(i["id"] == task["id"] for b in plan["blocks"] for i in b["items"])


def test_a_task_deferred_to_today_is_still_todays(client):
    """Nothing to move it out of the way of — it was never pushed forward."""
    task = _task(client)
    client.patch(f"{BASE}/tasks/{task['id']}", json={"scheduled_for": TODAY.isoformat()})

    plan = client.get(f"{BASE}/planner/today").json()
    assert any(i["id"] == task["id"] for b in plan["blocks"] for i in b["items"])


def test_the_deferral_is_recorded_as_a_correction(client, db_session):
    task = _task(client)
    _defer(client, task["id"], suggested_block="morning")

    (row,) = db_session.query(PlanInteraction).all()
    assert row.item_id == task["id"]
    assert row.action == "deferred"
    assert row.suggested_block == "morning"
    # Deferring says nothing about when you actually do things.
    assert row.actual_block is None


def test_a_deferral_without_a_block_still_works(client, db_session):
    """The plan view knows the block; other callers may not, and the move
    matters more than the note."""
    task = _task(client)
    assert _defer(client, task["id"]).status_code == 200
    assert db_session.query(PlanInteraction).count() == 0


def test_deferring_a_finished_task_is_refused(client):
    task = _task(client)
    client.post(f"{BASE}/tasks/{task['id']}/complete")
    assert _defer(client, task["id"]).status_code == 409


def test_deferring_something_that_is_not_yours_is_a_404(client, other_client):
    task = _task(client)
    assert _defer(other_client, task["id"]).status_code == 404


def test_the_defer_window_is_bounded(client):
    task = _task(client)
    assert _defer(client, task["id"], days=0).status_code == 422
    assert _defer(client, task["id"], days=31).status_code == 422
    assert _defer(client, task["id"], days=30).status_code == 200


def test_deferring_twice_moves_it_twice(client):
    task = _task(client)
    _defer(client, task["id"])
    body = _defer(client, task["id"], days=3).json()
    assert body["scheduled_for"] == (TODAY + timedelta(days=3)).isoformat()
