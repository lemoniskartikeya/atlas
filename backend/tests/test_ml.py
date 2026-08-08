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


# ------------------------------------------------------------------ evaluation
def _version(version: str, auc: float, lo: float, hi: float) -> dict:
    return {
        "version": version,
        "metrics": {
            "roc_auc": auc,
            "roc_auc_min": lo,
            "roc_auc_max": hi,
            "eval": "rolling-origin",
        },
    }



def test_evaluation_reports_a_spread_not_a_bare_number(db_session):
    """A single split on this much data moves further than most retrains do."""
    _habit_with_history(db_session, days=90)
    metrics = MLService(db_session).train()["metrics"]

    assert metrics["eval"] == "rolling-origin"
    assert metrics["n_folds"] >= 2
    assert metrics["roc_auc_min"] <= metrics["roc_auc"] <= metrics["roc_auc_max"]
    # The minority-class count is the real limit on trusting any of this.
    assert metrics["n_test_neg_min"] >= 1


def test_unmeasurable_data_says_why_instead_of_going_quiet(db_session):
    """No score is a fact about the data; a silent gap reads as a bug."""
    from app.learning.model import _evaluate

    import numpy as np

    # Every outcome identical — nothing to discriminate, no fold can score.
    ys = np.ones(60)
    xs = np.random.default_rng(0).normal(size=(60, 4))
    metrics = _evaluate(xs, ys)

    assert metrics["eval"] == "none"
    assert metrics["eval_note"]
    assert "roc_auc" not in metrics


def test_a_fold_only_sees_its_own_training_slice(db_session):
    """Feature selection must not be informed by the period being scored."""
    from app.learning.model import _score_fold

    import numpy as np

    rng = np.random.default_rng(0)
    ys = np.array([i % 3 != 0 for i in range(60)], dtype=float)
    xs = rng.normal(size=(60, 3))
    # A column that is constant during training and only varies afterwards is
    # uninformative *at fit time* — selecting on the full matrix would keep it.
    xs[:40, 2] = 1.0

    fold = _score_fold(xs, ys, split=40)
    assert fold is not None
    assert 0.0 <= fold["roc_auc"] <= 1.0
    assert fold["n_test"] == 20


def test_history_calls_a_small_delta_noise(client, monkeypatch):
    """Two models a hair apart, on folds that swing more than that."""
    from app.services import ml_gateway

    monkeypatch.setattr(
        ml_gateway,
        "model_history",
        lambda _uid: [
            _version("1", 0.70, 0.60, 0.80),
            _version("2", 0.66, 0.58, 0.78),
        ],
    )
    body = client.get("/api/v1/ml/history").json()

    assert body["delta_vs_previous"] == -0.04
    assert body["noise_floor"] == 0.20
    assert body["delta_is_meaningful"] is False


def test_history_refuses_to_compare_across_scoring_methods(client, monkeypatch):
    """An old single-split score and a fold mean are different quantities."""
    from app.services import ml_gateway

    monkeypatch.setattr(
        ml_gateway,
        "model_history",
        lambda _uid: [
            {"version": "1", "metrics": {"roc_auc": 0.75}},  # legacy, no `eval`
            _version("2", 0.64, 0.58, 0.70),
        ],
    )
    body = client.get("/api/v1/ml/history").json()

    assert body["delta_vs_previous"] == -0.11  # still reported...
    assert body["delta_is_meaningful"] is None  # ...but not called a regression
