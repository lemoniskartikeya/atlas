"""The task model: will this land on time?

The habit model was the only one for a long time, so tasks had no coverage at
all. The risk in adding them is not that the model is weak — on a personal
dataset it always will be — it is that it looks strong because it was shown
something it could not have known. Most of what follows is about that.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from app.domain.enums import Priority, TaskStatus
from app.learning import task_features
from app.models.task import Task

BASE = "/api/v1"
#: A fixed day for the feature tests, which pass it in explicitly.
TODAY = date(2026, 6, 15)
#: Training goes through MLService, which reads the real clock the way it does
#: in production — so those tests build their history relative to this instead.
REAL_TODAY = date.today()
LOCAL = datetime.now().astimezone().tzinfo


def _task(session, **kw) -> Task:
    """A task straight into the session, so timestamps can be set precisely."""
    defaults = dict(
        title="Something",
        status=TaskStatus.TODO,
        priority=Priority.MEDIUM,
        energy_required=3,
        focus_required=3,
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
    )
    task = Task(**{**defaults, **kw})
    session.add(task)
    session.flush()
    return task


def _feature(vec, name: str) -> float:
    return float(vec[task_features.FEATURE_NAMES.index(name)])


# --------------------------------------------------------------- the outcome
def test_finished_before_the_due_date_is_on_time(db_session):
    t = _task(
        db_session,
        status=TaskStatus.DONE,
        due_date=TODAY - timedelta(days=3),
        completed_at=datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc),
    )
    assert task_features.outcome(t, TODAY) == 1


def test_finished_on_the_due_date_itself_counts(db_session):
    """The deadline is the end of that day, not the start of it.

    Late in the evening *where the user is*: stored UTC, but attributed to the
    local day, so someone finishing at 23:30 in Delhi is on time rather than a
    day late.
    """
    due = TODAY - timedelta(days=3)
    t = _task(
        db_session,
        status=TaskStatus.DONE,
        due_date=due,
        completed_at=datetime(2026, 6, 12, 23, 30, tzinfo=LOCAL).astimezone(timezone.utc),
    )
    assert task_features.outcome(t, TODAY) == 1


def test_a_task_finished_just_after_local_midnight_is_late(db_session):
    """The other side of the same line, so the rule is pinned from both ends."""
    due = TODAY - timedelta(days=3)
    t = _task(
        db_session,
        status=TaskStatus.DONE,
        due_date=due,
        completed_at=datetime(2026, 6, 13, 0, 30, tzinfo=LOCAL).astimezone(timezone.utc),
    )
    assert task_features.outcome(t, TODAY) == 0


def test_finished_late_is_still_a_miss(db_session):
    t = _task(
        db_session,
        status=TaskStatus.DONE,
        due_date=TODAY - timedelta(days=5),
        completed_at=datetime(2026, 6, 13, 9, 0, tzinfo=timezone.utc),
    )
    assert task_features.outcome(t, TODAY) == 0


def test_an_open_task_past_its_date_is_a_miss(db_session):
    t = _task(db_session, due_date=TODAY - timedelta(days=1))
    assert task_features.outcome(t, TODAY) == 0


def test_an_open_task_due_later_is_not_settled(db_session):
    """Counting it as a miss today would train the model that every task fails."""
    assert task_features.outcome(_task(db_session, due_date=TODAY), TODAY) is None
    assert (
        task_features.outcome(_task(db_session, due_date=TODAY + timedelta(days=2)), TODAY)
        is None
    )


def test_a_task_with_no_due_date_teaches_nothing(db_session):
    """There is no 'on time' without a time."""
    assert task_features.outcome(_task(db_session, due_date=None), TODAY) is None
    assert (
        task_features.outcome(
            _task(
                db_session,
                status=TaskStatus.DONE,
                due_date=None,
                completed_at=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc),
            ),
            TODAY,
        )
        is None
    )


def test_a_cancelled_task_is_not_a_failure(db_session):
    """Deciding not to do something is a decision. Training on it would teach
    the model that pruning your list is the same as letting it rot."""
    t = _task(db_session, status=TaskStatus.CANCELLED, due_date=TODAY - timedelta(days=4))
    assert task_features.outcome(t, TODAY) is None


# ------------------------------------------------------------------ leakage
def test_the_first_task_has_no_track_record(db_session):
    _task(
        db_session,
        status=TaskStatus.DONE,
        due_date=TODAY - timedelta(days=10),
        completed_at=datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc),
    )
    X, y, _dates = task_features.build_training(db_session, TODAY)

    assert len(y) == 1
    assert np.isnan(_feature(X[0], "recent_rate_7")), "nothing preceded it to average"
    assert _feature(X[0], "on_time_streak") == 0.0


def test_the_track_record_only_looks_backwards(db_session):
    """Row i must see rows 0..i-1 and nothing after — the whole point.

    Three tasks, in due-date order: on time, on time, missed. The third row's
    rate must be 1.0, computed from the two before it, and must not be dragged
    down by its own outcome.
    """
    for i, (offset, ok) in enumerate([(20, True), (15, True), (10, False)]):
        due = TODAY - timedelta(days=offset)
        _task(
            db_session,
            title=f"t{i}",
            due_date=due,
            status=TaskStatus.DONE if ok else TaskStatus.TODO,
            completed_at=(
                datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc)
                if ok
                else None
            ),
        )

    X, y, dates = task_features.build_training(db_session, TODAY)
    assert list(y) == [1, 1, 0]
    assert dates == sorted(dates), "examples must be ordered by when they settled"

    assert np.isnan(_feature(X[0], "recent_rate_7"))
    assert _feature(X[1], "recent_rate_7") == 1.0
    assert _feature(X[2], "recent_rate_7") == 1.0
    assert _feature(X[2], "on_time_streak") == 2.0


def test_a_run_of_on_time_tasks_breaks_on_a_miss(db_session):
    plan = [(30, True), (25, True), (20, False), (15, True)]
    for i, (offset, ok) in enumerate(plan):
        due = TODAY - timedelta(days=offset)
        _task(
            db_session,
            title=f"t{i}",
            due_date=due,
            status=TaskStatus.DONE if ok else TaskStatus.TODO,
            completed_at=(
                datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc)
                if ok
                else None
            ),
        )

    X, _y, _d = task_features.build_training(db_session, TODAY)
    assert _feature(X[2], "on_time_streak") == 2.0   # two before the miss
    assert _feature(X[3], "on_time_streak") == 0.0   # reset by it


def test_the_backlog_count_is_as_of_that_day_not_now(db_session):
    """Two tasks: one closed long before the other came due, so it must not be
    counted in that one's backlog — and one still open, which must be."""
    early_due = TODAY - timedelta(days=20)
    _task(
        db_session,
        title="closed early",
        status=TaskStatus.DONE,
        due_date=early_due,
        completed_at=datetime.combine(early_due, datetime.min.time(), tzinfo=timezone.utc),
    )
    _task(db_session, title="still open", due_date=TODAY + timedelta(days=30))
    _task(db_session, title="subject", due_date=TODAY - timedelta(days=5))

    X, _y, _d = task_features.build_training(db_session, TODAY)
    # Only the settled ones become rows: "closed early" and "subject".
    assert len(X) == 2
    subject = X[1]
    # On the subject's due date: itself + "still open". Not "closed early".
    assert _feature(subject, "open_backlog") == 2.0


