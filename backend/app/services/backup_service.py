"""Backup / restore: export all user data to a portable JSON document and
restore it. Encryption is done client-side (the browser encrypts the export
with the user's passphrase before it ever hits disk), so this service only ever
handles plaintext — keeping the passphrase on the user's device.

The dump/load are generic over each model's columns (type-aware for
datetimes, dates, and enums), so new models only need to be added to ``_TABLES``.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.focus import FocusSession
from app.models.habit import Habit, HabitLog
from app.models.journal import JournalEntry
from app.models.note import Note
from app.models.task import Project, Task

BACKUP_VERSION = 1

# Parents before children — insert in this order, delete in reverse.
_TABLES: list[tuple[str, type]] = [
    ("projects", Project),
    ("habits", Habit),
    ("habit_logs", HabitLog),
    ("tasks", Task),
    ("journal_entries", JournalEntry),
    ("notes", Note),
    ("focus_sessions", FocusSession),
]


def _dump(obj) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        v = getattr(obj, col.name)
        if isinstance(v, datetime) or isinstance(v, date):
            v = v.isoformat()
        elif isinstance(v, enum.Enum):
            v = v.value
        out[col.name] = v
    return out


def _coerce(model: type, row: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for col in model.__table__.columns:
        if col.name not in row:
            continue
        v = row[col.name]
        if v is None:
            kwargs[col.name] = None
            continue
        t = col.type
        enum_class = getattr(t, "enum_class", None)
        if isinstance(t, sa.Enum) and enum_class is not None:
            v = enum_class(v)
        elif isinstance(t, sa.DateTime):
            v = datetime.fromisoformat(v)
        elif isinstance(t, sa.Date):
            v = date.fromisoformat(v)
        kwargs[col.name] = v
    return kwargs


class BackupService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def export(self) -> dict:
        data = {
            key: [_dump(o) for o in self.session.scalars(select(model))]
            for key, model in _TABLES
        }
        return {
            "atlas_backup": True,
            "version": BACKUP_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

    def import_(self, data: dict[str, list[dict]]) -> dict:
        # Replace mode: wipe existing rows (children first), then reload.
        for key, model in reversed(_TABLES):
            self.session.query(model).delete()
        self.session.flush()

        counts: dict[str, int] = {}
        for key, model in _TABLES:
            rows = data.get(key, []) or []
            if model is Task:
                counts[key] = self._insert_tasks(rows)
            else:
                for row in rows:
                    self.session.add(model(**_coerce(model, row)))
                counts[key] = len(rows)

        self.session.commit()
        return {"imported": counts, "total": sum(counts.values())}

    def _insert_tasks(self, rows: list[dict]) -> int:
        """Tasks are self-referential — insert with parent_id cleared, then set
        it once every id exists, so a subtask never references a missing parent."""
        parents: dict[str, Any] = {}
        for row in rows:
            payload = _coerce(Task, row)
            parents[payload["id"]] = payload.pop("parent_id", None)
            payload["parent_id"] = None
            self.session.add(Task(**payload))
        self.session.flush()
        for tid, pid in parents.items():
            if pid:
                task = self.session.get(Task, tid)
                if task is not None:
                    task.parent_id = pid
        return len(rows)
