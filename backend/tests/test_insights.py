"""The sentences the Analytics page puts under its charts.

Two things are worth guarding here, and they pull in opposite directions: a
rule must fire when the data genuinely supports it, and must stay silent when
it doesn't. Most of these tests are about the silence — a confident sentence
drawn from four data points is worse than no sentence at all.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.enums import HabitLogStatus
from app.services import insights
from app.services.insights import HabitRow

BASE = "/api/v1"


def _row(title="Read", *, all_time=0.8, last_30=0.8, total=40, streak=0) -> HabitRow:
    return HabitRow(
        title=title,
        success_rate=all_time,
        consistency_30d=last_30,
        total_completions=total,
        current_streak=streak,
    )


# ------------------------------------------------------------------ weekdays
def test_weekday_edge_names_the_best_and_worst_day():
    by_weekday = [(9, 10), (8, 10), (8, 10), (7, 10), (7, 10), (3, 10), (4, 10)]
    out = insights.weekday_edge(by_weekday)

    assert out is not None
    assert "Mondays are your strongest day at 90%" in out.text
    assert "Saturdays your weakest at 30%" in out.text
    assert "60 point gap" in out.evidence


def test_weekday_edge_compares_rates_not_volume():
    """A day with more habits scheduled is busier, not better.

    Saturday here completes 20 of 20; Monday completes 30 of 60. Counting
    completions would crown Monday, which is exactly backwards.
    """
    by_weekday = [(30, 60), (5, 10), (5, 10), (5, 10), (5, 10), (20, 20), (5, 10)]
    out = insights.weekday_edge(by_weekday)

    assert out is not None
    assert "Saturdays are your strongest day at 100%" in out.text
    assert "Mondays your weakest at 50%" in out.text


def test_weekday_edge_ignores_days_with_too_little_history():
    """One perfect Sunday is not a pattern."""
    by_weekday = [(20, 40)] * 6 + [(1, 1)]
    out = insights.weekday_edge(by_weekday)
    assert out is None, "a single occurrence must not become your best day"


def test_weekday_edge_stays_quiet_when_days_are_alike():
    by_weekday = [(8, 10), (8, 10), (7, 10), (8, 10), (8, 10), (7, 10), (8, 10)]
    assert insights.weekday_edge(by_weekday) is None


def test_weekday_edge_needs_seven_buckets():
    assert insights.weekday_edge([(5, 10)] * 6) is None


# --------------------------------------------------------------------- trend
def test_trend_reports_a_real_rise():
    out = insights.trend(recent=(45, 50), previous=(25, 50))
    assert out is not None
    assert out.tone == "good"
    assert "up 40 points" in out.text
    assert "50% then, 90% now" in out.text
    assert out.evidence == "45/50 vs 25/50 due"


def test_trend_reports_a_fall_as_something_to_watch():
    out = insights.trend(recent=(20, 50), previous=(40, 50))
    assert out is not None
    assert out.tone == "watch"
    assert "down 40 points" in out.text


def test_a_small_wobble_is_called_steady():
    """Week-to-week noise is not a trend, and calling it one trains people to
    ignore the whole panel."""
    out = insights.trend(recent=(26, 50), previous=(25, 50))
    assert out is not None
    assert out.tone == "neutral"
    assert "holding steady" in out.text


def test_trend_needs_both_halves():
    """A new account has no 'before' to compare against."""
    assert insights.trend(recent=(40, 50), previous=(2, 3)) is None
    assert insights.trend(recent=(2, 3), previous=(40, 50)) is None


def test_trend_says_how_many_weeks_it_looked_at():
    out = insights.trend((45, 50), (25, 50), window_days=14)
    assert out is not None and "last 2 weeks" in out.text


# -------------------------------------------------------------------- driver
def test_the_strongest_signal_wins():
    out = insights.strongest_driver(
        [("Sleep", 0.42, 60), ("Mood", 0.31, 60), ("Energy", -0.55, 60)]
    )
    assert out is not None
    assert out.text.startswith("Energy")
    assert "r=-0.55 across 60 days" in out.evidence


def test_a_positive_correlation_reads_as_more():
    out = insights.strongest_driver([("Sleep", 0.61, 40)])
    assert out is not None and "more of it" in out.text


def test_a_weak_correlation_is_not_worth_a_sentence():
    assert insights.strongest_driver([("Sleep", 0.12, 90), ("Mood", -0.2, 90)]) is None


def test_a_strong_correlation_on_two_weeks_of_data_is_not_reported():
    assert insights.strongest_driver([("Sleep", 0.9, 6)]) is None


def test_an_undefined_correlation_is_skipped():
    assert insights.strongest_driver([("Sleep", None, 90)]) is None


def test_the_driver_sentence_refuses_to_claim_causation():
    out = insights.strongest_driver([("Sleep", 0.7, 50)])
    assert out is not None
    assert "not a conclusion" in out.text


# -------------------------------------------------------------------- habits
def test_a_habit_below_its_own_record_is_flagged():
    rows = [
        _row("Read", all_time=0.85, last_30=0.4, total=60),
        _row("Run", all_time=0.7, last_30=0.68, total=60),
    ]
    out = insights.slipping_habit(rows)

    assert out is not None
    assert "“Read” has slipped" in out.text
    assert "40% over the last 30 days against 85% all time" in out.text
    assert out.tone == "watch"


def test_the_worst_slip_is_the_one_reported():
    rows = [
        _row("Read", all_time=0.9, last_30=0.6, total=60),
        _row("Run", all_time=0.9, last_30=0.3, total=60),
    ]
    out = insights.slipping_habit(rows)
    assert out is not None and "Run" in out.text


def test_a_brand_new_habit_cannot_have_slipped():
    """Two weeks in, 'below your average' is measuring nothing."""
    rows = [_row("Read", all_time=0.9, last_30=0.2, total=4)]
    assert insights.slipping_habit(rows) is None


def test_a_habit_holding_its_average_is_not_flagged():
    assert insights.slipping_habit([_row(all_time=0.8, last_30=0.78, total=90)]) is None


def test_the_anchor_is_the_one_still_holding():
    rows = [_row("Read", last_30=0.95, total=80, streak=12), _row("Run", last_30=0.5, total=80)]
    out = insights.anchor_habit(rows)

    assert out is not None
    assert "“Read” is your anchor" in out.text
    assert "12-day streak" in out.text
    assert out.tone == "good"


def test_a_short_streak_is_not_mentioned():
    out = insights.anchor_habit([_row(last_30=0.95, total=80, streak=1)])
    assert out is not None and "streak" not in out.text


def test_nothing_qualifies_as_an_anchor_below_the_bar():
    assert insights.anchor_habit([_row(last_30=0.6, total=80)]) is None


# ------------------------------------------------------------------ category
def test_a_dominant_category_is_named():
    out = insights.category_focus([("Health", 40), ("Work", 10), ("Learning", 5)])
    assert out is not None
    assert "73% of everything you complete is Health" in out.text
    assert "the other 2 categories share" in out.text


def test_a_single_runner_up_is_not_called_categories():
    out = insights.category_focus([("Health", 40), ("Work", 10)])
    assert out is not None
    assert "the other category takes what's left" in out.text


def test_an_even_spread_says_nothing():
    assert insights.category_focus([("Health", 20), ("Work", 18), ("Learning", 17)]) is None


def test_uncategorized_is_not_a_category():
    """Otherwise the insight reads 'most of what you do is Uncategorized',
    which describes the form, not the life."""
    assert insights.category_focus([("Uncategorized", 90), ("Health", 10)]) is None


def test_one_category_is_not_a_concentration():
    assert insights.category_focus([("Health", 90)]) is None


# ------------------------------------------------------------------ ranking
def test_ranking_drops_the_rules_that_had_nothing_to_say():
    out = insights.rank([None, None, None])
    assert out == []


def test_ranking_puts_direction_and_risk_first():
    unordered = [
        insights.Insight("category_focus", "c", "e", "neutral"),
        insights.Insight("anchor_habit", "a", "e", "good"),
        insights.Insight("trend", "t", "e", "good"),
        insights.Insight("slipping_habit", "s", "e", "watch"),
    ]
    assert [i.key for i in insights.rank(unordered)] == [
        "trend",
        "slipping_habit",
        "anchor_habit",
        "category_focus",
    ]


def test_ranking_keeps_the_list_short():
    many = [insights.Insight(k, k, "e", "neutral") for k in insights._ORDER]
    assert len(insights.rank(many)) == 4


# -------------------------------------------------------- service and endpoint
def test_a_new_account_gets_no_insights(client):
    """Silence is the honest answer with no history, and the UI shows nothing."""
    res = client.get(f"{BASE}/analytics/insights")
    assert res.status_code == 200
    assert res.json()["insights"] == []


def test_insights_are_derived_from_the_users_actual_logs(client):
    """End to end: real habit, real logs, real sentence.

    Completed every Monday and missed every Saturday for ten weeks, so the
    weekday rule has something true to find.
    """
    habit = client.post(
        f"{BASE}/habits",
        json={"title": "Weights", "frequency": "daily", "category": "Health"},
    ).json()

    today = date.today()
    start = today - timedelta(days=69)
    for i in range(70):
        day = start + timedelta(days=i)
        if day.weekday() == 5:  # Saturday, always missed
            continue
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={"date": day.isoformat(), "status": HabitLogStatus.COMPLETED.value},
        )

    body = client.get(f"{BASE}/analytics/insights").json()
    keys = {i["key"] for i in body["insights"]}
    assert "weekday_edge" in keys, body

    weekday = next(i for i in body["insights"] if i["key"] == "weekday_edge")
    assert "Saturdays your weakest at 0%" in weekday["text"]
    assert weekday["evidence"], "a claim must carry the numbers behind it"
    assert body["days"] == 365


def test_every_insight_carries_checkable_evidence(client):
    habit = client.post(
        f"{BASE}/habits", json={"title": "Read", "frequency": "daily", "category": "Learning"}
    ).json()
    today = date.today()
    for i in range(60):
        day = today - timedelta(days=i)
        if i % 3 == 0:
            continue
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={"date": day.isoformat(), "status": HabitLogStatus.COMPLETED.value},
        )

    found = client.get(f"{BASE}/analytics/insights").json()["insights"]
    # Without this the loop below would pass by looking at nothing.
    assert found, "two months of daily logs should produce something to say"

    for insight in found:
        assert insight["text"].strip()
        assert insight["evidence"].strip()
        assert insight["tone"] in {"good", "watch", "neutral"}
        # Every sentence should contain a number the user can go and check.
        assert any(ch.isdigit() for ch in insight["text"]), insight


def test_insights_are_scoped_to_the_signed_in_account(client, other_client):
    """One account's habits must never turn into another's insights."""
    habit = client.post(
        f"{BASE}/habits", json={"title": "Private", "frequency": "daily"}
    ).json()
    today = date.today()
    for i in range(60):
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={
                "date": (today - timedelta(days=i)).isoformat(),
                "status": HabitLogStatus.COMPLETED.value,
            },
        )

    body = other_client.get(f"{BASE}/analytics/insights").json()
    assert body["insights"] == []
    assert all("Private" not in i["text"] for i in body["insights"])


@pytest.mark.parametrize("days", [27, 731])
def test_the_window_is_bounded(client, days):
    assert client.get(f"{BASE}/analytics/insights?days={days}").status_code == 422