def test_a_task_created_after_another_is_not_in_its_past_backlog(db_session):
    due = TODAY - timedelta(days=10)
    _task(db_session, title="subject", due_date=due)
    _task(
        db_session,
        title="added later",
        due_date=TODAY + timedelta(days=5),
        created_at=datetime(2026, 6, 12, 9, 0, tzinfo=timezone.utc),
    )

    X, _y, _d = task_features.build_training(db_session, TODAY)
    assert len(X) == 1
    assert _feature(X[0], "open_backlog") == 1.0, "only the subject existed then"


def test_journal_signal_comes_from_the_day_before(db_session):
    from app.models.journal import JournalEntry

    due = TODAY - timedelta(days=5)
    db_session.add(JournalEntry(date=due - timedelta(days=1), mood=4, energy=2, sleep_hours=7.5))
    db_session.add(JournalEntry(date=due, mood=1, energy=1, sleep_hours=3.0))
    _task(db_session, due_date=due)
    db_session.flush()

    X, _y, _d = task_features.build_training(db_session, TODAY)
    assert _feature(X[0], "mood_prev") == 4.0, "the day itself would be hindsight"
    assert _feature(X[0], "sleep_prev") == 7.5


# ----------------------------------------------------------------- features
def test_lead_time_is_the_notice_you_gave_yourself(db_session):
    _task(
        db_session,
        due_date=date(2026, 6, 8),
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
    )
    X, _y, _d = task_features.build_training(db_session, TODAY)
    assert _feature(X[0], "lead_time_days") == 7.0


