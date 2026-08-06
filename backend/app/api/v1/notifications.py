"""Smart-notification endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import notification_service
from app.schemas.notification import NotificationAction, NotificationsResponse
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


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(svc: NotificationService = Depends(notification_service)):
    svc.mark_all_read()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
