"""Obsidian sync: a round-trip through Markdown that loses nothing.

Obsidian is a folder of Markdown files, so these tests work on a real temp
folder rather than mocking the filesystem — the whole feature is about what
ends up on disk and what comes back off it.
"""
from __future__ import annotations

import os
import time
from datetime import date

import pytest

from app.services.obsidian_service import parse_frontmatter, safe_filename

BASE = "/api/v1"


@pytest.fixture()
def vault(tmp_path):
    """A folder that looks like a real Obsidian vault."""
    root = tmp_path / "MyVault"
    (root / ".obsidian").mkdir(parents=True)
    return root


def _journal(client, day: str, **fields):
    res = client.put(f"{BASE}/journal/{day}", json=fields)
    assert res.status_code == 200, res.text
    return res.json()


def _sync(client, vault):
    res = client.post(f"{BASE}/obsidian/sync", json={"vault_path": str(vault)})
    assert res.status_code == 200, res.text
    return res.json()


def _touch_newer(path):
    """Make a file look edited after Atlas wrote it.

    Sync compares the file's mtime against the row's updated_at, and a test can
    easily write both inside the same clock tick — so push the mtime forward
    explicitly rather than sleeping and hoping.
    """
    future = time.time() + 10
    os.utime(path, (future, future))


# ------------------------------------------------------------------- the vault
def test_check_recognises_a_real_vault(client, vault):
    body = client.post(f"{BASE}/obsidian/check", json={"vault_path": str(vault)}).json()
    assert body["exists"] is True and body["is_vault"] is True


def test_check_accepts_a_plain_folder_but_says_so(client, tmp_path):
    plain = tmp_path / "just-a-folder"
    plain.mkdir()
    body = client.post(f"{BASE}/obsidian/check", json={"vault_path": str(plain)}).json()
    assert body["exists"] is True and body["is_vault"] is False
    assert "isn't an Obsidian vault" in body["detail"]


def test_a_missing_folder_is_refused_rather_than_created(client, tmp_path):
    missing = tmp_path / "nope"
    res = client.post(f"{BASE}/obsidian/sync", json={"vault_path": str(missing)})
    assert res.status_code == 400
    assert not missing.exists()


# ----------------------------------------------------------------- Atlas → vault
def test_journal_is_written_as_readable_markdown(client, vault):
    _journal(client, "2026-08-13", free_writing="Shipped the sync.", mood=4, sleep_hours=7.5)
    report = _sync(client, vault)

    path = vault / "Atlas" / "Journal" / "2026-08-13.md"
    assert path.exists()
    assert report["exported"] >= 1

    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["atlas_type"] == "journal"
    assert meta["date"] == "2026-08-13"
    assert meta["mood"] == 4
    assert meta["sleep_hours"] == 7.5
    assert meta["atlas_id"]  # identity survives a rename inside the vault
    assert "Shipped the sync." in body
    assert "## Notes" in body  # prose lands under a heading, not raw frontmatter


def test_sync_only_touches_its_own_folder(client, vault):
    theirs = vault / "Daily" / "2026-08-13.md"
    theirs.parent.mkdir(parents=True)
    theirs.write_text("# My own note\nUntouched.", encoding="utf-8")

    _journal(client, "2026-08-13", free_writing="Atlas entry.")
    _sync(client, vault)

    assert theirs.read_text(encoding="utf-8") == "# My own note\nUntouched."


def test_an_unchanged_entry_is_not_rewritten(client, vault):
    _journal(client, "2026-08-13", free_writing="Steady.")
    _sync(client, vault)
    path = vault / "Atlas" / "Journal" / "2026-08-13.md"
    before = path.stat().st_mtime_ns

    second = _sync(client, vault)
    assert path.stat().st_mtime_ns == before, "identical content should not churn the file"
    assert second["exported"] == 0


