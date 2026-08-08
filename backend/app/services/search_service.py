"""Natural-language search over the user's data.

Fully local — a transparent rule-based parser turns a phrase like
"skipped meditation last week" or "overdue tasks about design" into structured
filters (types, a date range, statuses, keywords), then searches habit logs,
tasks, journals, habits, and notes. The parse is echoed back as an
``interpretation`` so the user can see exactly how their query was understood.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scoping import current_user_id
from app.domain.enums import OPEN_TASK_STATUSES, TaskStatus
from app.models.note import Note
from app.core.timeutil import local_day
from app.schemas.search import SearchResponse, SearchResult
from app.services.habit_service import HabitService
from app.services.journal_service import JournalService
from app.services.task_service import TaskService

_TYPE_WORDS = {
    "habit": "habit", "habits": "habit",
    "task": "task", "tasks": "task", "todo": "task", "todos": "task",
    "journal": "journal", "journals": "journal", "entry": "journal", "entries": "journal",
    "note": "note", "notes": "note",
}
_STATUS_WORDS = {
    "completed": "completed", "complete": "completed", "done": "completed", "finished": "completed",
    "skipped": "skipped", "missed": "skipped", "skip": "skipped",
    "partial": "partial",
    "open": "open", "pending": "open", "incomplete": "open", "unfinished": "open",
    "overdue": "overdue", "late": "overdue",
}
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})

_STOP = {
    "show", "me", "all", "my", "the", "of", "for", "with", "that", "a", "an", "and",
    "to", "find", "search", "list", "where", "did", "was", "were", "have", "has",
    "about", "from", "on", "in", "i", "any", "which", "what", "when", "days", "day",
}
_LOG_STATUSES = {"completed", "skipped", "partial"}


@dataclass
class ParsedQuery:
    raw: str
    types: set[str] = field(default_factory=set)
    statuses: set[str] = field(default_factory=set)
    start: Optional[date] = None
    end: Optional[date] = None
    date_label: Optional[str] = None
    keywords: list[str] = field(default_factory=list)


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _parse_dates(text: str, today: date) -> tuple[str, Optional[date], Optional[date], Optional[str]]:
    """Consume the first date phrase; return (remaining_text, start, end, label)."""
    monday = today - timedelta(days=today.weekday())

    def take(pattern):
        return re.search(pattern, text)

    # Order matters: most specific first.
    m = take(r"\btoday\b")
    if m:
        return text.replace(m.group(0), " ", 1), today, today, "today"
    m = take(r"\byesterday\b")
    if m:
        y = today - timedelta(days=1)
        return text.replace(m.group(0), " ", 1), y, y, "yesterday"
    m = take(r"\bthis week\b")
    if m:
        return text.replace(m.group(0), " ", 1), monday, today, "this week"
    m = take(r"\blast week\b")
    if m:
        return text.replace(m.group(0), " ", 1), monday - timedelta(days=7), monday - timedelta(days=1), "last week"
    m = take(r"\bthis month\b")
    if m:
        return text.replace(m.group(0), " ", 1), today.replace(day=1), today, "this month"
    m = take(r"\blast month\b")
    if m:
        first = today.replace(day=1)
        prev_end = first - timedelta(days=1)
        return text.replace(m.group(0), " ", 1), prev_end.replace(day=1), prev_end, "last month"
    m = take(r"\bthis year\b")
    if m:
        return text.replace(m.group(0), " ", 1), today.replace(month=1, day=1), today, "this year"
    m = take(r"\b(?:last|past)\s+(\d+)\s+days?\b")
    if m:
        n = max(1, int(m.group(1)))
        return text.replace(m.group(0), " ", 1), today - timedelta(days=n - 1), today, f"last {n} days"
    m = take(r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\b(?:\s+(\d{4}))?")
    if m:
        month = _MONTHS[m.group(1)]
        year = int(m.group(2)) if m.group(2) else today.year
        start = date(year, month, 1)
        end = date(year, month, _last_day(year, month))
        if end > today:
            end = today
        label = f"{calendar.month_name[month]} {year}"
        return text.replace(m.group(0), " ", 1), start, end, label
    m = take(r"\b(20\d{2})\b")
    if m:
        year = int(m.group(1))
        end = date(year, 12, 31)
        if end > today:
            end = today
        return text.replace(m.group(0), " ", 1), date(year, 1, 1), end, str(year)
    return text, None, None, None


def parse(query: str, today: Optional[date] = None) -> ParsedQuery:
    today = today or date.today()
    p = ParsedQuery(raw=query)
    text = f" {query.lower()} "

    text, p.start, p.end, p.date_label = _parse_dates(text, today)

    tokens = re.findall(r"[a-z0-9']+", text)
    leftover: list[str] = []
    for tok in tokens:
        if tok in _TYPE_WORDS:
            p.types.add(_TYPE_WORDS[tok])
        elif tok in _STATUS_WORDS:
            p.statuses.add(_STATUS_WORDS[tok])
        elif tok in _STOP or len(tok) < 2:
            continue
        else:
            leftover.append(tok)
    p.keywords = leftover
    return p


def _hits(keywords: list[str], haystack: str) -> int:
    hay = haystack.lower()
    return sum(1 for k in keywords if k in hay)


def _matches(keywords: list[str], haystack: str) -> bool:
    if not keywords:
        return True
    hay = haystack.lower()
    return all(k in hay for k in keywords)


def _excerpt(text: str, keywords: list[str], width: int = 90) -> Optional[str]:
    text = " ".join(text.split())
    if not text:
        return None
    if keywords:
        low = text.lower()
        for k in keywords:
            i = low.find(k)
            if i >= 0:
                s = max(0, i - 30)
                return ("…" if s > 0 else "") + text[s : s + width].strip() + ("…" if s + width < len(text) else "")
    return text[:width] + ("…" if len(text) > width else "")


_VERB = {"completed": "Completed", "partial": "Partly did", "skipped": "Skipped"}


class SearchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.habits = HabitService(session)
        self.tasks = TaskService(session)
        self.journals = JournalService(session)

    def search(self, query: str, limit: int = 30, today: Optional[date] = None) -> SearchResponse:
        today = today or date.today()
        p = parse(query, today)
        targets = self._targets(p)

        results: list[SearchResult] = []
        if "log" in targets:
            results += self._logs(p)
        if "task" in targets:
            results += self._tasks(p, today)
        if "journal" in targets:
            results += self._journals(p)
        if "habit" in targets:
            results += self._habits(p)
        if "note" in targets:
            results += self._notes(p)

        results.sort(key=lambda r: (r.score, r.date or date.min), reverse=True)
        return SearchResponse(
            query=query,
            interpretation=self._interpretation(p),
            total=len(results),
            results=results[:limit],
        )

    # --------------------------------------------------------- target routing
    @staticmethod
    def _targets(p: ParsedQuery) -> set[str]:
        targets = set(p.types)
        if not targets:
            if p.statuses & _LOG_STATUSES:
                targets.add("log")
            if p.statuses & {"open", "overdue"}:
                targets.add("task")
            if "completed" in p.statuses:
                targets.update({"log", "task"})
            if p.start and not targets:
                targets.update({"log", "task", "journal"})
            if not targets:  # keyword-only or empty
                targets.update({"habit", "task", "journal", "note"})
        # A "habit" query with log-ish filters should surface the logs, too.
        if "habit" in targets and (p.statuses & _LOG_STATUSES or p.start):
            targets.add("log")
        return targets

    # ----------------------------------------------------------------- searchers
    def _logs(self, p: ParsedQuery) -> list[SearchResult]:
        statuses = p.statuses & _LOG_STATUSES
        if not statuses and not p.start:
            return []  # avoid dumping every log
        out: list[SearchResult] = []
        for habit in self.habits.list_habits(include_archived=True):
            if p.keywords and not _matches(p.keywords, f"{habit.title} {habit.category or ''}"):
                continue
            for log in habit.logs:
                if statuses and log.status.value not in statuses:
                    continue
                if p.start and not (p.start <= log.date <= p.end):
                    continue
                out.append(
                    SearchResult(
                        type="log",
                        id=log.id,
                        title=f"{_VERB.get(log.status.value, 'Logged')} {habit.title}",
                        snippet=log.note or log.reason,
                        date=log.date,
                        status=log.status.value,
                        route="/habits",
                        score=6.0 + _hits(p.keywords, habit.title),
                    )
                )
        return out

    def _tasks(self, p: ParsedQuery, today: date) -> list[SearchResult]:
        no_filters = not (p.statuses or p.start or p.keywords)
        out: list[SearchResult] = []
        for t in self.tasks.tasks.list_all():
            if no_filters and t.status not in OPEN_TASK_STATUSES:
                continue
            if "open" in p.statuses and t.status not in OPEN_TASK_STATUSES:
                continue
            if "overdue" in p.statuses and not (
                t.status in OPEN_TASK_STATUSES and t.due_date and t.due_date < today
            ):
                continue
            if "completed" in p.statuses and t.status != TaskStatus.DONE:
                continue
            if p.start:
                d = t.due_date or local_day(t.completed_at)
                if not d or not (p.start <= d <= p.end):
                    continue
            if p.keywords and not _matches(p.keywords, f"{t.title} {t.description or ''}"):
                continue
            when = t.due_date or local_day(t.completed_at)
            out.append(
                SearchResult(
                    type="task",
                    id=t.id,
                    title=t.title,
                    snippet=t.description,
                    date=when,
                    status=t.status.value,
                    route="/tasks",
                    score=5.0 + _hits(p.keywords, f"{t.title} {t.description or ''}"),
                )
            )
        return out

    def _journals(self, p: ParsedQuery) -> list[SearchResult]:
        out: list[SearchResult] = []
        for j in self.journals.recent(2000):
            if p.start and not (p.start <= j.date <= p.end):
                continue
            text = " ".join(
                filter(None, [j.gratitude, j.wins, j.challenges, j.free_writing, j.reflection, j.lessons])
            )
            if p.keywords and not _matches(p.keywords, text):
                continue
            if not p.keywords and not p.start and "journal" not in p.types:
                continue  # keyword-only "match all" shouldn't dump every entry
            out.append(
                SearchResult(
                    type="journal",
                    id=j.date.isoformat(),
                    title=f"Journal · {j.date.isoformat()}",
                    snippet=_excerpt(text, p.keywords),
                    date=j.date,
                    route=f"/journal?date={j.date.isoformat()}",
                    score=5.0 + _hits(p.keywords, text),
                )
            )
        return out

    def _habits(self, p: ParsedQuery) -> list[SearchResult]:
        out: list[SearchResult] = []
        for h in self.habits.list_habits(include_archived=True):
            hay = f"{h.title} {h.description or ''} {h.category or ''}"
            if p.keywords and not _matches(p.keywords, hay):
                continue
            out.append(
                SearchResult(
                    type="habit",
                    id=h.id,
                    title=h.title,
                    snippet=h.category or h.description,
                    route="/habits",
                    score=7.0 + _hits(p.keywords, h.title) * 2,
                )
            )
        return out

    def _notes(self, p: ParsedQuery) -> list[SearchResult]:
        if not p.keywords:
            return []
        out: list[SearchResult] = []
        for n in self.session.scalars(
            select(Note).where(Note.user_id == current_user_id(self.session))
        ):
            hay = f"{n.title} {n.content}"
            if not _matches(p.keywords, hay):
                continue
            out.append(
                SearchResult(
                    type="note",
                    id=n.id,
                    title=n.title,
                    snippet=_excerpt(n.content, p.keywords),
                    date=n.date,
                    score=5.0 + _hits(p.keywords, hay),
                )
            )
        return out

    # ------------------------------------------------------------- interpretation
    @staticmethod
    def _interpretation(p: ParsedQuery) -> str:
        bits: list[str] = []
        if p.types:
            bits.append("/".join(sorted(p.types)))
        if p.statuses:
            bits.append(", ".join(sorted(p.statuses)))
        if p.date_label:
            bits.append(p.date_label)
        if p.keywords:
            bits.append(f"matching “{' '.join(p.keywords)}”")
        return " · ".join(bits) if bits else "everything"
