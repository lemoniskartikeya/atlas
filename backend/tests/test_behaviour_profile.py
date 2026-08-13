"""How this person works, as opposed to how today is going.

The failure mode to guard against is a horoscope: four confident sentences
generated from a fortnight of logs, all of which sound plausible and none of
which are earned. So every trait has a floor, and most of what follows checks
that it stays silent below it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services.behaviour_profile import (
    BehaviourProfileService,
    load_tolerance,
    peak_hours,
    streak_durability,
    weekday_reliability,
)

BASE = "/api/v1"
TODAY = date.today()


# --------------------------------------------------------------- peak hours
def test_a_clear_morning_pattern_is_found():
    hours = [7] * 12 + [8] * 10 + [9] * 4 + [14, 15, 16, 20, 21]
    found = peak_hours(hours)

    assert found is not None
    trait, window = found
    assert window == (7, 10)
    assert "7am and 10am" in trait.summary
    assert "of everything you finish" in trait.summary
    assert str(len(hours)) in trait.evidence


def test_the_window_wraps_around_midnight():
    """A night owl's peak is real even though it crosses the date line."""
    hours = [23] * 10 + [0] * 10 + [1] * 8 + [9, 10, 14]
    found = peak_hours(hours)

    assert found is not None
    _trait, window = found
    assert window == (23, 2)


def test_working_at_all_hours_is_not_a_pattern():
    hours = [h % 24 for h in range(48)]  # perfectly flat
    assert peak_hours(hours) is None


def test_a_handful_of_completions_says_nothing_about_your_day():
    assert peak_hours([7, 7, 7, 8, 8]) is None


# ------------------------------------------------------------------ weekdays
def test_the_most_and_least_reliable_days():
    by_weekday = [(9, 10), (8, 10), (8, 10), (7, 10), (6, 10), (2, 10), (3, 10)]
    found = weekday_reliability(by_weekday)

    assert found is not None
    trait, best, worst = found
    assert (best, worst) == (0, 5)
    assert "Monday is your most reliable day (90%)" in trait.summary
    assert "Saturday your least (20%)" in trait.summary


def test_reliability_is_a_rate_not_a_tally():
    """Otherwise the busiest day always wins, which is the opposite of the truth."""
    by_weekday = [(30, 60)] + [(6, 10)] * 5 + [(10, 10)]
    _trait, best, worst = weekday_reliability(by_weekday)
    assert best == 6 and worst == 0


def test_days_that_look_alike_produce_nothing():
    assert weekday_reliability([(8, 10)] * 7) is None


def test_two_days_of_evidence_is_not_a_week():
    assert weekday_reliability([(8, 10), (2, 10)] + [(1, 2)] * 5) is None


# ------------------------------------------------------------------- streaks
def test_typical_streak_length():
    found = streak_durability([3, 4, 4, 5, 12])
    assert found is not None
    trait, typical = found
    assert typical == 4
    assert "break around day 4" in trait.summary
    assert "reached 12" in trait.summary


def test_consistent_runs_are_described_as_steady():
    found = streak_durability([5, 5, 5, 5])
    assert found is not None
    trait, typical = found
    assert typical == 5
    assert "steady" in trait.summary


def test_three_runs_is_not_a_habit_of_habits():
    assert streak_durability([3, 4, 9]) is None


# ---------------------------------------------------------------------- load
def _day(due: int, rate: float) -> dict:
    return {"due": due, "rate": rate, "date": TODAY}


def test_a_crowded_day_costing_you_is_reported():
    rows = [_day(2, 0.95) for _ in range(10)] + [_day(8, 0.4) for _ in range(10)]
    trait = load_tolerance(rows)

    assert trait is not None
    assert "Busy days cost you" in trait.summary
    assert "40%" in trait.summary and "95%" in trait.summary


def test_thriving_under_load_is_reported_as_such():
    """Some people do more when there is more to do, and telling them to slow
    down would be advice drawn from someone else's data."""
    rows = [_day(2, 0.4) for _ in range(10)] + [_day(8, 0.9) for _ in range(10)]
    trait = load_tolerance(rows)

    assert trait is not None
    assert "A fuller day suits you" in trait.summary


