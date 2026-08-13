"""Two-way sync between Atlas and an Obsidian vault.

Obsidian is a folder of Markdown files, so "integrating" with it means writing
files it can read and reading files it wrote. Nothing is installed and no
plugin is required — Atlas writes into a subfolder of the vault the user picks,
and Obsidian sees them on its next scan.

Design decisions worth keeping:

* **The vault path comes from the request, not the database.** It is a property
  of this machine, not of the account, and passing it per call avoids a schema
  migration for something the desktop client can remember locally.
* **Frontmatter carries the identity** (`atlas_id`), so a file can be renamed
  or moved inside the vault and still update the right row.
* **Last edit wins, and the loser is reported.** Silently discarding an edit
  someone made in Obsidian would be the worst possible failure here, so every
  decision comes back in the result for the UI to show.
* **A file Atlas has never seen is imported, not ignored** — that is how you
  write a journal entry in Obsidian and have it appear in Atlas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.scoping import current_user_id
from app.core.timeutil import local_day
from app.models.journal import JournalEntry
from app.models.note import Note

log = get_logger("atlas.obsidian")

#: Everything Atlas owns lives under here, so the rest of the vault is untouched.
ATLAS_FOLDER = "Atlas"
JOURNAL_FOLDER = "Journal"
NOTES_FOLDER = "Notes"

#: The journal's prose fields, in the order they appear in the file.
JOURNAL_SECTIONS = [
    ("gratitude", "Gratitude"),
    ("wins", "Wins"),
    ("challenges", "Challenges"),
    ("lessons", "Lessons"),
    ("reflection", "Reflection"),
    ("free_writing", "Notes"),
]

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ObsidianError(RuntimeError):
    """Something about the vault itself is wrong — shown to the user verbatim."""


@dataclass
class SyncReport:
    exported: int = 0
    imported: int = 0
    updated_in_atlas: int = 0
    skipped: int = 0
    conflicts: list[str] = field(default_factory=list)
    vault_path: str = ""

    def as_dict(self) -> dict:
        return {
            "exported": self.exported,
            "imported": self.imported,
            "updated_in_atlas": self.updated_in_atlas,
            "skipped": self.skipped,
            "conflicts": self.conflicts,
            "vault_path": self.vault_path,
        }


# ------------------------------------------------------------------ frontmatter
def _fm_value(raw: str) -> Any:
    """Parse the small subset of YAML we write. No dependency, no surprises."""
    raw = raw.strip()
    if raw in ("", "~", "null"):
        return None
    if raw in ("true", "false"):
        return raw == "true"
    if raw.startswith(("'", '"')) and raw.endswith(("'", '"')) and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [p.strip().strip("'\"") for p in inner.split(",")] if inner else []
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a Markdown file into its frontmatter mapping and its body."""
    match = _FRONTMATTER.match(text.replace("\r\n", "\n"))
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = _fm_value(value)
    return meta, match.group(2)


def _dump_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def safe_filename(name: str, fallback: str = "Untitled") -> str:
    """A filename Obsidian and every OS will accept, without collapsing detail."""
    cleaned = _ILLEGAL.sub("", (name or "").strip()).strip(". ")
    return (cleaned or fallback)[:120]


