"""Smart scheduler ("Today's Plan") DTOs.

The planner keeps the same explainability contract as the recommendation engine:
every placed item ships a ``reason`` and a ``confidence``. When a trained
completion model is available, items also carry a ``probability`` and a coarse
``risk`` bucket so the UI can show *why* the order is what it is.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class PlanItem(BaseModel):
    id: str
    kind: str  # "habit" | "task"
    title: str
    color: Optional[str] = None
    duration_min: Optional[int] = None
    priority: Optional[str] = None
    done: bool = False
    probability: Optional[float] = None  # model completion probability (habits, when trained)
    risk: Optional[str] = None  # "at-risk" | "steady" | None
    reason: str  # why it's placed here / in this order
    confidence: float  # 0..1


class PlanBlock(BaseModel):
    key: str  # "morning" | "afternoon" | "evening"
    label: str
    window: str  # human-readable window, e.g. "Before noon"
    is_now: bool  # the block the current hour falls in
    minutes: int  # estimated minutes of not-yet-done work in the block
    items: list[PlanItem]


class PlanResponse(BaseModel):
    date: date
    generated_at: datetime
    now_hour: int
    now_block: str
    model_backed: bool  # True when a trained model shaped the ordering
    reliability: Optional[float] = None  # model held-out ROC-AUC, when model-backed
    summary: str  # one-line, human-readable plan headline
    open_count: int  # not-yet-done items across all blocks
    total_minutes: int
    blocks: list[PlanBlock]


class PlanInteractionIn(BaseModel):
    """What the user did with one suggestion.

    The block and rank are the ones actually rendered, reported back by the
    client — that is what the user saw and reacted to. The server supplies the
    date and the hour, so a wrong clock on the client cannot rewrite history.
    """

    item_kind: str  # "habit" | "task"
    item_id: str
    action: str  # "completed" | "deferred" | "dismissed"
    suggested_block: str  # "morning" | "afternoon" | "evening"
    suggested_rank: Optional[int] = None


class PlanInteractionOut(BaseModel):
    recorded: bool
    item_id: str
    action: str
    suggested_block: str
    #: Where the user actually was. Differs from suggested_block exactly when
    #: this counts as a correction.
    actual_block: Optional[str] = None
    corrected: bool


class DeferRequest(BaseModel):
    """Push a planned task to another day.

    `days` rather than a date so the common case needs no client-side date
    arithmetic; the server owns "tomorrow", which is the only way it agrees
    with the plan the server built.
    """

    task_id: str
    days: int = 1
    #: Where it was sitting when you moved it, for the correction record.
    suggested_block: Optional[str] = None


class DeferResponse(BaseModel):
    task_id: str
    title: str
    scheduled_for: date
    #: True when the new day is past the deadline — deferring never moves a due
    #: date, so this stays visible rather than being quietly resolved.
    still_overdue: bool
    detail: str
