"""Recommendation-effectiveness DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class FamilyEffectiveness(BaseModel):
    family: str
    label: str
    #: Resolved recommendations of this style.
    shown: int
    #: How many were followed (the nudged habit was completed that day).
    followed: int
    rate: float
    #: Ranking multiplier, or None while the evidence is still too thin.
    weight: Optional[float] = None
    #: True when this family's track record is actually reordering the list.
    influencing: bool = False


class EffectivenessResponse(BaseModel):
    families: list[FamilyEffectiveness]
    total_resolved: int
    #: Resolved samples a family needs before it's allowed to influence ranking.
    min_samples: int
