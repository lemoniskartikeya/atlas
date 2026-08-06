"""Habit-simulator endpoint (what-if scenarios over the completion model)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import simulation_service
from app.schemas.simulation import SimulationRequest, SimulationResponse
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("", response_model=SimulationResponse)
def run_simulation(
    payload: SimulationRequest, svc: SimulationService = Depends(simulation_service)
):
    return svc.run(payload)
