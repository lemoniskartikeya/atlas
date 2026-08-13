"""Obsidian vault sync endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import scoped_session
from app.services.obsidian_service import ATLAS_FOLDER, ObsidianError, ObsidianService

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


class SyncRequest(BaseModel):
    #: The vault folder lives on this machine, not in the account — the desktop
    #: client remembers it, so no schema change is needed to store a path.
    vault_path: str = Field(min_length=1, max_length=1000)


class SyncResult(BaseModel):
    exported: int
    imported: int
    updated_in_atlas: int
    skipped: int
    conflicts: list[str]
    vault_path: str


class VaultCheck(BaseModel):
    exists: bool
    is_vault: bool
    detail: str


@router.post("/check", response_model=VaultCheck)
def check_vault(payload: SyncRequest):
    """Tell the user what Atlas makes of the folder before it writes anything."""
    path = Path(payload.vault_path).expanduser()
    if not path.exists() or not path.is_dir():
        return VaultCheck(exists=False, is_vault=False, detail="That folder doesn't exist.")
    if (path / ".obsidian").exists():
        return VaultCheck(
            exists=True,
            is_vault=True,
            detail=f"Obsidian vault found. Atlas will use the “{ATLAS_FOLDER}” folder inside it.",
        )
    return VaultCheck(
        exists=True,
        is_vault=False,
        detail=(
            "That folder isn't an Obsidian vault (no .obsidian directory), but Atlas "
            f"can still write its “{ATLAS_FOLDER}” folder there."
        ),
    )


@router.post("/sync", response_model=SyncResult)
def sync(payload: SyncRequest, session=Depends(scoped_session)):
    """Two-way sync: write Atlas out, then read back anything Obsidian changed."""
    try:
        return ObsidianService(session).sync(payload.vault_path)
    except ObsidianError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
