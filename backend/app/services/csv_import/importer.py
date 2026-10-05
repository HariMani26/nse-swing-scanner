"""CSV import: parsing, flexible column mapping, and universe import.

The uploaded CSV's column names are never assumed - the caller (frontend
preview page) maps arbitrary CSV column names to the fields we need
(symbol, company_name, sector). ``guess_column_mapping`` provides a
best-effort default mapping to save the user time, but the user can override
it before importing.
"""
from __future__ import annotations

import io
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Stock

SYMBOL_HINTS = ["symbol", "ticker", "nse code", "nse symbol", "scrip"]
COMPANY_HINTS = ["company", "name", "security name", "company name"]
SECTOR_HINTS = ["sector", "industry"]


def parse_csv(file_bytes: bytes) -> Tuple[List[str], List[dict]]:
    df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    rows = df.to_dict(orient="records")
    return list(df.columns), rows


def _best_match(columns: List[str], hints: List[str]) -> str:
    lower_map = {c: c.lower() for c in columns}
    for hint in hints:
        for col, lower in lower_map.items():
            if lower == hint:
                return col
    for hint in hints:
        for col, lower in lower_map.items():
            if hint in lower:
                return col
    return ""


def guess_column_mapping(columns: List[str]) -> Dict[str, str]:
    return {
        "symbol": _best_match(columns, SYMBOL_HINTS),
        "company_name": _best_match(columns, COMPANY_HINTS),
        "sector": _best_match(columns, SECTOR_HINTS),
    }


def import_rows(
    db: Session,
    rows: List[dict],
    column_mapping: Dict[str, str],
    mode: str = "add",
) -> Tuple[int, int, int]:
    symbol_col = column_mapping.get("symbol")
    if not symbol_col:
        raise ValueError("A 'symbol' column mapping is required")
    company_col = column_mapping.get("company_name")
    sector_col = column_mapping.get("sector")

    if mode == "replace":
        db.query(Stock).update({Stock.is_active: False})

    existing = {s.symbol: s for s in db.query(Stock).all()}
    imported, skipped = 0, 0

    for row in rows:
        raw_symbol = str(row.get(symbol_col, "")).strip().upper()
        if not raw_symbol:
            skipped += 1
            continue
        raw_symbol = raw_symbol.replace(".NS", "").replace(" ", "")
        company_name = str(row.get(company_col, "")).strip() if company_col else ""
        sector = str(row.get(sector_col, "")).strip() if sector_col else ""

        if raw_symbol in existing:
            stock = existing[raw_symbol]
            stock.is_active = True
            if company_name:
                stock.company_name = company_name
            if sector:
                stock.sector = sector
        else:
            stock = Stock(
                symbol=raw_symbol,
                company_name=company_name,
                sector=sector,
                source="csv_import",
                is_active=True,
            )
            db.add(stock)
            existing[raw_symbol] = stock
        imported += 1

    db.commit()
    total_universe = db.query(Stock).filter(Stock.is_active.is_(True)).count()
    return imported, skipped, total_universe
