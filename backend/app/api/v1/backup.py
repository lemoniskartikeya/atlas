"""Backup / restore, and plain CSV export."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import backup_service, scoped_session
from app.schemas.backup import BackupImport, BackupResult, CsvDataset, CsvDatasets
from app.services import csv_export
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


# ---------------------------------------------------------------------- CSV
# Separate from the JSON backup above, which exists to be restored. These exist
# to be opened in a spreadsheet, so they are flat and slightly lossy.
@router.get("/csv", response_model=CsvDatasets)
def list_csv_datasets():
    """What can be exported, so the UI doesn't hard-code the list."""
    return CsvDatasets(
        datasets=[
            CsvDataset(key=d.key, label=d.label, description=d.description, columns=d.headers)
            for d in csv_export.DATASETS
        ]
    )


@router.get("/csv/{dataset}")
def export_csv(dataset: str, session: Session = Depends(scoped_session)):
    spec = csv_export.get(dataset)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No dataset called {dataset!r}.")

    body = csv_export.render(spec, session)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{csv_export.filename(dataset)}"',
            # The file is one account's own data; nothing should hold a copy.
            "Cache-Control": "no-store",
        },
    )