# ----------------------------------------------------------------- vault → Atlas
def test_an_edit_in_obsidian_comes_back_into_atlas(client, vault):
    _journal(client, "2026-08-13", free_writing="First draft.")
    _sync(client, vault)

    path = vault / "Atlas" / "Journal" / "2026-08-13.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("First draft.", "Edited in Obsidian."),
        encoding="utf-8",
    )
    _touch_newer(path)

    report = _sync(client, vault)
    assert report["updated_in_atlas"] == 1
    assert report["conflicts"]

    entry = client.get(f"{BASE}/journal/2026-08-13").json()
    assert entry["free_writing"] == "Edited in Obsidian."


def test_a_journal_written_by_hand_in_obsidian_is_imported(client, vault):
    """No atlas_id — the filename is the only clue, and it is enough."""
    folder = vault / "Atlas" / "Journal"
    folder.mkdir(parents=True)
    (folder / "2026-08-12.md").write_text(
        "---\nmood: 5\n---\n\n## Wins\n\nWrote this in Obsidian.\n", encoding="utf-8"
    )

    report = _sync(client, vault)
    assert report["imported"] >= 1

    entry = client.get(f"{BASE}/journal/2026-08-12").json()
    assert entry["wins"] == "Wrote this in Obsidian."
    assert entry["mood"] == 5


def test_atlas_does_not_overwrite_a_newer_file(client, vault):
    """The worst possible failure here is silently destroying someone's writing."""
    _journal(client, "2026-08-13", free_writing="From Atlas.")
    _sync(client, vault)

    path = vault / "Atlas" / "Journal" / "2026-08-13.md"
    edited = path.read_text(encoding="utf-8").replace("From Atlas.", "Newer, from Obsidian.")
    path.write_text(edited, encoding="utf-8")
    _touch_newer(path)

    _sync(client, vault)
    assert "Newer, from Obsidian." in path.read_text(encoding="utf-8")


def test_a_full_round_trip_preserves_every_section(client, vault):
    _journal(
        client,
        "2026-08-13",
        gratitude="Coffee.",
        wins="Shipped it.",
        challenges="The blur.",
        lessons="Measure first.",
        reflection="Good day.",
        free_writing="Longer thoughts.",
        mood=4,
        energy=3,
    )
    _sync(client, vault)

    path = vault / "Atlas" / "Journal" / "2026-08-13.md"
    _touch_newer(path)  # force the import pass to read it back
    _sync(client, vault)

    entry = client.get(f"{BASE}/journal/2026-08-13").json()
    assert entry["gratitude"] == "Coffee."
    assert entry["wins"] == "Shipped it."
    assert entry["challenges"] == "The blur."
    assert entry["lessons"] == "Measure first."
    assert entry["reflection"] == "Good day."
    assert entry["free_writing"] == "Longer thoughts."
    assert entry["mood"] == 4 and entry["energy"] == 3


# ---------------------------------------------------------------- other vaults
def test_one_accounts_vault_never_receives_anothers_writing(client, other_client, vault):
    _journal(client, "2026-08-13", free_writing="Mine, private.")
    _sync(client, vault)

    other_vault = vault.parent / "TheirVault"
    (other_vault / ".obsidian").mkdir(parents=True)
    _sync(other_client, other_vault)

    exported = list((other_vault / "Atlas" / "Journal").glob("*.md"))
    assert exported == [], "another account's journal reached this vault"


# --------------------------------------------------------------------- helpers
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Normal Title", "Normal Title"),
        ("with/slash", "withslash"),
        ('bad:"chars"?', "badchars"),
        ("   ", "Untitled"),
        ("", "Untitled"),
    ],
)
def test_filenames_stay_legal_without_collapsing_detail(raw, expected):
    assert safe_filename(raw) == expected


def test_frontmatter_parses_the_subset_we_write():
    meta, body = parse_frontmatter(
        "---\nmood: 4\nsleep_hours: 7.5\ntitle: A Note\ntags: [a, b]\ndone: true\n---\n\nBody.\n"
    )
    assert meta == {
        "mood": 4,
        "sleep_hours": 7.5,
        "title": "A Note",
        "tags": ["a", "b"],
        "done": True,
    }
    assert body.strip() == "Body."


def test_a_file_without_frontmatter_is_all_body():
    meta, body = parse_frontmatter("# Just a heading\n\nText.\n")
    assert meta == {}
    assert "Just a heading" in body