def test_load_makes_no_difference_says_nothing():
    rows = [_day(2, 0.8) for _ in range(10)] + [_day(8, 0.78) for _ in range(10)]
    assert load_tolerance(rows) is None


def test_an_unvarying_load_cannot_be_compared():
    """Every day identical means there is no busy half to look at."""
    assert load_tolerance([_day(3, 0.8) for _ in range(30)]) is None


def test_a_fortnight_is_not_enough_to_judge_load():
    rows = [_day(2, 0.95) for _ in range(5)] + [_day(8, 0.3) for _ in range(5)]
    assert load_tolerance(rows) is None


# ------------------------------------------------------------ end to end
def test_a_new_account_has_no_profile(client, db_session):
    """Three days of logs must not produce a personality."""
    profile = BehaviourProfileService(db_session).build(TODAY)
    assert profile.traits == []

    body = client.get(f"{BASE}/analytics/profile").json()
    assert body["traits"] == []
    assert body["peak_hours"] is None
    assert body["window_days"] == BehaviourProfileService.WINDOW_DAYS


def test_a_real_history_produces_real_traits(client, db_session):
    """A habit done most mornings, missed most weekends, over four months."""
    habit = client.post(
        f"{BASE}/habits", json={"title": "Weights", "frequency": "daily"}
    ).json()

    for i in range(1, 100):
        day = TODAY - timedelta(days=i)
        if day.weekday() >= 5:
            continue  # weekends are where it falls apart
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={"date": day.isoformat(), "status": "completed"},
        )

    # Logging through the API stamps logged_at with "now", so set the hour
    # explicitly — the point of the trait is the hour of the day.
    from app.models.habit import HabitLog

    for n, log in enumerate(db_session.query(HabitLog).all()):
        log.logged_at = datetime.combine(
            log.date, datetime.min.time(), tzinfo=timezone.utc
        ).astimezone().replace(hour=7 if n % 5 else 19)
    db_session.commit()

    profile = BehaviourProfileService(db_session).build(TODAY)
    keys = {t.key for t in profile.traits}

    assert "peak_hours" in keys, [t.summary for t in profile.traits]
    assert "weekday_reliability" in keys
    assert profile.worst_weekday in (5, 6), "weekends are the weak spot here"

    for trait in profile.traits:
        assert trait.summary.strip() and trait.evidence.strip()
        assert any(ch.isdigit() for ch in trait.summary), trait.summary


def test_the_profile_is_scoped_to_the_account(client, other_client):
    habit = client.post(f"{BASE}/habits", json={"title": "Private", "frequency": "daily"}).json()
    for i in range(1, 90):
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={"date": (TODAY - timedelta(days=i)).isoformat(), "status": "completed"},
        )

    assert other_client.get(f"{BASE}/analytics/profile").json()["traits"] == []


def test_a_running_streak_is_not_counted_as_finished(db_session, client):
    """Its length isn't known yet, and counting it would drag the typical
    figure down every time you looked at the page."""
    habit = client.post(f"{BASE}/habits", json={"title": "Run", "frequency": "daily"}).json()
    for i in range(0, 30):
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={"date": (TODAY - timedelta(days=i)).isoformat(), "status": "completed"},
        )

    from app.repositories.habit_repo import HabitRepository

    habits = list(HabitRepository(db_session).list_all(include_archived=True))
    runs = BehaviourProfileService._completed_runs(habits, TODAY - timedelta(days=120), TODAY)
    assert runs == [], "one unbroken run, still going"


def test_the_coach_is_told_how_the_user_works(client, db_session):
    habit = client.post(f"{BASE}/habits", json={"title": "Read", "frequency": "daily"}).json()
    for i in range(1, 100):
        day = TODAY - timedelta(days=i)
        if day.weekday() >= 5:
            continue
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={"date": day.isoformat(), "status": "completed"},
        )

    from app.services.coach_service import CoachService

    svc = CoachService(db_session)
    digest = svc._digest_text(svc._context(TODAY))
    assert "Long-run patterns:" in digest, digest
