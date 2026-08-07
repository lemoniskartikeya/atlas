"""Calendar month aggregation."""
from __future__ import annotations

from datetime import date, timedelta

BASE = "/api/v1"


def _habit(client, **body):
    body.setdefault("title", "Meditate")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


def _month(client, d: date):
    return client.get(f"{BASE}/calendar?year={d.year}&month={d.month}").json()


def _day(payload, d: date):
    return next(x for x in payload["days"] if x["date"] == d.isoformat())


def test_grid_is_whole_monday_first_weeks(client):
    payload = _month(client, date(2026, 8, 1))
    days = payload["days"]
    assert len(days) % 7 == 0
    assert date.fromisoformat(days[0]["date"]).weekday() == 0  # Monday
    assert date.fromisoformat(days[-1]["date"]).weekday() == 6  # Sunday
    # Padding days belong to neighbouring months and are flagged as such.
    assert any(not d["in_month"] for d in days)
    assert all(date.fromisoformat(d["date"]).month == 8 for d in days if d["in_month"])


def test_label_and_today_flag(client):
    today = date.today()
    payload = _month(client, today)
    assert payload["label"].endswith(str(today.year))
    assert sum(1 for d in payload["days"] if d["is_today"]) == 1
    assert _day(payload, today)["is_today"] is True


def test_logged_habit_appears_with_its_status(client):
    _habit(client, title="Deep Work")
    hid = _habit(client, title="Read")
    client.post(f"{BASE}/habits/{hid}/logs", json={"status": "completed"})

    today = date.today()
    day = _day(_month(client, today), today)
    read = next(h for h in day["habits"] if h["title"] == "Read")
    assert read["status"] == "completed"
    assert day["habits_done"] == 1


def test_unlogged_daily_habit_shows_as_due(client):
    _habit(client, title="Stretch", frequency="daily")
    today = date.today()
    day = _day(_month(client, today), today)
    assert [h["status"] for h in day["habits"]] == ["due"]
    assert day["habits_due"] == 1 and day["habits_done"] == 0


def test_intensity_is_done_over_due(client):
    a = _habit(client, title="A", frequency="daily")
    _habit(client, title="B", frequency="daily")
    client.post(f"{BASE}/habits/{a}/logs", json={"status": "completed"})

    today = date.today()
    day = _day(_month(client, today), today)
    assert day["habits_due"] == 2
    assert day["intensity"] == 0.5


def test_custom_schedule_only_lands_on_its_weekdays(client):
    today = date.today()
    _habit(client, title="Gym", frequency="custom", custom_days=[today.weekday()])

    payload = _month(client, today)
    for d in payload["days"]:
        expected = date.fromisoformat(d["date"]).weekday() == today.weekday()
        has_gym = any(h["title"] == "Gym" for h in d["habits"])
        assert has_gym == expected, d["date"]


def test_weekly_habits_are_not_pinned_to_a_day(client):
    """A weekly target commits to a count, not a date — don't invent one."""
    _habit(client, title="Long Run", frequency="weekly", target_per_period=1)
    payload = _month(client, date.today())
    assert not any(
        h["title"] == "Long Run" and h["status"] == "due"
        for d in payload["days"]
        for h in d["habits"]
    )


def test_tasks_show_on_due_date_and_completion_date(client):
    today = date.today()
    tomorrow = today + timedelta(days=1)
    tid = client.post(
        f"{BASE}/tasks", json={"title": "Ship it", "due_date": tomorrow.isoformat()}
    ).json()["id"]

    payload = _month(client, today)
    if tomorrow.month == today.month:
        assert any(t["title"] == "Ship it" for t in _day(payload, tomorrow)["tasks"])

    client.post(f"{BASE}/tasks/{tid}/complete")
    day = _day(_month(client, today), today)
    done = next(t for t in day["tasks"] if t["title"] == "Ship it")
    assert done["completed_here"] is True
    assert day["tasks_completed"] == 1


def test_journal_and_focus_roll_into_the_day(client):
    today = date.today()
    client.put(
        f"{BASE}/journal/{today.isoformat()}",
        json={"mood": 4, "energy": 3, "sleep_hours": 7.5},
    )
    client.post(f"{BASE}/focus/sessions", json={"duration_min": 25, "distractions": 1})

    day = _day(_month(client, today), today)
    assert day["has_journal"] is True
    assert day["mood"] == 4 and day["sleep_hours"] == 7.5
    assert day["focus_minutes"] == 25 and day["focus_sessions"] == 1


def test_month_totals_and_perfect_days(client):
    hid = _habit(client, title="Meditate", frequency="daily")
    client.post(f"{BASE}/habits/{hid}/logs", json={"status": "completed"})

    payload = _month(client, date.today())
    assert payload["total_habits_done"] >= 1
    # Only habit due today, and it's done → today counts as perfect.
    assert payload["perfect_days"] >= 1


def test_future_days_are_flagged(client):
    today = date.today()
    payload = _month(client, today)
    for d in payload["days"]:
        assert d["is_future"] == (date.fromisoformat(d["date"]) > today)


def test_defaults_to_the_current_month(client):
    today = date.today()
    payload = client.get(f"{BASE}/calendar").json()
    assert payload["year"] == today.year and payload["month"] == today.month
