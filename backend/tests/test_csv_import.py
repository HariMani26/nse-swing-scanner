"""Tests for CSV parsing, flexible column mapping, and universe import."""
from __future__ import annotations

from app.models import Stock
from app.services.csv_import.importer import guess_column_mapping, import_rows, parse_csv


SAMPLE_CSV = (
    b"Symbol,Company Name,Sector,52 Week High,Price\n"
    b"RELIANCE,Reliance Industries,Energy,3000,2800\n"
    b"TCS,Tata Consultancy Services,IT,4500,4100\n"
)

SAMPLE_CSV_ODD_HEADERS = (
    b"NSE Symbol,Security Name,Industry\n"
    b"INFY,Infosys Ltd,IT\n"
)


def test_parse_csv_returns_columns_and_rows():
    columns, rows = parse_csv(SAMPLE_CSV)
    assert columns == ["Symbol", "Company Name", "Sector", "52 Week High", "Price"]
    assert len(rows) == 2
    assert rows[0]["Symbol"] == "RELIANCE"


def test_guess_column_mapping_finds_standard_headers():
    columns, _ = parse_csv(SAMPLE_CSV)
    mapping = guess_column_mapping(columns)
    assert mapping["symbol"] == "Symbol"
    assert mapping["company_name"] == "Company Name"
    assert mapping["sector"] == "Sector"


def test_guess_column_mapping_handles_unusual_headers():
    columns, _ = parse_csv(SAMPLE_CSV_ODD_HEADERS)
    mapping = guess_column_mapping(columns)
    assert mapping["symbol"] == "NSE Symbol"
    assert mapping["company_name"] == "Security Name"
    assert mapping["sector"] == "Industry"


def test_import_rows_add_mode_creates_stocks(db_session):
    columns, rows = parse_csv(SAMPLE_CSV)
    mapping = guess_column_mapping(columns)
    imported, skipped, total = import_rows(db_session, rows, mapping, mode="add")

    assert imported == 2
    assert skipped == 0
    assert total == 2
    symbols = {s.symbol for s in db_session.query(Stock).all()}
    assert symbols == {"RELIANCE", "TCS"}


def test_import_rows_missing_symbol_column_raises(db_session):
    columns, rows = parse_csv(SAMPLE_CSV)
    try:
        import_rows(db_session, rows, {"symbol": ""}, mode="add")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_import_rows_replace_mode_deactivates_previous_universe(db_session):
    columns, rows = parse_csv(SAMPLE_CSV)
    mapping = guess_column_mapping(columns)
    import_rows(db_session, rows, mapping, mode="add")

    new_rows = [{"Symbol": "INFY", "Company Name": "Infosys", "Sector": "IT"}]
    imported, skipped, total = import_rows(db_session, new_rows, mapping, mode="replace")

    assert total == 1
    active_symbols = {s.symbol for s in db_session.query(Stock).filter(Stock.is_active.is_(True))}
    assert active_symbols == {"INFY"}
    # Old stocks are deactivated, not deleted.
    all_symbols = {s.symbol for s in db_session.query(Stock).all()}
    assert "RELIANCE" in all_symbols


def test_import_rows_skips_blank_symbols(db_session):
    rows = [{"Symbol": "", "Company Name": "Nothing"}, {"Symbol": "TCS", "Company Name": "TCS Ltd"}]
    imported, skipped, total = import_rows(db_session, rows, {"symbol": "Symbol", "company_name": "Company Name"})
    assert imported == 1
    assert skipped == 1
