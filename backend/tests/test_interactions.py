"""Corrections: recording them, and then acting on them.

The planner has always been able to state an opinion about when you should do
something. What it could never do is notice that you disagree — so a habit
placed in the morning stayed there forever, however many evenings you actually
did it in. These cover both halves: that a disagreement is stored as a fact,
and that enough of them move the plan.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.plan_interaction import PlanInteraction
from app.services.interaction_service import (
    MIN_CORRECTIONS,
    InteractionService,
    block_for_hour,
)

BASE = "/api/v1"
TODAY = date(2026, 6, 15)


def _record(svc: InteractionService, **kw):
    defaults = dict(
        item_kind="habit",
        item_id="habit-1",
        action="completed",
        suggested_block="morning",
        plan_date=TODAY,
        at_hour=9,
    )
    return svc.record(**{**defaults, **kw})


# --------------------------------------------------------------- the boundary
@pytest.mark.parametrize(
    "hour,block",
    [(0, "morning"), (8, "morning"), (11, "morning"), (12, "afternoon"),
     (16, "afternoon"), (17, "evening"), (23, "evening")],
)
def test_hours_map_to_the_planners_own_blocks(hour, block):
    """Same boundaries the planner draws, or the two would disagree about
    where the user was."""
    assert block_for_hour(hour) == block


# ---------------------------------------------------------------- recording
def test_following_the_plan_is_recorded_as_agreement(db_session):
    svc = InteractionService(db_session)
    row = _record(svc, suggested_block="morning", at_hour=9)

    assert row.actual_block == "morning"
    assert row.corrected is False


def test_doing_it_elsewhere_is_recorded_as_a_correction(db_session):
    svc = InteractionService(db_session)
    row = _record(svc, suggested_block="morning", at_hour=20)

    assert row.suggested_block == "morning"
    assert row.actual_block == "evening"
    assert row.corrected is True


def test_deferring_says_nothing_about_your_preferred_time(db_session):
    """Putting something off at 9am is not evidence that you do it at 9am."""
    svc = InteractionService(db_session)
    row = _record(svc, action="deferred", at_hour=9)

    assert row.actual_block is None
    assert row.corrected is False


def test_changing_your_mind_replaces_the_answer(db_session):
    """One settled outcome per item per day, not an event log."""
    svc = InteractionService(db_session)
    _record(svc, action="dismissed", at_hour=9)
    _record(svc, action="completed", at_hour=20)

    rows = db_session.query(PlanInteraction).all()
    assert len(rows) == 1
    assert rows[0].action == "completed"
    assert rows[0].actual_block == "evening"


def test_the_same_item_on_another_day_is_a_separate_fact(db_session):
    svc = InteractionService(db_session)
    _record(svc, plan_date=TODAY)
    _record(svc, plan_date=TODAY - timedelta(days=1))
    assert db_session.query(PlanInteraction).count() == 2


def test_nonsense_is_refused_rather_than_stored(db_session):
    """A typo'd block would become evidence for a slot that does not exist."""
    svc = InteractionService(db_session)
    with pytest.raises(ValueError):
        _record(svc, action="procrastinated")
    with pytest.raises(ValueError):
        _record(svc, suggested_block="lunchtime")
    with pytest.raises(ValueError):
        _record(svc, at_hour=25)
    assert db_session.query(PlanInteraction).count() == 0


# ----------------------------------------------------------------- learning
def _corrections(svc, n: int, block_hour: int = 20, item_id="habit-1", start=TODAY):
    for i in range(n):
        _record(
            svc,
            item_id=item_id,
            plan_date=start - timedelta(days=i),
            suggested_block="morning",
            at_hour=block_hour,
        )


def test_one_late_finish_does_not_move_anything(db_session):
    """A plan that flaps on a single data point is worse than a stubborn one."""
    svc = InteractionService(db_session)
    _corrections(svc, 1)
    assert svc.preferred_blocks(TODAY) == {}


def test_a_repeated_correction_becomes_a_preference(db_session):
    svc = InteractionService(db_session)
    _corrections(svc, MIN_CORRECTIONS)

    prefs = svc.preferred_blocks(TODAY)
    assert prefs["habit-1"] == ("evening", MIN_CORRECTIONS)


def test_a_split_record_is_not_a_preference(db_session):
    """Someone who does it whenever they can has no preferred slot, and
    inventing one for them would be noise dressed up as insight."""
    svc = InteractionService(db_session)
    for i in range(6):
        _record(
            svc,
            plan_date=TODAY - timedelta(days=i),
            at_hour=20 if i % 2 else 9,
        )
    assert svc.preferred_blocks(TODAY) == {}


