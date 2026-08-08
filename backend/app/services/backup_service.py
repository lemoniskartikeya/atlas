"""Backup / restore: export all user data to a portable JSON document and
restore it. Encryption is done client-side (the browser encrypts the export
with the user's passphrase before it ever hits disk), so this service only ever
handles plaintext — keeping the passphrase on the user's device.

The dump/load are generic over each model's columns (type-aware for
datetimes, dates, and enums), so new models only need to be added to ``_TABLES``.

Everything here is scoped to the signed-in account. ``user_id`` is deliberately
*stripped* from the export rather than carried: a backup is a document about
your data, not about which row in ``users`` happened to own it, so restoring
into a different account (or onto a fresh install) just works — the ownership
stamp in ``app.core.scoping`` re-assigns each row on the way in.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scoping import UNSCOPED, current_user_id
from app.models.base import new_uuid
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


#: Never travels in a backup — see the module docstring.
_OWNER_COL = "user_id"

_BY_TABLE = {model.__tablename__: model for _key, model in _TABLES}


def _foreign_keys(model: type) -> dict[str, str]:
    """``{column_name: referenced_table}`` for the in-backup references only.

    Derived from the mapper rather than hand-listed, so a new relationship is
    remapped on import automatically.
    """
    out: dict[str, str] = {}
    for col in model.__table__.columns:
        if col.name == _OWNER_COL:
            continue
        for fk in col.foreign_keys:
            target = fk.column.table.name
            if target in _BY_TABLE:
                out[col.name] = target
    return out


def _dump(obj) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        if col.name == _OWNER_COL:
            continue
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
        # Ignore an owner id even if an older or hand-edited document carries
        # one: imported rows always belong to whoever is restoring them.
        if col.name == _OWNER_COL or col.name not in row:
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

    @property
    def user_id(self) -> str:
        return current_user_id(self.session)

    def export(self) -> dict:
        uid = self.user_id
        data = {
            key: [
                _dump(o)
                for o in self.session.scalars(select(model).where(model.user_id == uid))
            ]
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
        # The owner filter here is load-bearing and cannot be delegated to the
        # session-wide scoping: that filter rewrites SELECTs, and this is a
        # bulk DELETE. Without the explicit WHERE, one account restoring a
        # backup would erase every other account's vault.
        uid = self.user_id
        for key, model in reversed(_TABLES):
            self.session.query(model).filter(model.user_id == uid).delete()
        self.session.flush()

        id_map = self._plan_ids(data)

        counts: dict[str, int] = {}
        for key, model in _TABLES:
            rows = data.get(key, []) or []
            if model is Task:
                counts[key] = self._insert_tasks(rows, id_map)
            else:
                for row in rows:
                    self.session.add(model(**self._payload(model, row, id_map)))
                counts[key] = len(rows)

        self.session.commit()
        return {"imported": counts, "total": sum(counts.values())}

    # ------------------------------------------------------------------- ids
    def _plan_ids(self, data: dict[str, list[dict]]) -> dict[str, dict[str, str]]:
        """Decide each incoming row's primary key before anything is inserted.

        Row ids travel in the backup, and after the wipe above they are usually
        free again — restoring your own vault keeps them, which is what makes a
        restore idempotent. But importing *someone else's* export (or a second
        copy of your own into another account) would collide with rows that are
        still there and belong to another account. Those rows get a fresh id,
        and every reference to them is rewritten to match.

        Planned up front, across all tables, so a foreign key can be translated
        no matter which table is inserted first.
        """
        id_map: dict[str, dict[str, str]] = {}
        for key, model in _TABLES:
            table = model.__tablename__
            # Deliberately unscoped: a collision with *another account's* row
            # is precisely what this is looking for, and the session filter
            # would hide exactly those ids. Only primary keys are read — no
            # other account's content is touched.
            taken = set(
                self.session.scalars(
                    select(model.id).execution_options(**{UNSCOPED: True})
                )
            )
            mapping: dict[str, str] = {}
            for row in data.get(key, []) or []:
                old = row.get("id")
                if not old:
                    continue
                new = old if old not in taken else new_uuid()
                taken.add(new)
                mapping[old] = new
            id_map[table] = mapping
        return id_map

    def _payload(
        self, model: type, row: dict[str, Any], id_map: dict[str, dict[str, str]]
    ) -> dict[str, Any]:
        """Coerce a stored row and point it at the ids it will actually have."""
        payload = _coerce(model, row)
        table = model.__tablename__
        if "id" in payload:
            payload["id"] = id_map.get(table, {}).get(payload["id"], payload["id"])
        for column, target in _foreign_keys(model).items():
            value = payload.get(column)
            if value is not None:
                # A reference to a row that isn't in the backup is dropped
                # rather than left dangling.
                payload[column] = id_map.get(target, {}).get(value)
        return payload

    def _insert_tasks(
        self, rows: list[dict], id_map: dict[str, dict[str, str]]
    ) -> int:
        """Tasks are self-referential — insert with parent_id cleared, then set
        it once every id exists, so a subtask never references a missing parent."""
        parents: dict[str, Any] = {}
        added: dict[str, Task] = {}
        for row in rows:
            payload = self._payload(Task, row, id_map)
            parents[payload["id"]] = payload.pop("parent_id", None)
            payload["parent_id"] = None
            task = Task(**payload)
            added[payload["id"]] = task
            self.session.add(task)
        self.session.flush()
        # Hold the objects we just created rather than re-fetching by id: these
        # are unambiguously ours, and a lookup could only reintroduce doubt.
        for tid, pid in parents.items():
            if pid and tid in added:
                added[tid].parent_id = pid
        return len(rows)
