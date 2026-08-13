"""Your data as spreadsheets.

Two things distinguish a CSV export that works from one that looks like it
works: it survives the awkward values people actually type — commas, quotes,
newlines, accents — and it doesn't hand a formula to whoever opens it.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

import pytest

from app.services import csv_export

BASE = "/api/v1"
TODAY = date.today()


def _parse(body: str) -> list[list[str]]:
    """Read the response back the way a spreadsheet would."""
    text = body.lstrip(csv_export.BOM)
    return list(csv.reader(io.StringIO(text)))


def _download(client, dataset: str):
    res = client.get(f"{BASE}/backup/csv/{dataset}")
    assert res.status_code == 200, res.text
    return res


# ------------------------------------------------------------------ the file
def test_every_dataset_downloads_as_a_named_file(client):
    for spec in csv_export.DATASETS:
        res = _download(client, spec.key)
        assert res.headers["content-type"].startswith("text/csv")
        assert f'filename="atlas-{spec.key}-' in res.headers["content-disposition"]
        assert res.headers["cache-control"] == "no-store"


def test_headers_match_what_the_catalogue_promised(client):
    listed = {d["key"]: d["columns"] for d in client.get(f"{BASE}/backup/csv").json()["datasets"]}
    assert listed, "the UI reads this list rather than hard-coding one"

    for key, columns in listed.items():
        rows = _parse(_download(client, key).text)
        assert rows[0] == columns, f"{key} header drifted from its advertised columns"


def test_an_empty_account_still_exports_a_valid_sheet(client):
    """A file with only headers opens fine. A zero-byte file looks broken."""
    rows = _parse(_download(client, "habit_logs").text)
    assert len(rows) == 1 and rows[0][0] == "date"


def test_the_file_starts_with_a_bom(client):
    """Without it Excel reads UTF-8 as the local codepage and mangles accents."""
    assert _download(client, "habits").text.startswith(csv_export.BOM)


def test_an_unknown_dataset_is_a_404(client):
    assert client.get(f"{BASE}/backup/csv/salaries").status_code == 404


# ------------------------------------------------------------- awkward values
def test_commas_quotes_and_newlines_survive_the_round_trip(client):
    nasty = 'Read "War & Peace", slowly\nsecond line'
    client.post(f"{BASE}/habits", json={"title": nasty, "frequency": "daily"})

    rows = _parse(_download(client, "habits").text)
    assert len(rows) == 2
    assert rows[1][0] == nasty, "the title must come back exactly as it went in"


def test_accented_text_survives(client):
    client.post(f"{BASE}/habits", json={"title": "Café résumé — 日本語", "frequency": "daily"})
    rows = _parse(_download(client, "habits").text)
    assert rows[1][0] == "Café résumé — 日本語"


@pytest.mark.parametrize("dangerous", ["=1+1", "+SUM(A1)", "-2+3", "@SUM(A1)"])
def test_a_cell_that_would_run_as_a_formula_is_defused(dangerous):
    """A habit named =HYPERLINK(...) becomes a live link for whoever you send
    the file to. The apostrophe is stripped on display by Excel and Sheets."""
    assert csv_export._safe(dangerous) == "'" + dangerous


def test_ordinary_text_is_left_alone():
    for value in ("Read a book", "10k run", "e=mc2", "a-b", ""):
        assert not csv_export._safe(value).startswith("'"), value


def test_a_negative_number_is_still_readable():
    """Defusing turns it into text, which is the price of not executing it —
    but nothing in the export writes negative numbers into a cell, so no
    numeric column is affected."""
    assert csv_export._safe(-5) == "'-5"


# -------------------------------------------------------------- the contents
def test_the_habit_log_carries_what_was_recorded(client):
    habit = client.post(
        f"{BASE}/habits", json={"title": "Run", "frequency": "daily", "category": "Health"}
    ).json()
    client.post(
        f"{BASE}/habits/{habit['id']}/logs",
        json={
            "date": TODAY.isoformat(),
            "status": "completed",
            "duration_min": 35,
            "mood_after": 4,
            "note": "felt good",
        },
    )

    rows = _parse(_download(client, "habit_logs").text)
    assert len(rows) == 2
    row = dict(zip(rows[0], rows[1]))
    assert row["date"] == TODAY.isoformat()
    assert row["habit"] == "Run"
    assert row["category"] == "Health"
    assert row["status"] == "completed"
    assert row["duration_min"] == "35"
    assert row["mood_after"] == "4"
    assert row["note"] == "felt good"


def test_the_daily_sheet_has_a_row_per_day(client):
    habit = client.post(f"{BASE}/habits", json={"title": "Run", "frequency": "daily"}).json()
    for i in range(3):
        client.post(
            f"{BASE}/habits/{habit['id']}/logs",
            json={"date": (TODAY - timedelta(days=i)).isoformat(), "status": "completed"},
        )

    rows = _parse(_download(client, "daily").text)
    assert len(rows) == 366, "a year of days plus the header"

    today_row = dict(zip(rows[0], rows[-1]))
    assert today_row["date"] == TODAY.isoformat()
    assert today_row["habits_due"] == "1"
    assert today_row["habits_done"] == "1"
    assert today_row["completion_pct"] == "100.0"


def test_tasks_carry_their_project_name_not_its_id(client, db_session):
    """An id in a spreadsheet is a dead end."""
    from app.models.task import Project

    # Projects have no HTTP surface yet, so this goes in through the session.
    project = Project(name="House move")
    db_session.add(project)
    db_session.commit()

    client.post(f"{BASE}/tasks", json={"title": "Book van", "project_id": project.id})

    rows = _parse(_download(client, "tasks").text)
    row = dict(zip(rows[0], rows[1]))
    assert row["project"] == "House move"


def test_a_list_field_becomes_something_readable(client):
    client.post(f"{BASE}/tasks", json={"title": "Ship it", "tags": ["work", "urgent"]})
    rows = _parse(_download(client, "tasks").text)
    assert dict(zip(rows[0], rows[1]))["tags"] == "work, urgent"


def test_missing_values_are_blank_not_the_word_none(client):
    client.post(f"{BASE}/tasks", json={"title": "Someday"})
    rows = _parse(_download(client, "tasks").text)
    row = dict(zip(rows[0], rows[1]))
    assert row["due_date"] == ""
    assert row["completed_on"] == ""
    assert "None" not in rows[1]


def test_booleans_read_as_words(client):
    client.post(f"{BASE}/habits", json={"title": "Old thing", "frequency": "daily"})
    rows = _parse(_download(client, "habits").text)
    assert dict(zip(rows[0], rows[1]))["archived"] == "no"


# ----------------------------------------------------------------- ownership
def test_an_export_contains_only_your_own_data(client, other_client):
    client.post(f"{BASE}/habits", json={"title": "Mine alone", "frequency": "daily"})
    other_client.post(f"{BASE}/habits", json={"title": "Theirs alone", "frequency": "daily"})

    mine = _download(client, "habits").text
    theirs = _download(other_client, "habits").text

    assert "Mine alone" in mine and "Theirs alone" not in mine
    assert "Theirs alone" in theirs and "Mine alone" not in theirs


def test_signing_out_takes_the_export_with_it(anon_client):
    assert anon_client.get(f"{BASE}/backup/csv/habits").status_code in (401, 403)