def test_old_evidence_stops_counting(db_session):
    """A routine that changed last spring should not win today's argument."""
    svc = InteractionService(db_session)
    _corrections(svc, MIN_CORRECTIONS, start=TODAY - timedelta(days=120))
    assert svc.preferred_blocks(TODAY) == {}


def test_agreement_is_not_mistaken_for_a_correction(db_session):
    """Completing things where they were put should leave the plan alone."""
    svc = InteractionService(db_session)
    _corrections(svc, MIN_CORRECTIONS, block_hour=9)

    prefs = svc.preferred_blocks(TODAY)
    # An entry may exist — the evidence is one-sided — but it agrees with the
    # suggestion, so the planner will find nothing to move.
    assert prefs.get("habit-1", ("morning", 0))[0] == "morning"


def test_deferrals_never_become_preferences(db_session):
    svc = InteractionService(db_session)
    for i in range(MIN_CORRECTIONS + 2):
        _record(svc, action="deferred", plan_date=TODAY - timedelta(days=i), at_hour=20)
    assert svc.preferred_blocks(TODAY) == {}


# ------------------------------------------------------- the planner listens
def _habit(client, **kw):
    body = {"title": "Run", "frequency": "daily", "time_preference": "morning"}
    return client.post(f"{BASE}/habits", json={**body, **kw}).json()


def test_the_planner_moves_a_habit_you_keep_doing_later(client, db_session):
    habit = _habit(client)

    plan = client.get(f"{BASE}/planner/today").json()
    placed = {i["id"]: b["key"] for b in plan["blocks"] for i in b["items"]}
    assert placed[habit["id"]] == "morning", "starts where the user said"

    svc = InteractionService(db_session)
    today = date.today()
    for i in range(MIN_CORRECTIONS):
        svc.record(
            item_kind="habit",
            item_id=habit["id"],
            action="completed",
            suggested_block="morning",
            plan_date=today - timedelta(days=i),
            at_hour=20,
        )

    plan = client.get(f"{BASE}/planner/today").json()
    moved = {i["id"]: (b["key"], i["reason"]) for b in plan["blocks"] for i in b["items"]}
    block, reason = moved[habit["id"]]

    assert block == "evening"
    # It has to say why, or it looks like the app lost the setting.
    assert "usually finish this in the evening" in reason
    assert "moved here from the morning" in reason


def test_the_planner_is_unchanged_without_evidence(client):
    habit = _habit(client)
    plan = client.get(f"{BASE}/planner/today").json()
    placed = {i["id"]: b["key"] for b in plan["blocks"] for i in b["items"]}
    assert placed[habit["id"]] == "morning"


# -------------------------------------------------------------- the endpoint
def test_the_endpoint_records_what_the_plan_view_reports(client):
    res = client.post(
        f"{BASE}/planner/interactions",
        json={
            "item_kind": "habit",
            "item_id": "abc123",
            "action": "completed",
            "suggested_block": "morning",
            "suggested_rank": 0,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recorded"] is True
    assert body["item_id"] == "abc123"
    assert body["actual_block"] in {"morning", "afternoon", "evening"}


def test_the_endpoint_refuses_an_unknown_action(client):
    res = client.post(
        f"{BASE}/planner/interactions",
        json={
            "item_kind": "habit",
            "item_id": "abc123",
            "action": "teleported",
            "suggested_block": "morning",
        },
    )
    assert res.status_code == 422


def test_interactions_are_scoped_to_the_account(client, other_client, db_session):
    client.post(
        f"{BASE}/planner/interactions",
        json={
            "item_kind": "habit",
            "item_id": "mine",
            "action": "completed",
            "suggested_block": "morning",
        },
    )
    other_client.post(
        f"{BASE}/planner/interactions",
        json={
            "item_kind": "habit",
            "item_id": "theirs",
            "action": "completed",
            "suggested_block": "evening",
        },
    )

    # db_session is bound to the first account, so this is that account's view
    # of the table — and the intruder's row must simply not be in it.
    visible = {row.item_id for row in db_session.query(PlanInteraction).all()}
    assert visible == {"mine"}, "another account's corrections must not be readable"

    # Nor may they shape this account's plan.
    assert "theirs" not in InteractionService(db_session).preferred_blocks()