# ---------------------------------------------------------------- the service
class ObsidianService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ paths
    def _root(self, vault_path: str) -> Path:
        if not (vault_path or "").strip():
            raise ObsidianError("Choose your Obsidian vault folder first.")
        vault = Path(vault_path).expanduser()
        if not vault.exists() or not vault.is_dir():
            raise ObsidianError(f"That folder doesn't exist: {vault}")
        # A vault is just a folder, but .obsidian is the one reliable marker.
        # Warn rather than refuse — people sync a subfolder deliberately.
        if not (vault / ".obsidian").exists():
            log.info("obsidian.no_marker", extra={"path": str(vault)})
        root = vault / ATLAS_FOLDER
        (root / JOURNAL_FOLDER).mkdir(parents=True, exist_ok=True)
        (root / NOTES_FOLDER).mkdir(parents=True, exist_ok=True)
        return root

    # ----------------------------------------------------------------- render
    def _journal_markdown(self, entry: JournalEntry) -> str:
        meta = {
            "atlas_id": entry.id,
            "atlas_type": "journal",
            "date": entry.date.isoformat(),
            "mood": entry.mood,
            "energy": entry.energy,
            "sleep_hours": entry.sleep_hours,
            "updated": _iso(entry.updated_at),
        }
        parts = [_dump_frontmatter(meta), "", f"# {entry.date.isoformat()}", ""]
        for attr, heading in JOURNAL_SECTIONS:
            value = (getattr(entry, attr, None) or "").strip()
            if value:
                parts += [f"## {heading}", "", value, ""]
        return "\n".join(parts).rstrip() + "\n"

    def _note_markdown(self, note: Note) -> str:
        meta = {
            "atlas_id": note.id,
            "atlas_type": "note",
            "title": note.title,
            "tags": note.tags or None,
            "date": note.date.isoformat() if note.date else None,
            "updated": _iso(note.updated_at),
        }
        return f"{_dump_frontmatter(meta)}\n\n{(note.content or '').strip()}\n"

    # ------------------------------------------------------------------- sync
    def sync(self, vault_path: str) -> dict:
        """Push Atlas → vault, then pull anything the vault changed back.

        Export first so a brand-new vault is populated before we look for
        incoming edits; the import pass then only sees genuine outside changes.
        """
        root = self._root(vault_path)
        report = SyncReport(vault_path=str(root))

        self._export(root, report)
        self._import(root, report)
        self.session.commit()

        log.info("obsidian.synced", extra=report.as_dict())
        return report.as_dict()

    # ----------------------------------------------------------------- export
    def _export(self, root: Path, report: SyncReport) -> None:
        for entry in self._journals():
            path = root / JOURNAL_FOLDER / f"{entry.date.isoformat()}.md"
            if self._write_if_newer(path, self._journal_markdown(entry), entry.updated_at, report):
                report.exported += 1

        used: set[str] = set()
        for note in self._notes():
            name = safe_filename(note.title, "Untitled")
            # Two notes may share a title; keep both by disambiguating with the id.
            if name.lower() in used:
                name = f"{name} ({note.id[:8]})"
            used.add(name.lower())
            path = root / NOTES_FOLDER / f"{name}.md"
            if self._write_if_newer(path, self._note_markdown(note), note.updated_at, report):
                report.exported += 1

    def _write_if_newer(
        self, path: Path, content: str, updated_at: Optional[datetime], report: SyncReport
    ) -> bool:
        """Write unless the file on disk has been edited more recently.

        Overwriting a newer file would silently destroy something the user
        typed in Obsidian, so that case is left for the import pass to pick up.
        """
        if path.exists():
            if path.read_text(encoding="utf-8") == content:
                return False  # identical — don't churn the mtime
            disk = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            atlas = _aware(updated_at)
            if atlas and disk > atlas:
                report.skipped += 1
                return False
        path.write_text(content, encoding="utf-8")
        return True

    # ----------------------------------------------------------------- import
    def _import(self, root: Path, report: SyncReport) -> None:
        journals = {e.id: e for e in self._journals()}
        notes = {n.id: n for n in self._notes()}

        for path in sorted((root / JOURNAL_FOLDER).glob("*.md")):
            self._import_journal(path, journals, report)
        for path in sorted((root / NOTES_FOLDER).glob("*.md")):
            self._import_note(path, notes, report)

    def _import_journal(self, path: Path, existing: dict, report: SyncReport) -> None:
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        sections = _split_sections(body)

        entry = existing.get(str(meta.get("atlas_id") or ""))
        if entry is None:
            # No id, or an id Atlas doesn't know: fall back to the date, which
            # is what a hand-written "2026-08-13.md" in the vault will have.
            day = _parse_date(meta.get("date")) or _parse_date(path.stem)
            if day is None:
                report.skipped += 1
                return
            entry = self.session.scalars(
                select(JournalEntry).where(JournalEntry.date == day)
            ).first()
            if entry is None:
                entry = JournalEntry(date=day)
                self.session.add(entry)
                self._apply_journal(entry, meta, sections)
                report.imported += 1
                return

        if not self._file_is_newer(path, entry.updated_at):
            return
        if self._apply_journal(entry, meta, sections):
            report.updated_in_atlas += 1
            report.conflicts.append(f"Journal {entry.date.isoformat()} updated from Obsidian")

    def _import_note(self, path: Path, existing: dict, report: SyncReport) -> None:
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        content = body.strip()

        note = existing.get(str(meta.get("atlas_id") or ""))
        if note is None:
            # A Markdown file someone created in Obsidian — bring it in.
            note = Note(
                title=str(meta.get("title") or path.stem),
                content=content,
                tags=meta.get("tags") or None,
                date=_parse_date(meta.get("date")),
            )
            self.session.add(note)
            report.imported += 1
            return

        if not self._file_is_newer(path, note.updated_at):
            return
        changed = note.content != content or note.title != str(meta.get("title") or note.title)
        note.content = content
        note.title = str(meta.get("title") or path.stem)
        if meta.get("tags") is not None:
            note.tags = meta.get("tags") or None
        if changed:
            report.updated_in_atlas += 1
            report.conflicts.append(f"Note “{note.title}” updated from Obsidian")

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _file_is_newer(path: Path, updated_at: Optional[datetime]) -> bool:
        disk = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        atlas = _aware(updated_at)
        return atlas is None or disk > atlas

    @staticmethod
    def _apply_journal(entry: JournalEntry, meta: dict, sections: dict) -> bool:
        changed = False
        for attr, heading in JOURNAL_SECTIONS:
            incoming = sections.get(heading.lower())
            if incoming is not None and (getattr(entry, attr, None) or "") != incoming:
                setattr(entry, attr, incoming)
                changed = True
        for field_name in ("mood", "energy", "sleep_hours"):
            value = meta.get(field_name)
            if value is not None and getattr(entry, field_name, None) != value:
                setattr(entry, field_name, value)
                changed = True
        return changed

    def _journals(self) -> Iterable[JournalEntry]:
        return self.session.scalars(
            select(JournalEntry)
            .where(JournalEntry.user_id == current_user_id(self.session))
            .order_by(JournalEntry.date)
        ).all()

    def _notes(self) -> Iterable[Note]:
        return self.session.scalars(
            select(Note)
            .where(Note.user_id == current_user_id(self.session))
            .order_by(Note.created_at)
        ).all()


def _split_sections(body: str) -> dict[str, str]:
    """Turn `## Heading` blocks back into a mapping, so a round-trip is lossless."""
    sections: dict[str, str] = {}
    current: Optional[str] = None
    buffer: list[str] = []
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.startswith("## "):
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip().lower()
            buffer = []
        elif current:
            buffer.append(line)
    if current:
        sections[current] = "\n".join(buffer).strip()
    return sections


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, AttributeError):
        return None


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """Stored timestamps are naive UTC; compare them in UTC, never local."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _iso(value: Optional[datetime]) -> Optional[str]:
    aware = _aware(value)
    return aware.isoformat() if aware else None
