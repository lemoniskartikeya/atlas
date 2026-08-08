"""ML endpoints (optional router — only mounted when ML deps are installed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import scoped_session
from app.schemas.ml import MLStatus, PredictionsResponse, TrainOutcome
from app.services.ml_service import MLService

router = APIRouter(prefix="/ml", tags=["ml"])


def _service(session: Session = Depends(scoped_session)) -> MLService:
    return MLService(session)


@router.get("/status", response_model=MLStatus)
def ml_status(svc: MLService = Depends(_service)):
    return svc.status()


@router.post("/train", response_model=TrainOutcome)
def ml_train(svc: MLService = Depends(_service)):
    return svc.train()


@router.get("/predictions", response_model=PredictionsResponse)
def ml_predictions(svc: MLService = Depends(_service)):
    return svc.predict_today()
