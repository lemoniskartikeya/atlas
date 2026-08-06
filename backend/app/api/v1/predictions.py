"""Prediction-engine endpoint — forward-looking, explainable outlook."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import prediction_service
from app.schemas.prediction import PredictionReport
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("", response_model=PredictionReport)
def get_predictions(svc: PredictionService = Depends(prediction_service)):
    return svc.build()
