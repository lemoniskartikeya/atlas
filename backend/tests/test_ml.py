"""Tests for the ML feature pipeline and completion model."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.domain.enums import Frequency, HabitLogStatus
from app.learning import features
from app.models.habit import Habit, HabitLog
from app.services.ml_service import MLService


def _habit_with_history(session, days: int = 60, skip_every: int = 10) -> Habit:
    habit = Habit(title="ML Habit", frequency=Frequency.DAILY)
    habit.created_at = datetime.now(timezone.utc) - timedelta(days=days + 5)
    session.add(habit)
    session.flush()
    today = date.today()
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        status = HabitLogStatus.SKIPPED if i % skip_every == 0 else HabitLogStatus.COMPLETED
        habit.logs.append(HabitLog(date=d, status=status))
    session.commit()
    return habit


def test_feature_matrix_shape(db_session):
    _habit_with_history(db_session, days=20)
    X, y, dates = features.build_training(db_session)
    assert X.shape[1] == len(features.FEATURE_NAMES)
    assert X.shape[0] == len(y) == len(dates)
    assert X.shape[0] > 0


def test_no_leakage_first_row_has_empty_history(db_session):
    _habit_with_history(db_session, days=15)
    X, y, dates = features.build_training(db_session)
    # streak_in is index 16; the earliest example has no prior history -> streak 0.
    streak_idx = features.FEATURE_NAMES.index("streak_in")
    assert X[0][streak_idx] == 0.0


def test_train_and_predict(db_session):
    _habit_with_history(db_session, days=60)
    svc = MLService(db_session)

    result = svc.train()
    assert result["trained"] is True, result
    assert result["n_samples"] >= 40

    preds = svc.predict_today()
    assert preds["trained"] is True
    assert len(preds["predictions"]) == 1
    p = preds["predictions"][0]
    assert 0.0 <= p["probability"] <= 1.0
    assert isinstance(p["explanation"], str) and p["explanation"]


def test_train_refuses_insufficient_data(db_session):
    _habit_with_history(db_session, days=10)  # < MIN_SAMPLES
    result = MLService(db_session).train()
    assert result["trained"] is False
    assert "Need at least" in result["reason"]
