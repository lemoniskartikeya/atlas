"""ORM models. Importing this package registers every table on ``Base.metadata``."""
from app.models.base import Base
from app.models.feedback import RecommendationOutcome
from app.models.focus import FocusSession
from app.models.habit import Habit, HabitLog
from app.models.job import JobRun
from app.models.journal import JournalEntry
from app.models.notification import NotificationState
from app.models.note import Note
from app.models.task import Project, Task
from app.models.user import AuthSession, User

__all__ = [
    "AuthSession",
    "Base",
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
