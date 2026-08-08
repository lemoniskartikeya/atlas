"""Generic repository base. Repositories own persistence; services own behavior."""
from __future__ import annotations

from typing import Any, Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.scoping import current_user_id
from app.models.base import Base, OwnedMixin

M = TypeVar("M", bound=Base)


class BaseRepository(Generic[M]):
    model: Type[M]

    def __init__(self, session: Session) -> None:
        self.session = session

    # ----------------------------------------------------------------- scoping
    @property
    def user_id(self) -> str:
        """The account this repository is acting for."""
        return current_user_id(self.session)

    def scoped(self, stmt: Select[Any]) -> Select[Any]:
        """Constrain a statement to the current account.

        ``app.core.scoping`` already filters ORM selects session-wide; doing it
        here too means a query is scoped by its own text, which is what makes
        subclasses readable and keeps the guarantee if the events are ever
        bypassed.
        """
        if issubclass(self.model, OwnedMixin):
            return stmt.where(self.model.user_id == self.user_id)
        return stmt

    def get(self, id_: str) -> Optional[M]:
        # Deliberately not ``Session.get``: that consults the identity map
        # first and would hand back another account's row if this session had
        # already loaded it. A real SELECT with the owner in the WHERE clause
        # cannot.
        return self.session.scalars(
            self.scoped(select(self.model).where(self.model.id == id_))
        ).first()

    def list(self) -> Sequence[M]:
        return list(self.session.scalars(self.scoped(select(self.model))))

    def add(self, obj: M) -> M:
        self.session.add(obj)
        return obj

    def delete(self, obj: M) -> None:
        self.session.delete(obj)

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()