def test_a_task_added_after_it_was_due_reads_as_negative_notice(db_session):
    _task(
        db_session,
        due_date=date(2026, 5, 28),
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
    )
    X, _y, _d = task_features.build_training(db_session, TODAY)
    assert _feature(X[0], "lead_time_days") == -4.0


def test_a_subtask_knows_it_is_one(db_session):
    """A step inside a bigger piece of work behaves differently from a
    standalone task, so the model gets to see which it is."""
    parent = _task(db_session, title="parent", due_date=TODAY - timedelta(days=3))
    _task(db_session, title="child", parent_id=parent.id, due_date=TODAY - timedelta(days=2))
    db_session.flush()
    db_session.refresh(parent)

    X, _y, _d = task_features.build_training(db_session, TODAY)
    parent_row, child_row = X  # ordered by due date: parent, then child

    assert _feature(parent_row, "is_subtask") == 0.0
    assert _feature(parent_row, "n_subtasks") == 1.0
    assert _feature(child_row, "is_subtask") == 1.0
    assert _feature(child_row, "n_subtasks") == 0.0


def test_missing_estimates_are_recorded_as_missing_not_zero_effort(db_session):
    _task(db_session, due_date=TODAY - timedelta(days=3), estimated_effort_min=None)
    X, _y, _d = task_features.build_training(db_session, TODAY)
    assert _feature(X[0], "has_estimate") == 0.0


def test_the_feature_vector_matches_its_names(db_session):
    _task(db_session, due_date=TODAY - timedelta(days=3))
    X, _y, _d = task_features.build_training(db_session, TODAY)
    assert X.shape[1] == len(task_features.FEATURE_NAMES)


def test_an_empty_account_produces_an_empty_frame(db_session):
    X, y, dates = task_features.build_training(db_session, TODAY)
    assert X.shape == (0, len(task_features.FEATURE_NAMES))
    assert len(y) == 0 and dates == []


# ---------------------------------------------------------------- inference
def test_inference_covers_open_tasks_that_can_still_be_made(db_session):
    _task(db_session, title="due today", due_date=TODAY)
    _task(db_session, title="due later", due_date=TODAY + timedelta(days=3))
    rows = task_features.build_inference(db_session, TODAY)
    assert {t.title for t, _v in rows} == {"due today", "due later"}


def test_an_overdue_task_is_not_predicted_about(db_session):
    """Its outcome is already decided; a probability would be theatre."""
    _task(db_session, title="overdue", due_date=TODAY - timedelta(days=1))
    assert task_features.build_inference(db_session, TODAY) == []


def test_finished_and_undated_tasks_are_not_predicted_about(db_session):
    _task(
        db_session,
        title="done",
        status=TaskStatus.DONE,
        due_date=TODAY + timedelta(days=1),
        completed_at=datetime(2026, 6, 14, 9, 0, tzinfo=timezone.utc),
    )
    _task(db_session, title="someday", due_date=None)
    assert task_features.build_inference(db_session, TODAY) == []


def test_inference_uses_the_record_up_to_today(db_session):
    for i in range(3):
        due = TODAY - timedelta(days=10 - i)
        _task(
            db_session,
            title=f"past{i}",
            status=TaskStatus.DONE,
            due_date=due,
            completed_at=datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc),
        )
    _task(db_session, title="upcoming", due_date=TODAY + timedelta(days=2))

    (task, vec), = task_features.build_inference(db_session, TODAY)
    assert task.title == "upcoming"
    assert _feature(vec, "recent_rate_7") == 1.0
    assert _feature(vec, "on_time_streak") == 3.0


