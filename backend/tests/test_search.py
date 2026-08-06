"""Tests for natural-language search: the parser + end-to-end search."""
from __future__ import annotations

from datetime import date

from app.services.search_service import SearchService, parse

BASE = "/api/v1"
TODAY = date(2026, 8, 9)  # a Sunday → deterministic week windows


# ------------------------------------------------------------------- parser

def test_parse_status_date_and_keywords():
    p = parse("skipped meditation last week", today=TODAY)
    assert p.statuses == {"skipped"}
    assert p.date_label == "last week"
    assert p.start == date(2026, 7, 27) and p.end == date(2026, 8, 2)
    assert p.keywords == ["meditation"]
    assert not p.types


def test_parse_types_and_status():
    p = parse("overdue tasks about design", today=TODAY)
    assert p.types == {"task"}
    assert p.statuses == {"overdue"}
    assert p.keywords == ["design"]


def test_parse_month_and_year():
    p = parse("journal entries in July 2025", today=TODAY)
    assert p.types == {"journal"}
    assert p.start == date(2025, 7, 1) and p.end == date(2025, 7, 31)
    assert p.date_label == "July 2025"


def test_parse_last_n_days():
    p = parse("last 3 days", today=TODAY)
    assert p.start == date(2026, 8, 7) and p.end == TODAY
    assert p.date_label == "last 3 days"


# ------------------------------------------------------------- search (e2e)

def _habit(client, **body):
    body.setdefault("title", "Habit")
    return client.post(f"{BASE}/habits", json=body).json()["id"]


def test_search_skipped_habit_last_week(client, db_session):
    hid = _habit(client, title="Meditate")
    client.post(f"{BASE}/habits/{hid}/logs", json={"date": "2026-07-28", "status": "skipped"})
    client.post(f"{BASE}/habits/{hid}/logs", json={"date": "2026-08-05", "status": "completed"})

    res = SearchService(db_session).search("skipped meditate last week", today=TODAY)
    logs = [r for r in res.results if r.type == "log"]
    assert logs, "expected a matching log"
    assert all(r.status == "skipped" for r in logs)
    assert all(date(2026, 7, 27) <= r.date <= date(2026, 8, 2) for r in logs)
    assert "skipped" in res.interpretation and "last week" in res.interpretation


def test_search_overdue_tasks(client, db_session):
    client.post(f"{BASE}/tasks", json={"title": "Design onboarding", "due_date": "2026-08-01"})
    client.post(f"{BASE}/tasks", json={"title": "Future thing", "due_date": "2026-12-01"})

    res = SearchService(db_session).search("overdue tasks", today=TODAY)
    titles = [r.title for r in res.results if r.type == "task"]
    assert "Design onboarding" in titles
    assert "Future thing" not in titles  # not yet due


def test_search_journal_keyword(client, db_session):
    client.put(f"{BASE}/journal/2026-08-05", json={"wins": "finished the big project launch"})

    res = SearchService(db_session).search("journal about project", today=TODAY)
    js = [r for r in res.results if r.type == "journal"]
    assert js
    assert "project" in (js[0].snippet or "").lower()


def test_search_habit_by_name(client, db_session):
    _habit(client, title="Deep Work", category="focus")
    res = SearchService(db_session).search("deep work", today=TODAY)
    assert any(r.type == "habit" and r.title == "Deep Work" for r in res.results)
