"""Generic repository base. Repositories own persistence; services own behavior."""
from __future__ import annotations

from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    model: Type[M]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id_: str) -> Optional[M]:
        return self.session.get(self.model, id_)

    def list(self) -> Sequence[M]:
        return list(self.session.scalars(select(self.model)))

    def add(self, obj: M) -> M:
        self.session.add(obj)
        return obj

    def delete(self, obj: M) -> None:
        self.session.delete(obj)

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()
