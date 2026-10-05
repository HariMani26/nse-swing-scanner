"""CSV upload / preview / flexible-mapping import endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CsvImportRequest, CsvImportResult, CsvPreviewOut
from app.services.csv_import.importer import guess_column_mapping, import_rows, parse_csv

router = APIRouter(prefix="/api/csv", tags=["csv"])


@router.post("/preview", response_model=CsvPreviewOut)
async def preview_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    content = await file.read()
    try:
        columns, rows = parse_csv(content)
    except Exception as exc:
        raise HTTPException(400, f"Could not parse CSV: {exc}") from exc

    return CsvPreviewOut(columns=columns, rows=rows, row_count=len(rows))


@router.get("/suggest-mapping")
def suggest_mapping(columns: str):
    """Given comma-separated column names, return a best-effort field mapping."""
    cols = [c.strip() for c in columns.split(",") if c.strip()]
    return guess_column_mapping(cols)


@router.post("/import", response_model=CsvImportResult)
def import_csv(payload: CsvImportRequest, db: Session = Depends(get_db)):
    if payload.mode not in ("add", "replace"):
        raise HTTPException(400, "mode must be 'add' or 'replace'")
    try:
        imported, skipped, total_universe = import_rows(
            db, payload.rows, payload.column_mapping, payload.mode
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return CsvImportResult(imported=imported, skipped=skipped, mode=payload.mode, total_universe=total_universe)
