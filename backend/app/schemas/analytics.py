"""Analytics API DTOs."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class HeatmapCell(BaseModel):
    date: date
    count: int
    level: int  # 0..4 intensity bucket for rendering


class HeatmapResponse(BaseModel):
    start: date
    end: date
    total: int
    max_count: int
    cells: list[HeatmapCell]
