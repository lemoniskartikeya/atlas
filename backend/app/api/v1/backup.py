"""Backup / restore endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import backup_service
from app.schemas.backup import BackupImport, BackupResult
from app.services.backup_service import BackupService

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("/export")
def export_backup(svc: BackupService = Depends(backup_service)):
    return svc.export()


@router.post("/import", response_model=BackupResult)
def import_backup(payload: BackupImport, svc: BackupService = Depends(backup_service)):
    if not payload.atlas_backup or not payload.data:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Not a valid Atlas backup file."
        )
    return svc.import_(payload.data)