# ------------------------------------------------------- training end to end
def _history(session, n: int, today: date = REAL_TODAY) -> None:
    """A believable record: high-priority tasks mostly land, low-priority ones
    mostly don't, so there is a real signal for the model to find."""
    for i in range(n):
        due = today - timedelta(days=n - i + 1)
        on_time = i % 3 != 0
        _task(
            session,
            title=f"task {i}",
            priority=Priority.HIGH if on_time else Priority.LOW,
            due_date=due,
            status=TaskStatus.DONE if on_time else TaskStatus.TODO,
            completed_at=(
                datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc)
                if on_time
                else None
            ),
            created_at=datetime.combine(
                due - timedelta(days=3), datetime.min.time(), tzinfo=timezone.utc
            ),
        )


def test_training_refuses_when_there_is_too_little_to_learn_from(db_session):
    from app.services.ml_service import MIN_TASK_SAMPLES, MLService

    _history(db_session, 5)
    out = MLService(db_session).train_tasks()

    assert out["trained"] is False
    assert out["n_samples"] == 5
    assert str(MIN_TASK_SAMPLES) in out["reason"]


def test_training_refuses_when_every_task_landed(db_session):
    """A model fitted on one outcome predicts that outcome forever."""
    from app.services.ml_service import MLService

    for i in range(40):
        due = REAL_TODAY - timedelta(days=45 - i)
        _task(
            db_session,
            title=f"t{i}",
            due_date=due,
            status=TaskStatus.DONE,
            completed_at=datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc),
        )

    out = MLService(db_session).train_tasks()
    assert out["trained"] is False


def test_a_model_trains_and_then_predicts(db_session):
    from app.services.ml_service import MLService

    _history(db_session, 45)
    _task(
        db_session,
        title="upcoming",
        priority=Priority.HIGH,
        due_date=REAL_TODAY + timedelta(days=2),
    )

    svc = MLService(db_session)
    assert svc.task_status()["trained"] is False

    out = svc.train_tasks()
    assert out["trained"] is True, out
    assert out["n_samples"] == 45
    assert svc.task_status()["trained"] is True

    got = svc.predict_tasks()
    assert got["trained"] is True
    (row,) = got["predictions"]
    assert row["task_id"] and row["title"] == "upcoming"
    assert 0.0 <= row["probability"] <= 1.0
    assert row["explanation"].strip()


def test_the_task_model_does_not_disturb_the_habit_model(db_session):
    """Both live in one account's folder; each must keep its own index."""
    from app.learning import registry
    from app.services.ml_service import MLService

    _history(db_session, 45)
    svc = MLService(db_session)
    assert svc.train_tasks()["trained"] is True

    assert svc.status()["trained"] is False, "training tasks must not fake a habit model"
    assert registry.latest_meta(svc.user_id, registry.TASK) is not None
    assert registry.latest_meta(svc.user_id) is None


def test_predictions_are_unavailable_until_something_is_trained(db_session):
    from app.services.ml_service import MLService

    out = MLService(db_session).predict_tasks(TODAY)
    assert out == {"trained": False, "predictions": []}


# --------------------------------------------------------------- API surface
def test_the_endpoints_are_honest_before_training(client):
    assert client.get(f"{BASE}/ml/tasks/status").json()["trained"] is False
    body = client.get(f"{BASE}/ml/tasks/predictions").json()
    assert body["trained"] is False and body["predictions"] == []


def test_training_through_the_api_says_why_it_declined(client):
    body = client.post(f"{BASE}/ml/tasks/train").json()
    assert body["trained"] is False
    assert body["reason"]


def test_the_gateway_stays_quiet_without_a_model(db_session):
    from app.services import ml_gateway

    assert ml_gateway.task_predictions(db_session) == (None, None)


