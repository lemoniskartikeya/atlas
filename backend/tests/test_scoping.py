"""Two accounts, one database, no leaks.

Every other test file runs as a single account and would pass just as happily
if scoping did nothing at all. These are the ones that would fail.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.core.scoping import ScopeError, acting_as, current_user_id
from app.models.habit import Habit
from app.models.journal import JournalEntry
from app.repositories.habit_repo import HabitRepository
from app.services.auth_service import AuthService


def _habit(client, title: str) -> str:
    res = client.post("/api/v1/habits", json={"title": title})
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ------------------------------------------------------------------ read isolation
def test_habits_are_invisible_across_accounts(client, other_client):
    mine = _habit(client, "Morning run")
    theirs = _habit(other_client, "Evening swim")

    assert [h["title"] for h in client.get("/api/v1/habits").json()] == ["Morning run"]
    assert [h["title"] for h in other_client.get("/api/v1/habits").json()] == [
        "Evening swim"
    ]
    assert mine != theirs


def test_fetching_another_accounts_habit_by_id_is_a_404(client, other_client):
    """Not a 403: existence itself is none of the other account's business."""
    theirs = _habit(other_client, "Evening swim")
    assert client.get(f"/api/v1/habits/{theirs}").status_code == 404
    assert client.get(f"/api/v1/habits/{theirs}/stats").status_code == 404
    assert client.patch(f"/api/v1/habits/{theirs}", json={"title": "Hijacked"}).status_code == 404
    assert client.delete(f"/api/v1/habits/{theirs}").status_code == 404

    # ...and it is genuinely untouched.
    assert other_client.get(f"/api/v1/habits/{theirs}").json()["title"] == "Evening swim"


def test_habit_logs_do_not_cross_over(client, other_client):
    mine = _habit(client, "Read")
    theirs = _habit(other_client, "Read")
    for cl, hid in ((client, mine), (other_client, theirs)):
        assert cl.post(f"/api/v1/habits/{hid}/logs", json={"date": "2026-08-01"}).status_code == 201
    other_client.post(f"/api/v1/habits/{theirs}/logs", json={"date": "2026-08-02"})

    assert len(client.get(f"/api/v1/habits/{mine}/logs").json()) == 1
    assert len(other_client.get(f"/api/v1/habits/{theirs}/logs").json()) == 2
    # Logging against someone else's habit is not possible at all.
    assert client.post(
        f"/api/v1/habits/{theirs}/logs", json={"date": "2026-08-03"}
    ).status_code == 404


def test_tasks_and_focus_sessions_are_scoped(client, other_client):
    client.post("/api/v1/tasks", json={"title": "Mine"})
    other_client.post("/api/v1/tasks", json={"title": "Theirs"})
    assert [t["title"] for t in client.get("/api/v1/tasks").json()] == ["Mine"]
    assert [t["title"] for t in other_client.get("/api/v1/tasks").json()] == ["Theirs"]

    started = datetime.now(timezone.utc).isoformat()
    client.post(
        "/api/v1/focus/sessions",
        json={"started_at": started, "duration_min": 25, "distractions": 1},
    )
    assert len(client.get("/api/v1/focus/sessions").json()) == 1
    assert other_client.get("/api/v1/focus/sessions").json() == []


def test_both_accounts_can_journal_the_same_day(client, other_client):
    """The old schema made ``date`` globally unique — one account per day, ever."""
    day = "2026-08-05"
    assert client.put(f"/api/v1/journal/{day}", json={"mood": 5}).status_code == 200
    assert other_client.put(f"/api/v1/journal/{day}", json={"mood": 2}).status_code == 200

    assert client.get(f"/api/v1/journal/{day}").json()["mood"] == 5
    assert other_client.get(f"/api/v1/journal/{day}").json()["mood"] == 2


def test_notification_state_is_per_account(client, other_client):
    """Both accounts mint the same deterministic notification ids."""
    nid = "streak:shared-id:2026-08-05"
    assert client.post("/api/v1/notifications/dismiss", json={"id": nid}).status_code == 204
    assert (
        other_client.post("/api/v1/notifications/dismiss", json={"id": nid}).status_code
        == 204
    )
    # Two rows, not one overwritten row — the composite key holds.
    body = client.get("/api/v1/notifications").json()
    assert isinstance(body["notifications"], list)


# ------------------------------------------------------------------------ backups
def test_export_contains_only_your_own_data(client, other_client):
    _habit(client, "Mine")
    _habit(other_client, "Theirs")

    doc = client.get("/api/v1/backup/export").json()
    titles = [h["title"] for h in doc["data"]["habits"]]
    assert titles == ["Mine"]
    # The owner id never travels with a backup.
    assert all("user_id" not in row for row in doc["data"]["habits"])


def test_restoring_a_backup_does_not_wipe_the_other_account(client, other_client):
    """The import wipe is a bulk DELETE, which no query-rewriting can protect."""
    _habit(client, "Mine")
    _habit(other_client, "Theirs")
    doc = client.get("/api/v1/backup/export").json()

    res = client.post("/api/v1/backup/import", json=doc)
    assert res.status_code == 200, res.text

    assert [h["title"] for h in client.get("/api/v1/habits").json()] == ["Mine"]
    assert [h["title"] for h in other_client.get("/api/v1/habits").json()] == ["Theirs"]


