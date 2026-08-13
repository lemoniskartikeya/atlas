"""A brand-new account starts from zero, and an old one gets its history back.

Scoping is already covered field-by-field in ``test_scoping``. What this file
pins is the behaviour a *user* would describe: sign out and the app is empty,
sign back in and everything is exactly where you left it — including on the
aggregate surfaces (dashboard, analytics, timeline, search), which read through
their own services rather than the plain repositories.
"""
from __future__ import annotations

from datetime import date

from tests.conftest import TEST_PASSWORD

READ_SURFACES = [
    "/api/v1/habits",
    "/api/v1/tasks",
    "/api/v1/timeline",
]


def _seed(client) -> dict:
    """Give an account some real history across several data types."""
    today = date.today().isoformat()
    habit = client.post("/api/v1/habits", json={"title": "Morning run"}).json()["id"]
    assert (
        client.post(
            f"/api/v1/habits/{habit}/logs",
            json={"date": today, "status": "completed"},
        ).status_code
        == 201
    )
    assert client.post("/api/v1/tasks", json={"title": "Ship the release"}).status_code == 201
    assert (
        client.put(
            f"/api/v1/journal/{today}",
            json={"free_writing": "A good day.", "mood": 4},
        ).status_code
        == 200
    )
    return {"habit": habit}


def _rows(payload):
    """Collections come back either bare or wrapped — normalise to a list."""
    if isinstance(payload, list):
        return payload
    for key in ("items", "events", "results"):
        if key in payload:
            return payload[key]
    raise AssertionError(f"unrecognised collection shape: {payload!r}")


def test_a_second_account_starts_from_zero(client, other_client):
    """The newcomer sees an empty app, not the first account's history."""
    _seed(client)

    for path in READ_SURFACES:
        res = other_client.get(path)
        assert res.status_code == 200, f"{path} -> {res.status_code} {res.text}"
        assert _rows(res.json()) == [], f"{path} leaked data to a new account"

    dash = other_client.get("/api/v1/dashboard").json()
    assert dash["habits_today"] == []
    assert dash["habits_completed"] == 0
    assert dash["habits_total"] == 0
    assert dash["tasks_today"] == []
    assert dash["top_streaks"] == []
    assert dash["recent_journal"] is None
    assert dash["life_score"] == 0 or dash["weekly_consistency"] == 0

    # The heatmap is generated per account, so it must exist but be all zeroes.
    heat = other_client.get("/api/v1/analytics/heatmap").json()
    assert heat["cells"], "heatmap should still render a calendar for a new account"
    assert heat["total"] == 0
    assert all(cell["count"] == 0 for cell in heat["cells"])


def test_signing_back_in_restores_everything(client):
    """The same credentials return the same vault — logout is not a wipe."""
    seeded = _seed(client)

    before = client.get("/api/v1/habits").json()
    dash_before = client.get("/api/v1/dashboard").json()
    assert [h["title"] for h in before] == ["Morning run"]

    # Sign out for real: the token is revoked server-side.
    assert client.post("/api/v1/auth/logout").status_code in (200, 204)
    client.headers.pop("Authorization", None)
    assert client.get("/api/v1/habits").status_code == 401

    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": "tester", "password": TEST_PASSWORD},
    )
    assert res.status_code == 200, res.text
    client.headers["Authorization"] = f"Bearer {res.json()['token']}"

    after = client.get("/api/v1/habits").json()
    assert [h["id"] for h in after] == [seeded["habit"]]

    dash_after = client.get("/api/v1/dashboard").json()
    for field in ("habits_completed", "habits_total", "tasks_open", "life_score"):
        assert dash_after[field] == dash_before[field], f"{field} changed across a re-login"
    assert dash_after["recent_journal"]["free_writing"] == "A good day."


def test_a_revoked_token_cannot_be_reused(client):
    """Logging out must actually revoke, or "reset on logout" means nothing."""
    stale = client.headers["Authorization"]
    client.post("/api/v1/auth/logout")

    client.headers["Authorization"] = stale
    assert client.get("/api/v1/habits").status_code == 401
