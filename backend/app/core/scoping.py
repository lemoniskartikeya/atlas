"""Tenant scoping: which account's data is this session allowed to touch?

Atlas has ~20 services and 30-odd query sites. Relying on every one of them to
remember ``.where(user_id == me)`` is how cross-account leaks happen, so the
identity lives on the **Session** instead of being threaded through every
signature, and two ORM events enforce it centrally:

* ``do_orm_execute`` attaches a :func:`with_loader_criteria` over
  :class:`~app.models.base.OwnedMixin` to every SELECT, including relationship
  and lazy loads. A model is covered the moment it inherits the mixin.
* ``before_flush`` stamps ``user_id`` on newly added rows, so create paths
  can't forget either, and refuses to flush a row belonging to someone else.

Repositories and services still filter explicitly where they build queries.
That is deliberate duplication: the events are the safety net for the query
someone writes next year, not an excuse to write unscoped queries today.

Reads through an *unscoped* session (the scheduler before it picks an account,
the migration runner, the seeder) see everything — the filter only engages once
an identity is bound. Anything serving a request goes through
``app.api.deps.scoped_session``, which always binds one.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.models.base import OwnedMixin

#: Key under which the active account id is stashed on ``Session.info``.
_KEY = "atlas_user_id"

#: Execution option that deliberately opts a statement out of the filter.
#: Used only by code that is legitimately cross-account (the account-claiming
#: backfill, the scheduler enumerating owners).
UNSCOPED = "atlas_unscoped"


class ScopeError(RuntimeError):
    """Raised when a session is asked for an identity it does not have."""


def set_current_user(session: Session, user_id: Optional[str]) -> None:
    """Bind (or with ``None``, unbind) the account this session speaks for."""
    if user_id is None:
        session.info.pop(_KEY, None)
    else:
        session.info[_KEY] = user_id


def current_user_id(session: Session) -> str:
    """The bound account id, for queries that filter explicitly.

    Raises rather than returning ``None``: a service reaching for the current
    account when there isn't one is a bug, and silently returning everything is
    exactly the failure this module exists to prevent.
    """
    uid = session.info.get(_KEY)
    if uid is None:
        raise ScopeError(
            "No account is bound to this session. Request handlers must use "
            "app.api.deps.scoped_session; background work must wrap itself in "
            "app.core.scoping.acting_as()."
        )
    return uid


def maybe_current_user_id(session: Session) -> Optional[str]:
    """The bound account id, or ``None`` — for code that tolerates both."""
    return session.info.get(_KEY)


@contextmanager
def acting_as(session: Session, user_id: Optional[str]) -> Iterator[Session]:
    """Run a block as one account, restoring the previous identity after.

    The scheduler uses this to walk every account in turn on a single session.
    """
    previous = session.info.get(_KEY)
    set_current_user(session, user_id)
    try:
        yield session
    finally:
        set_current_user(session, previous)


# --------------------------------------------------------------------- events


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(execute_state) -> None:
    """Constrain every ORM SELECT to the session's account."""
    if not execute_state.is_select:
        return
    # ``is_column_load`` covers deferred/expired attribute refreshes of a row
    # we already legitimately hold; ``is_relationship_load`` covers a lazy load
    # whose parent query was already filtered. Re-filtering either can only
    # produce spurious misses.
    if execute_state.is_column_load or execute_state.is_relationship_load:
        return
    if execute_state.execution_options.get(UNSCOPED):
        return
    uid = execute_state.session.info.get(_KEY)
    if uid is None:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            OwnedMixin,
            lambda cls: cls.user_id == uid,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _stamp_owner(session: Session, flush_context, instances) -> None:
    """Give every new owned row the session's account, and guard the rest."""
    uid = session.info.get(_KEY)
    if uid is None:
        return
    for obj in session.new:
        if isinstance(obj, OwnedMixin) and obj.user_id is None:
            obj.user_id = uid
    # A row loaded through the filter above already belongs to this account, so
    # a mismatch here means someone constructed one by hand with a foreign id.
    for obj in session.new | session.dirty:
        if isinstance(obj, OwnedMixin) and obj.user_id not in (None, uid):
            raise ScopeError(
                f"{type(obj).__name__} belongs to account {obj.user_id}, but this "
                f"session is acting as {uid}."
            )
