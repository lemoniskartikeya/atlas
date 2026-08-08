"""FastAPI dependency providers wiring sessions into services.

Every provider below hangs off :func:`scoped_session`, so two things are true
of any endpoint that takes a service: it requires a signed-in account, and the
session it receives already knows which account that is. Nothing in a service
has to ask.

The one deliberate exception is :func:`auth_service`, which has to run *before*
an identity exists in order to establish one.
"""
from __future__ import annotations

from typing import Iterator, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.scoping import acting_as
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
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


# ----------------------------------------------------------------- identity


def auth_service(session: Session = Depends(get_session)) -> AuthService:
    """Unscoped by necessity — this is what decides who you are."""
    return AuthService(session)


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def optional_user(
    authorization: Optional[str] = Header(default=None),
    svc: AuthService = Depends(auth_service),
) -> Optional[User]:
    token = _bearer(authorization)
    return svc.resolve(token) if token else None


def current_user(user: Optional[User] = Depends(optional_user)) -> User:
    """Require a signed-in account. Use on anything account-scoped."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue.")
    return user


def scoped_session(
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Iterator[Session]:
    """A session bound to the caller's account for the life of the request.

    ``acting_as`` restores whatever identity the session had before rather than
    clearing it: in production that is nothing, but the test suite reuses one
    session across both requests and direct service calls, and clearing would
    strand it without an owner halfway through a test.
    """
    with acting_as(session, user.id):
        yield session


# ----------------------------------------------------------------- services


def habit_service(session: Session = Depends(scoped_session)) -> HabitService:
    return HabitService(session)


def task_service(session: Session = Depends(scoped_session)) -> TaskService:
    return TaskService(session)


def journal_service(session: Session = Depends(scoped_session)) -> JournalService:
    return JournalService(session)


def analytics_service(session: Session = Depends(scoped_session)) -> AnalyticsService:
    return AnalyticsService(session)


def dashboard_service(session: Session = Depends(scoped_session)) -> DashboardService:
    return DashboardService(session)


def calendar_service(session: Session = Depends(scoped_session)) -> CalendarService:
    return CalendarService(session)


def planner_service(session: Session = Depends(scoped_session)) -> PlannerService:
    return PlannerService(session)


def prediction_service(session: Session = Depends(scoped_session)) -> PredictionService:
    return PredictionService(session)


def notification_service(
    session: Session = Depends(scoped_session),
) -> NotificationService:
    return NotificationService(session)


def simulation_service(session: Session = Depends(scoped_session)) -> SimulationService:
    return SimulationService(session)


def review_service(session: Session = Depends(scoped_session)) -> WeeklyReviewService:
    return WeeklyReviewService(session)


def timeline_service(session: Session = Depends(scoped_session)) -> TimelineService:
    return TimelineService(session)


def search_service(session: Session = Depends(scoped_session)) -> SearchService:
    return SearchService(session)


def coach_service(session: Session = Depends(scoped_session)) -> CoachService:
    return CoachService(session)


def focus_service(session: Session = Depends(scoped_session)) -> FocusService:
    return FocusService(session)


def backup_service(session: Session = Depends(scoped_session)) -> BackupService:
    return BackupService(session)
