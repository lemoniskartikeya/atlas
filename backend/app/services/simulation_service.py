"""Habit simulator: runs what-if scenarios through the completion model.

Core service (no hard ML import) — it reaches the model through the guarded
gateway, so it returns a graceful "train a model first" response when none
exists instead of erroring.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.simulation import SimulationRequest
from app.services import ml_gateway


class SimulationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(self, request: SimulationRequest, today: Optional[date] = None) -> dict:
        # mode="json" so TimeOfDay -> its string value ("evening"), which both the
        # override maths and the human lever text expect.
        result = ml_gateway.simulate(self.session, request.model_dump(mode="json"), today)
        if result is None:
            return {
                "available": False,
                "summary": "Train the completion model to run what-if simulations.",
                "rows": [],
            }
        return result
