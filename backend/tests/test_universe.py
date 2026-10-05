import gzip
import json

import httpx
import pytest

from app.models import Stock
from app.seed import OnlineUniverse, parse_equity_catalogue, sync_equity_catalogue


def instrument(symbol="RELIANCE", **changes):
    row = {"segment": "NSE_EQ", "instrument_type": "EQ", "trading_symbol": symbol, "name": "Live company"}
    row.update(changes)
    return row


def test_parse_only_valid_nse_equity_json():
    rows = [instrument(), instrument("M&M"), instrument("FUTURE", segment="NSE_FO"),
            instrument("ETF", instrument_type="ETF"), instrument("bad / symbol"), None]
    assert parse_equity_catalogue(rows) == {"RELIANCE": "Live company", "M&M": "Live company"}
    with pytest.raises(ValueError):
        parse_equity_catalogue([])
    with pytest.raises(ValueError):
        parse_equity_catalogue({"error": "unavailable"})


def test_sync_replaces_csv_metadata_and_preserves_user_choices(db_session):
    db_session.add_all([
        Stock(symbol="RELIANCE", company_name="CSV name", sector="CSV sector", source="csv_import", is_active=True),
        Stock(symbol="OLDCSV", source="csv_import", is_active=True),
        Stock(symbol="REMOVED", source="upstox_nse", is_active=False),
        Stock(symbol="CUSTOM", company_name="My stock", source="manual", is_active=True),
    ])
    db_session.commit()
    equities = {"RELIANCE": "Current company", "REMOVED": "Removed company", "NEW": "New company"}
    sync_equity_catalogue(db_session, equities)
    sync_equity_catalogue(db_session, equities)
    rows = {stock.symbol: stock for stock in db_session.query(Stock).all()}
    assert rows["RELIANCE"].source == "upstox_nse"
    assert rows["RELIANCE"].company_name == "Current company"
    assert rows["RELIANCE"].sector == ""
    assert not rows["OLDCSV"].is_active
    assert not rows["REMOVED"].is_active
    assert rows["CUSTOM"].is_active
    assert rows["NEW"].is_active
    assert len(rows) == 5


@pytest.mark.asyncio
async def test_json_download_cached_and_failed_refresh_preserves_universe(db_session, monkeypatch):
    service = OnlineUniverse()
    requests = []
    payload = [instrument(f"STOCK{number}") for number in range(501)]

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=gzip.compress(json.dumps(payload).encode()))

    original_client = httpx.AsyncClient
    monkeypatch.setattr("app.seed.httpx.AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler)))
    status = await service.refresh(db_session)
    assert status["instrument_count"] == 501
    assert status["last_synced_at"]
    await service.refresh(db_session)
    assert len(requests) == 1
    service._last_attempt -= 301
    payload.clear()
    failed = await service.refresh(db_session, force=True)
    assert failed["error"]
    assert db_session.query(Stock).filter(Stock.is_active.is_(True)).count() == 501
    assert failed["last_synced_at"] == status["last_synced_at"]