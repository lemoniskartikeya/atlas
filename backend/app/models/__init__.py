"""ORM models. Importing this package registers every table on ``Base.metadata``."""
from app.models.base import Base, OwnedMixin
from app.models.feedback import RecommendationOutcome
from app.models.focus import FocusSession
from app.models.habit import Habit, HabitLog
from app.models.job import JobRun
from app.models.journal import JournalEntry
from app.models.notification import NotificationState
from app.models.note import Note
from app.models.task import Project, Task
from app.models.user import AuthSession, User


def owned_models() -> list[type]:
    """Every mapped class that belongs to an account.

    Derived from the mapper registry rather than hand-listed, so a new
    account-scoped model is covered the moment it inherits ``OwnedMixin`` —
    there is no second place to remember to update.
    """
    return sorted(
        (m.class_ for m in Base.registry.mappers if issubclass(m.class_, OwnedMixin)),
        key=lambda cls: cls.__tablename__,
    )


__all__ = [
    "AuthSession",
    "Base",
    "OwnedMixin",
    "owned_models",
    "JobRun",
    "RecommendationOutcome",
    "FocusSession",
    "Habit",
    "HabitLog",
    "JournalEntry",
    "NotificationState",
    "Note",
    "Project",
    "Task",
    "User",
]
