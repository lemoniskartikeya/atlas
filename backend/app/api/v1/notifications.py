"""Smart-notification endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import notification_service
from app.schemas.notification import (
    NotificationAction,
    NotificationActRequest,
    NotificationActResponse,
    NotificationsResponse,
    ResumeRequest,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsResponse)
def list_notifications(svc: NotificationService = Depends(notification_service)):
    return svc.build()


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(payload: NotificationAction, svc: NotificationService = Depends(notification_service)):
    svc.mark_read(payload.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(payload: NotificationAction, svc: NotificationService = Depends(notification_service)):
    svc.dismiss(payload.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/snooze", status_code=status.HTTP_204_NO_CONTENT)
def snooze(payload: NotificationAction, svc: NotificationService = Depends(notification_service)):
    """Quiet one nudge for today. Unlike dismissing, it isn't held against it."""
    svc.snooze(payload.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/act", response_model=NotificationActResponse)
def act(
    payload: NotificationActRequest,
    svc: NotificationService = Depends(notification_service),
):
    """Do what the nudge is about, from the nudge.

    Logs the habit, or completes / defers the task. Refuses anything that
    doesn't apply rather than reporting a success that didn't happen.
    """
    try:
        detail = svc.act(payload.id, payload.action)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return NotificationActResponse(done=True, detail=detail)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(svc: NotificationService = Depends(notification_service)):
    svc.mark_all_read()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/resume", status_code=status.HTTP_204_NO_CONTENT)
def resume(payload: ResumeRequest, svc: NotificationService = Depends(notification_service)):
    """Un-snooze a nudge Atlas backed off from after repeated dismissals."""
    svc.resume(payload.kind, payload.target)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
