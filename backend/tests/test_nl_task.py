"""Reading "gym tomorrow 7am" as a task.

The interesting half of a parser like this is what it *doesn't* match. A tool
that turns "buy 3 apples" into a 3am appointment, or eats the word "august" out
of "august planning session", is worse than one that never tried — so most of
what follows is about leaving things alone.
"""
from __future__ import annotations

from datetime import date, datetime, time

import pytest

from app.services.nl_task import parse

BASE = "/api/v1"
#: A Friday, mid-morning, so "9am" is already past and "3pm" is not.
NOW = datetime(2026, 8, 14, 10, 0)
TODAY = NOW.date()


def p(text: str):
    return parse(text, NOW)


# ------------------------------------------------------------------- dates
def test_tomorrow():
    r = p("gym tomorrow")
    assert r.title == "gym"
    assert r.due_date == date(2026, 8, 15)


@pytest.mark.parametrize("word", ["tmr", "tmw"])
def test_common_shorthands(word):
    assert p(f"gym {word}").due_date == date(2026, 8, 15)


def test_today_and_tonight():
    assert p("gym today").due_date == TODAY
    tonight = p("read tonight")
    assert tonight.due_date == TODAY
    assert tonight.deadline.time() == time(19, 0), "'tonight' implies the evening"


def test_a_weekday_means_the_next_one():
    assert p("review monday").due_date == date(2026, 8, 17)


def test_a_weekday_naming_today_means_next_week():
    """Said on a Friday, "do it friday" is not about the hour you're in."""
    assert p("review friday").due_date == date(2026, 8, 21)


def test_in_n_days_and_weeks():
    assert p("plan in 3 days").due_date == date(2026, 8, 17)
    assert p("plan in 2 weeks").due_date == date(2026, 8, 28)
    assert p("plan next week").due_date == date(2026, 8, 21)


@pytest.mark.parametrize("phrase", ["file taxes 20 aug", "file taxes aug 20", "file taxes 20th august"])
def test_named_months_either_way_round(phrase):
    assert p(phrase).due_date == date(2026, 8, 20)


def test_an_iso_date_is_taken_literally():
    assert p("ship it 2026-12-01").due_date == date(2026, 12, 1)


def test_a_date_already_past_means_next_year():
    """"jan 3" said in August is five months away, not seven months ago."""
    assert p("renew licence jan 3").due_date == date(2027, 1, 3)


def test_an_impossible_date_is_left_alone():
    r = p("call about feb 30")
    assert r.due_date is None
    assert "feb 30" in r.title


# ------------------------------------------------------------------- times
def test_am_and_pm():
    assert p("gym tomorrow 7am").deadline.time() == time(7, 0)
    assert p("gym tomorrow 7pm").deadline.time() == time(19, 0)


def test_minutes():
    assert p("standup tomorrow at 9:15am").deadline.time() == time(9, 15)
    assert p("call tomorrow 14:30").deadline.time() == time(14, 30)


def test_midday_and_midnight():
    assert p("lunch tomorrow noon").deadline.time() == time(12, 0)
    assert p("deploy tomorrow midnight").deadline.time() == time(0, 0)
    assert p("lunch tomorrow 12pm").deadline.time() == time(12, 0)
    assert p("deploy tomorrow 12am").deadline.time() == time(0, 0)


def test_a_bare_hour_means_the_afternoon():
    """Nobody schedules a call for 3am, and the guess is shown back."""
    assert p("call mum at 3").deadline.time() == time(15, 0)
    assert p("call mum at 9").deadline.time() == time(9, 0), "but 9 means the morning"


def test_a_time_with_no_day_means_today():
    r = p("call at 3")
    assert r.due_date == TODAY


def test_a_time_that_has_already_gone_means_tomorrow():
    """It's 10am. "at 9" cannot mean an hour ago."""
    assert p("call at 9").due_date == date(2026, 8, 15)


def test_nonsense_times_are_not_times():
    assert p("read 99:99").deadline is None
    assert p("chapter 25").deadline is None


# ---------------------------------------------------------------- the rest
def test_priority_markers():
    assert p("fix build !high").priority == "high"
    assert p("fix build urgent").priority == "high"
    assert p("fix build asap").priority == "high"
    assert p("fix build critical").priority == "critical"
    assert p("tidy desk !low").priority == "low"


def test_durations():
    assert p("read for 30 min").estimated_effort_min == 30
    assert p("read 45m").estimated_effort_min == 45
    assert p("read 2h").estimated_effort_min == 120
    assert p("read 1.5 hours").estimated_effort_min == 90


def test_an_absurd_duration_is_refused():
    r = p("wait 90000 minutes")
    assert r.estimated_effort_min is None
    assert "90000" in r.title


def test_tags():
    r = p("file taxes #finance #admin")
    assert r.tags == ["finance", "admin"]
    assert r.title == "file taxes"


def test_everything_at_once():
    r = p("submit report tomorrow 4pm !high 45m #work")
    assert r.title == "submit report"
    assert r.due_date == date(2026, 8, 15)
    assert r.deadline.time() == time(16, 0)
    assert r.priority == "high"
    assert r.estimated_effort_min == 45
    assert r.tags == ["work"]


# ------------------------------------------------------- leaving things alone
def test_a_plain_title_is_left_exactly_as_it_is():
    r = p("buy milk")
    assert r.title == "buy milk"
    assert r.is_empty()


def test_a_number_is_not_a_time():
    r = p("buy 3 apples")
    assert r.deadline is None
    assert r.title == "buy 3 apples"


def test_a_month_name_without_a_day_is_just_a_word():
    r = p("august planning session")
    assert r.due_date is None
    assert r.title == "august planning session"


def test_words_are_not_matched_inside_other_words():
    for phrase in ("somersault practice", "monitor the logs", "summarise the deck"):
        assert p(phrase).title == phrase, f"{phrase} was mangled"


def test_a_phrase_that_is_only_a_date_keeps_its_title():
    """"tomorrow" is a poor task name, but an empty one is worse."""
    r = p("tomorrow")
    assert r.title == "tomorrow"
    assert r.due_date is None


def test_empty_input_is_survivable():
    assert parse("", NOW).title == ""
    assert parse("   ", NOW).title == ""


def test_understood_lists_what_was_taken():
    r = p("submit report tomorrow 4pm !high #work")
    joined = " · ".join(r.understood)
    assert "due tomorrow at 4:00pm" in joined
    assert "high priority" in joined
    assert "#work" in joined


# ----------------------------------------------------------------- endpoint
def test_the_endpoint_parses_without_creating_anything(client):
    res = client.post(f"{BASE}/tasks/parse", json={"text": "gym tomorrow 7am !high"})
    assert res.status_code == 200
    body = res.json()

    assert body["title"] == "gym"
    assert body["priority"] == "high"
    assert body["due_date"]
    assert body["understood"]
    assert client.get(f"{BASE}/tasks").json() == [], "parsing is a preview, not a write"


def test_the_endpoint_is_honest_when_it_understood_nothing(client):
    body = client.post(f"{BASE}/tasks/parse", json={"text": "buy milk"}).json()
    assert body["title"] == "buy milk"
    assert body["understood"] == []
    assert body["due_date"] is None


def test_the_endpoint_handles_an_empty_phrase(client):
    body = client.post(f"{BASE}/tasks/parse", json={"text": "   "}).json()
    assert body["title"] == ""
    assert body["understood"] == []