def test_the_gateway_serves_predictions_once_trained(db_session):
    from app.services import ml_gateway
    from app.services.ml_service import MLService

    _history(db_session, 45)
    _task(db_session, title="upcoming", due_date=REAL_TODAY + timedelta(days=2))
    assert MLService(db_session).train_tasks()["trained"] is True

    by_id, reliability = ml_gateway.task_predictions(db_session)
    assert by_id is not None and len(by_id) == 1
    (row,) = by_id.values()
    assert "probability" in row and "explanation" in row
    assert reliability is None or 0.0 <= reliability <= 1.0


# -------------------------------------------------------------------- job
def test_the_retrain_job_explains_itself_while_waiting(db_session):
    from app.services.jobs import retrain_task_model

    _history(db_session, 5)
    result = retrain_task_model(db_session)
    assert result.status == "skipped"
    assert "due date" in result.detail


def test_the_retrain_job_trains_when_there_is_enough(db_session):
    from app.services.jobs import retrain_task_model

    _history(db_session, 45)
    result = retrain_task_model(db_session)
    assert result.status == "ok", result.detail
    assert "45 tasks" in result.detail


def test_the_retrain_job_waits_for_new_evidence(db_session):
    from app.services.jobs import retrain_task_model

    _history(db_session, 45)
    assert retrain_task_model(db_session).status == "ok"

    again = retrain_task_model(db_session)
    assert again.status == "skipped"
    assert "come due since the last model" in again.detail


@pytest.mark.parametrize("kind", ["habit", "task"])
def test_each_model_kind_has_its_own_files(kind):
    from app.learning import registry

    path = registry.registry_path("some-user", kind)
    assert path.name == ("registry.json" if kind == "habit" else "registry_task.json")


# ------------------------------------------------- does it actually learn?
def test_a_planted_pattern_is_found(db_session):
    """The pipeline has to be able to learn something, or none of the rest matters.

    Rule in the data: tasks given several days' notice land, same-day ones
    don't. Nothing else varies, so a working pipeline should recover both the
    rule and the reason.
    """
    from app.learning import registry
    from app.services.ml_service import MLService

    for i in range(80):
        due = REAL_TODAY - timedelta(days=90 - i)
        notice = 5 if i % 2 == 0 else 0
        on_time = notice >= 3
        _task(
            db_session,
            title=f"t{i}",
            due_date=due,
            created_at=datetime.combine(
                due - timedelta(days=notice), datetime.min.time(), tzinfo=timezone.utc
            ),
            status=TaskStatus.DONE if on_time else TaskStatus.TODO,
            completed_at=(
                datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc)
                if on_time
                else None
            ),
        )

    svc = MLService(db_session)
    out = svc.train_tasks()
    assert out["trained"] is True
    assert out["metrics"]["roc_auc"] >= 0.9, out["metrics"]

    bundle = registry.latest_bundle(svc.user_id, registry.TASK)
    assert bundle["importances"][0]["feature"] == "lead_time_days"


def test_noise_does_not_produce_a_confident_model(db_session):
    """The leak detector.

    Outcomes here are coin flips, unrelated to any feature. An honest pipeline
    scores near chance. If a label ever leaked into the features — through the
    rolling history, the backlog count, or the ordering — this is where it
    would show up, as a model that is suspiciously good at predicting noise.
    """
    import random

    from app.services.ml_service import MLService

    rng = random.Random(11)
    for i in range(150):
        due = REAL_TODAY - timedelta(days=200 - i)
        on_time = rng.random() < 0.5
        _task(
            db_session,
            title=f"t{i}",
            due_date=due,
            priority=rng.choice(list(Priority)),
            energy_required=rng.randint(1, 5),
            focus_required=rng.randint(1, 5),
            estimated_effort_min=rng.choice([None, 15, 30, 60]),
            created_at=datetime.combine(
                due - timedelta(days=rng.randint(0, 10)),
                datetime.min.time(),
                tzinfo=timezone.utc,
            ),
            status=TaskStatus.DONE if on_time else TaskStatus.TODO,
            completed_at=(
                datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc)
                if on_time
                else None
            ),
        )

    metrics = MLService(db_session).train_tasks()["metrics"]
    assert metrics["roc_auc"] <= 0.75, f"too good on pure noise — something leaks: {metrics}"


