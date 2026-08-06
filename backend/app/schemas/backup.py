"""Backup / restore DTOs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BackupImport(BaseModel):
    atlas_backup: bool = False
    version: int = 1
    data: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class BackupResult(BaseModel):
    imported: dict[str, int]
    total: int
