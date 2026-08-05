"""Project and Task ORM models.

Task supports subtasks via a self-referential parent/children relationship.
Cross-task *dependencies* (a many-to-many DAG) arrive in Phase 2.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import Priority, TaskStatus
from app.models.base import Base, TimestampMixin, UUIDMixin


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    color: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    tasks: Mapped[list["Task"]] = relationship(back_populates="project")


class Task(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None, index=True
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), default=None, index=True
    )

    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=20),
        default=TaskStatus.TODO,
        index=True,
    )
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority, native_enum=False, length=20), default=Priority.MEDIUM
    )
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    labels: Mapped[Optional[list]] = mapped_column(JSON, default=None)

    estimated_effort_min: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    actual_effort_min: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    due_date: Mapped[Optional[date]] = mapped_column(Date, default=None, index=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    scheduled_for: Mapped[Optional[date]] = mapped_column(Date, default=None, index=True)

    context: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    energy_required: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    focus_required: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    location: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )

    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")
    parent: Mapped[Optional["Task"]] = relationship(
        "Task", back_populates="subtasks", remote_side="Task.id"
    )
    subtasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="parent", cascade="all, delete-orphan"
    )
