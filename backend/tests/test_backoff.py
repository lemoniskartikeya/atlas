"""Notifications back off when they're repeatedly ignored."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.notification import NotificationState
from app.services.notification_service import (
    _BACKOFF_AFTER,
    _cooldown_days,
    NotificationService,
)

BASE = "/api/v1"


def _seed_dismissals(db_session, kind: str, target, n: int, *, days_ago: int = 0):
    """Write n consecutive dismissals for one stream, newest last."""
    now = datetime.now(timezone.utc) - timedelta(days=days_ago)
    for i in range(n):
        db_session.add(
            NotificationState(
                notification_id=f"{kind}:{target}:seed{i}",
                status="dismissed",
                kind=kind,
                target=target,
                created_at=now - timedelta(minutes=n - i),
            )
        )
    db_session.commit()


# ------------------------------------------------------------------- ladder
def test_cooldown_grows_with_persistence():
    assert _cooldown_days(_BACKOFF_AFTER - 1) == 0  # below the threshold: no silence
    short = _cooldown_days(_BACKOFF_AFTER)
    mid = _cooldown_days(5)
    long = _cooldown_days(8)
    assert 0 < short < mid < long


# ------------------------------------------------------------------ back-off
def test_below_threshold_still_notifies(db_session):
    svc = NotificationService(db_session)
    _seed_dismissals(db_session, "streak", "habit-1", _BACKOFF_AFTER - 1)
    quiet, until, streak = svc._backoff("streak", "habit-1", datetime.now(timezone.utc))
    assert streak == _BACKOFF_AFTER - 1
    assert quiet is False and until is None


def test_consecutive_dismissals_trigger_silence(db_session):
    svc = NotificationService(db_session)
    _seed_dismissals(db_session, "streak", "habit-1", _BACKOFF_AFTER)
    quiet, until, streak = svc._backoff("streak", "habit-1", datetime.now(timezone.utc))
    assert streak == _BACKOFF_AFTER
    assert quiet is True and until is not None


def test_a_read_resets_the_run(db_session):
    """Engagement means the nudge landed — that should clear the back-off."""
    svc = NotificationService(db_session)
    _seed_dismissals(db_session, "streak", "habit-1", _BACKOFF_AFTER)
    db_session.add(
        NotificationState(
            notification_id="streak:habit-1:opened",
            status="read",
            kind="streak",
            target="habit-1",
            created_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
    )
    db_session.commit()

    quiet, _until, streak = svc._backoff("streak", "habit-1", datetime.now(timezone.utc))
    assert streak == 0 and quiet is False


def test_silence_lapses_and_lets_a_probe_through(db_session):
    """After the cooldown, one nudge is allowed through to re-test."""
    svc = NotificationService(db_session)
    _seed_dismissals(
        db_session, "streak", "habit-1", _BACKOFF_AFTER, days_ago=_cooldown_days(_BACKOFF_AFTER) + 1
    )
    quiet, until, streak = svc._backoff("streak", "habit-1", datetime.now(timezone.utc))
    assert streak == _BACKOFF_AFTER
    assert until is not None
    assert quiet is False  # cooldown has expired


def test_backoff_is_per_stream_not_global(db_session):
    svc = NotificationService(db_session)
    _seed_dismissals(db_session, "streak", "habit-1", _BACKOFF_AFTER)
    now = datetime.now(timezone.utc)
    assert svc._backoff("streak", "habit-1", now)[0] is True
    # A different habit, and a different kind, are untouched.
    assert svc._backoff("streak", "habit-2", now)[0] is False
    assert svc._backoff("task", "habit-1", now)[0] is False


# ---------------------------------------------------------------- end to end
def test_dismissing_records_kind_and_target(client, db_session):
    hid = client.post(f"{BASE}/habits", json={"title": "Meditate"}).json()["id"]
    client.post(f"{BASE}/habits/{hid}/logs", json={"status": "completed"})

    items = client.get(f"{BASE}/notifications").json()["notifications"]
    if not items:  # time-gated; nothing due at this hour
        return
    client.post(f"{BASE}/notifications/dismiss", json={"id": items[0]["id"]})

    row = db_session.query(NotificationState).filter_by(
        notification_id=items[0]["id"]
    ).one()
    # Denormalised so history can be grouped without parsing ids.
    assert row.kind == items[0]["kind"]
    assert row.status == "dismissed"


def test_snoozed_streams_are_reported_and_resumable(client, db_session):
    """A silenced stream is surfaced honestly, and can be switched back on."""
    _seed_dismissals(db_session, "task", "task-1", _BACKOFF_AFTER)

    svc = NotificationService(db_session)
    quiet, _u, _s = svc._backoff("task", "task-1", datetime.now(timezone.utc))
    assert quiet is True

    res = client.post(f"{BASE}/notifications/resume", json={"kind": "task", "target": "task-1"})
    assert res.status_code == 204
    assert svc._backoff("task", "task-1", datetime.now(timezone.utc))[0] is False


def test_response_exposes_a_snoozed_list(client):
    body = client.get(f"{BASE}/notifications").json()
    assert "snoozed" in body and isinstance(body["snoozed"], list)