# ------------------------------------------------------- deadline risk on the plan
def test_no_deadline_claims_without_a_basis(db_session):
    """A brand-new account with one dated task knows nothing about you yet."""
    from app.services.prediction_service import PredictionService

    _task(db_session, title="write report", due_date=REAL_TODAY + timedelta(days=2))
    report = PredictionService(db_session).build(REAL_TODAY)
    assert report.deadline_risks == []


def test_deadline_risk_falls_back_to_your_own_record(db_session):
    """No model trained, but a track record of missing — so say so, and say why."""
    from app.services.prediction_service import PredictionService

    for i in range(10):
        due = REAL_TODAY - timedelta(days=20 - i)
        _task(db_session, title=f"missed {i}", due_date=due)  # all left open, all late
    _task(db_session, title="write report", due_date=REAL_TODAY)

    report = PredictionService(db_session).build(REAL_TODAY)
    (risk,) = report.deadline_risks

    assert risk.title == "write report"
    assert risk.days_left == 0
    assert risk.level == "high"
    assert risk.probability is None, "no model — this is the heuristic path"
    assert "Due today" in risk.reason
    assert "0% of your last 10 deadlines" in risk.reason


def test_a_reliable_record_produces_no_warning(db_session):
    from app.services.prediction_service import PredictionService

    for i in range(10):
        due = REAL_TODAY - timedelta(days=20 - i)
        _task(
            db_session,
            title=f"landed {i}",
            due_date=due,
            status=TaskStatus.DONE,
            completed_at=datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc),
        )
    _task(db_session, title="write report", due_date=REAL_TODAY)

    assert PredictionService(db_session).build(REAL_TODAY).deadline_risks == []


def test_a_distant_deadline_is_less_urgent_than_the_same_one_today(db_session):
    """Same odds, more room to act — the warning should fade with distance."""
    from app.services.prediction_service import PredictionService

    for i in range(10):
        due = REAL_TODAY - timedelta(days=20 - i)
        if i % 2:
            _task(db_session, title=f"missed {i}", due_date=due)
        else:
            _task(
                db_session,
                title=f"landed {i}",
                due_date=due,
                status=TaskStatus.DONE,
                completed_at=datetime.combine(due, datetime.min.time(), tzinfo=timezone.utc),
            )
    _task(db_session, title="today", due_date=REAL_TODAY)
    _task(db_session, title="next week", due_date=REAL_TODAY + timedelta(days=7))

    risks = {r.title: r.risk for r in PredictionService(db_session).build(REAL_TODAY).deadline_risks}
    assert risks.get("today", 0) > risks.get("next week", 0)


def test_overdue_tasks_are_not_reported_as_at_risk(db_session):
    """They have already slipped. Calling that a risk is a lie about tense."""
    from app.services.prediction_service import PredictionService

    for i in range(10):
        _task(db_session, title=f"missed {i}", due_date=REAL_TODAY - timedelta(days=20 - i))
    _task(db_session, title="already late", due_date=REAL_TODAY - timedelta(days=1))

    titles = {r.title for r in PredictionService(db_session).build(REAL_TODAY).deadline_risks}
    assert "already late" not in titles


def test_deadline_risk_prefers_the_model_when_one_exists(db_session):
    from app.services.ml_service import MLService
    from app.services.prediction_service import PredictionService

    _history(db_session, 45)
    _task(db_session, title="write report", due_date=REAL_TODAY + timedelta(days=1))
    assert MLService(db_session).train_tasks()["trained"] is True

    risks = PredictionService(db_session).build(REAL_TODAY).deadline_risks
    if risks:  # the model may judge it safe, which is a legitimate answer
        assert risks[0].probability is not None
        assert "likely to land on time" in risks[0].reason


def test_the_plan_endpoint_carries_deadline_risks(client):
    body = client.get(f"{BASE}/predictions").json()
    assert "deadline_risks" in body
    assert body["deadline_risks"] == []
