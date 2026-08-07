"""FastAPI dependency providers wiring sessions into services."""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.services.analytics_service import AnalyticsService
from app.services.backup_service import BackupService
from app.services.calendar_service import CalendarService
from app.services.coach_service import CoachService
from app.services.dashboard_service import DashboardService
from app.services.focus_service import FocusService
from app.services.habit_service import HabitService
from app.services.journal_service import JournalService
from app.services.notification_service import NotificationService
from app.services.planner_service import PlannerService
from app.services.prediction_service import PredictionService
from app.services.review_service import WeeklyReviewService
from app.services.search_service import SearchService
from app.services.simulation_service import SimulationService
from app.services.task_service import TaskService
from app.services.timeline_service import TimelineService


def habit_service(session: Session = Depends(get_session)) -> HabitService:
    return HabitService(session)


def task_service(session: Session = Depends(get_session)) -> TaskService:
    return TaskService(session)


def journal_service(session: Session = Depends(get_session)) -> JournalService:
    return JournalService(session)


def analytics_service(session: Session = Depends(get_session)) -> AnalyticsService:
    return AnalyticsService(session)


def dashboard_service(session: Session = Depends(get_session)) -> DashboardService:
    return DashboardService(session)


def calendar_service(session: Session = Depends(get_session)) -> CalendarService:
    return CalendarService(session)


def planner_service(session: Session = Depends(get_session)) -> PlannerService:
    return PlannerService(session)


def prediction_service(session: Session = Depends(get_session)) -> PredictionService:
    return PredictionService(session)


def notification_service(session: Session = Depends(get_session)) -> NotificationService:
    return NotificationService(session)


def simulation_service(session: Session = Depends(get_session)) -> SimulationService:
    return SimulationService(session)


def review_service(session: Session = Depends(get_session)) -> WeeklyReviewService:
    return WeeklyReviewService(session)


def timeline_service(session: Session = Depends(get_session)) -> TimelineService:
    return TimelineService(session)


def search_service(session: Session = Depends(get_session)) -> SearchService:
    return SearchService(session)


def coach_service(session: Session = Depends(get_session)) -> CoachService:
    return CoachService(session)


def focus_service(session: Session = Depends(get_session)) -> FocusService:
    return FocusService(session)


def backup_service(session: Session = Depends(get_session)) -> BackupService:
    return BackupService(session)
