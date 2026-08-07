"""Recommendations are scored against what actually happened."""
from __future__ import annotations

from datetime import date, timedelta

from app.models.feedback import RecommendationOutcome
from app.schemas.dashboard import Recommendation
from app.services.feedback_service import (
    MIN_SAMPLES_FOR_SIGNAL,
    FeedbackService,
    family_of,
)
from app.services.recommender import Recommender

BASE = "/api/v1"


def _rec(rec_id: str, habit_id=None, confidence=0.6) -> Recommendation:
    return Recommendation(
        id=rec_id,
        kind="habit",
        title="t",
        detail="d",
        confidence=confidence,
        reason="r",
        habit_id=habit_id,
    )


# ------------------------------------------------------------------ families
def test_parameterised_ids_collapse_into_one_family():
    """Evidence must aggregate per nudge *style*, not fragment per habit."""
    assert family_of("ml-risk-abc") == family_of("ml-risk-def") == "ml-risk"
    assert family_of("streak-abc") == "streak"
    # Non-parameterised nudges stand alone.
    assert family_of("sleep-low") == "sleep-low"


# ----------------------------------------------------------------- recording
def test_recording_is_idempotent(db_session):
    """The dashboard rebuilds on every load; that must not duplicate rows."""
    svc = FeedbackService(db_session)
    today = date.today()
    recs = [_rec("ml-risk-h1", "h1"), _rec("sleep-low")]

    svc.record_shown(recs, today)
    svc.record_shown(recs, today)
    svc.record_shown(recs, today)

    assert db_session.query(RecommendationOutcome).count() == 2


def test_same_recommendation_on_a_new_day_is_a_new_row(db_session):
    svc = FeedbackService(db_session)
    today = date.today()
    svc.record_shown([_rec("ml-risk-h1", "h1")], today - timedelta(days=1))
    svc.record_shown([_rec("ml-risk-h1", "h1")], today)
    assert db_session.query(RecommendationOutcome).count() == 2


# ---------------------------------------------------------------- resolution
def test_resolution_scores_against_real_completions(client, db_session):
    hid = client.post(f"{BASE}/habits", json={"title": "Meditate"}).json()["id"]
    yesterday = date.today() - timedelta(days=1)
    client.post(
        f"{BASE}/habits/{hid}/logs",
        json={"status": "completed", "date": yesterday.isoformat()},
    )

    svc = FeedbackService(db_session)
    svc.record_shown([_rec(f"ml-risk-{hid}", hid)], yesterday)
    svc.resolve_due(date.today())

    row = db_session.query(RecommendationOutcome).one()
    assert row.followed is True and row.resolved_at is not None


def test_unfollowed_recommendation_scores_false(client, db_session):
    hid = client.post(f"{BASE}/habits", json={"title": "Read"}).json()["id"]
    yesterday = date.today() - timedelta(days=1)

    svc = FeedbackService(db_session)
    svc.record_shown([_rec(f"streak-{hid}", hid)], yesterday)
    svc.resolve_due(date.today())

    assert db_session.query(RecommendationOutcome).one().followed is False


def test_todays_recommendations_are_not_scored_yet(db_session):
    """A day still in progress isn't a failure."""
    svc = FeedbackService(db_session)
    svc.record_shown([_rec("ml-risk-h1", "h1")], date.today())
    svc.resolve_due(date.today())
    assert db_session.query(RecommendationOutcome).one().followed is None


def test_nudges_without_a_habit_are_closed_unscored(db_session):
    """"Sleep more" has no completion event — don't count it as a miss."""
    svc = FeedbackService(db_session)
    svc.record_shown([_rec("sleep-low")], date.today() - timedelta(days=1))
    svc.resolve_due(date.today())

    row = db_session.query(RecommendationOutcome).one()
    assert row.followed is None
    assert row.resolved_at is not None  # resolved, just not scored


# ------------------------------------------------------------------- scoring
def _seed_outcomes(db_session, family: str, followed: bool, n: int, offset: int = 0):
    """`offset` keeps repeat calls for one family off the same (rec_id, day)."""
    base = date.today() - timedelta(days=2 + offset)
    for i in range(n):
        db_session.add(
            RecommendationOutcome(
                rec_id=f"{family}-h{offset}-{i}",
                kind="habit",
                family=family,
                habit_id=f"h{i}",
                shown_on=base - timedelta(days=i),
                followed=followed,
            )
        )
    db_session.commit()


def test_weights_ignore_families_with_too_little_evidence(db_session):
    _seed_outcomes(db_session, "streak", True, MIN_SAMPLES_FOR_SIGNAL - 1)
    assert "streak" not in FeedbackService(db_session).weights()


def test_effective_family_is_promoted_ineffective_demoted(db_session):
    _seed_outcomes(db_session, "streak", True, MIN_SAMPLES_FOR_SIGNAL)
    _seed_outcomes(db_session, "ml-risk", False, MIN_SAMPLES_FOR_SIGNAL)

    weights = FeedbackService(db_session).weights()
    assert weights["streak"] > 1.0 > weights["ml-risk"]


def test_effectiveness_reports_hit_rate(db_session):
    _seed_outcomes(db_session, "streak", True, 3)
    _seed_outcomes(db_session, "streak", False, 1, offset=10)
    stats = FeedbackService(db_session).effectiveness()["streak"]
    assert stats["shown"] == 4 and stats["followed"] == 3
    assert stats["rate"] == 0.75


# ------------------------------------------------------------------- ranking
def test_ranking_is_a_no_op_without_weights():
    recs = [_rec("a", confidence=0.5), _rec("b", confidence=0.9)]
    assert [r.id for r in Recommender()._rank(list(recs))] == ["a", "b"]


def test_weights_reorder_and_flag_recommendations():
    recs = [_rec("ml-risk-h1", "h1", confidence=0.60), _rec("streak-h2", "h2", confidence=0.55)]
    ranked = Recommender(weights={"ml-risk": 0.7, "streak": 1.3})._rank(list(recs))

    # 0.60*0.7 = 0.42 vs 0.55*1.3 = 0.715 -> the proven nudge leads.
    assert [r.id for r in ranked] == ["streak-h2", "ml-risk-h1"]
    assert all(r.outcome_ranked for r in ranked)


def test_unweighted_families_keep_their_position():
    recs = [_rec("sleep-low", confidence=0.55), _rec("morning-window", confidence=0.55)]
    ranked = Recommender(weights={"streak": 1.3})._rank(list(recs))
    assert [r.id for r in ranked] == ["sleep-low", "morning-window"]
    assert not any(r.outcome_ranked for r in ranked)


# ---------------------------------------------------------------- end to end
def test_dashboard_records_what_it_showed(client, db_session):
    client.post(f"{BASE}/habits", json={"title": "Meditate"})
    body = client.get(f"{BASE}/dashboard").json()

    shown = {r["id"] for r in body["recommendations"]}
    stored = {r.rec_id for r in db_session.query(RecommendationOutcome).all()}
    assert shown == stored