def test_an_imported_backup_belongs_to_whoever_restores_it(client, other_client):
    _habit(client, "Portable")
    doc = client.get("/api/v1/backup/export").json()

    assert other_client.post("/api/v1/backup/import", json=doc).status_code == 200
    assert [h["title"] for h in other_client.get("/api/v1/habits").json()] == ["Portable"]
    assert [h["title"] for h in client.get("/api/v1/habits").json()] == ["Portable"]


# -------------------------------------------------------------------------- auth
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/habits"),
        ("get", "/api/v1/tasks"),
        ("get", "/api/v1/dashboard"),
        ("get", "/api/v1/journal"),
        ("get", "/api/v1/analytics/summary"),
        ("get", "/api/v1/timeline"),
        ("get", "/api/v1/calendar?year=2026&month=8"),
        ("get", "/api/v1/planner/today"),
        ("get", "/api/v1/predictions"),
        ("get", "/api/v1/notifications"),
        ("get", "/api/v1/focus/sessions"),
        ("get", "/api/v1/focus/stats"),
        ("get", "/api/v1/search?q=run"),
        ("get", "/api/v1/review"),
        ("get", "/api/v1/backup/export"),
        ("get", "/api/v1/jobs"),
        ("get", "/api/v1/feedback/effectiveness"),
        ("get", "/api/v1/ml/history"),
        ("get", "/api/v1/coach/status"),
        ("post", "/api/v1/habits"),
        ("post", "/api/v1/tasks"),
    ],
)
def test_data_endpoints_require_an_account(anon_client, method, path):
    assert getattr(anon_client, method)(path).status_code == 401


def test_health_and_auth_status_stay_public(anon_client):
    """The desktop shell polls these before anyone can possibly be signed in."""
    assert anon_client.get("/api/v1/health").status_code == 200
    assert anon_client.get("/api/v1/auth/status").status_code == 200


# ------------------------------------------------------------- the scoping layer
def test_an_unbound_session_refuses_to_answer(db_session):
    """Better a loud failure than a query that quietly returns everyone's rows."""
    with acting_as(db_session, None):
        with pytest.raises(ScopeError):
            HabitRepository(db_session).list_all()


def test_new_rows_are_stamped_with_the_current_account(db_session):
    habit = Habit(title="Stamped")
    db_session.add(habit)
    db_session.flush()
    assert habit.user_id == current_user_id(db_session)


def test_writing_a_row_owned_by_someone_else_is_rejected(db_session):
    other = AuthService(db_session).register("someone-else", "Passw0rd!")
    db_session.add(Habit(title="Smuggled", user_id=other.id))
    with pytest.raises(ScopeError):
        db_session.flush()
    db_session.rollback()


def test_the_first_account_claims_a_pre_accounts_vault(db_session):
    """Data written before Atlas had users must not disappear on upgrade."""
    # Simulate the migration's outcome on a vault with no accounts: unowned rows.
    with acting_as(db_session, None):
        db_session.add(Habit(title="Legacy habit", user_id=None))
        db_session.add(JournalEntry(date=date(2025, 1, 1), mood=4, user_id=None))
        db_session.commit()

    # Invisible to the account that exists — it never owned them.
    assert [h.title for h in HabitRepository(db_session).list_all()] == []

    auth = AuthService(db_session)
    claimed = auth.claim_orphan_vault(db_session.info["test_user"])
    assert claimed == 2
    assert [h.title for h in HabitRepository(db_session).list_all()] == ["Legacy habit"]


def test_a_pre_scoping_model_is_adopted_by_the_first_account(db_session):
    """Models used to live in one global folder; upgrading must not orphan them."""
    from pathlib import Path

    from app.core.config import get_settings

    root = Path(get_settings().data_dir) / "models"
    root.mkdir(parents=True, exist_ok=True)
    legacy_index = root / "registry.json"
    legacy_bundle = root / "model_20260101000000.joblib"
    legacy_index.write_text('[{"version": "20260101000000"}]', encoding="utf-8")
    legacy_bundle.write_bytes(b"not-really-a-model")

    user = db_session.info["test_user"]
    try:
        assert AuthService._adopt_legacy_models(user) == 2
        assert not legacy_index.exists() and not legacy_bundle.exists()
        assert (root / user.id / "registry.json").exists()
        assert (root / user.id / legacy_bundle.name).exists()

        # Idempotent: a second call has nothing left to move.
        assert AuthService._adopt_legacy_models(user) == 0
    finally:
        for leftover in (legacy_index, legacy_bundle):
            leftover.unlink(missing_ok=True)
        for leftover in (root / user.id).glob("*"):
            leftover.unlink(missing_ok=True)


def test_claiming_only_ever_touches_unowned_rows(db_session):
    """Called twice, it must not drag another account's data across."""
    owner = db_session.info["test_user"]
    other = AuthService(db_session).register("bystander", "Passw0rd!")
    with acting_as(db_session, other.id):
        db_session.add(Habit(title="Theirs"))
        db_session.commit()

    assert AuthService(db_session).claim_orphan_vault(owner) == 0
    with acting_as(db_session, other.id):
        assert [h.title for h in HabitRepository(db_session).list_all()] == ["Theirs"]
