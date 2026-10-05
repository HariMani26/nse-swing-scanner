from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from app.models import PaperPosition, Stock, TradingAlert
from app.services.scanner.trading_analysis import IST, SCORE_WEIGHTS
from app.services.scanner.trading_analysis import summarize_timeframe
from app.services.scanner.trading_service import evaluate_stock, intraday_setups, top_candidates


def evaluate(side="BUY", change=None, realtime=True):
    now = datetime(2026, 9, 30, 11, 0, tzinfo=IST)
    trend = "BULLISH" if side == "BUY" else "BEARISH"
    summary = dict(available=True, stale=False, trend=trend, structure="HH/HL" if side == "BUY" else "LH/LL",
                   ema_status=trend, ema20=100, ema200=90 if side == "BUY" else 110, support=98, resistance=102, atr=1,
                   relative_volume=1.5, breakout=side == "BUY", breakdown=side == "SELL",
                   vwap=99 if side == "BUY" else 101, pivots=[], timestamp=now.isoformat())
    summaries = {key: deepcopy(summary) for key in ("1W", "1D", "4H", "1H", "15M", "5M", "1M")}
    if change:
        change(summaries)
    daily = pd.DataFrame(dict(open=100., high=102., low=98., close=100., volume=2_000_000.),
                         index=pd.date_range(end="2026-09-29", periods=220, freq="B", tz=IST))
    minute = daily.iloc[-1:].copy()
    minute.index = pd.DatetimeIndex([now - pd.Timedelta(minutes=1)])
    frames = {key: daily for key in summaries}
    frames["1M"] = minute
    market = {"status": trend, "breadth": 50 if side == "BUY" else -50,
              "indices": [{"name": name, "daily": summary, "hourly": summary}
                          for name in ("NIFTY", "BANK NIFTY", "NIFTY 100", "NIFTY 500")] +
                         [{"name": "INDIA VIX", "daily": summary, "value": 15}]}
    return evaluate_stock("TEST", "Test", "Technology", summary, summaries, frames, daily,
                          {"bid": 99.99, "ask": 100.01, "quote_timestamp": now.isoformat()}, market,
                          SimpleNamespace(supports_realtime=realtime, is_delayed=not realtime), "swing", now)


@pytest.mark.asyncio
async def test_complete_universe_is_analyzed_in_bounded_batches(monkeypatch):
    from datetime import timezone
    from app.services.scanner.trading_analysis import expected_daily_date
    from app.services.scanner.trading_service import TradingService

    service = TradingService()
    frame = pd.DataFrame(dict(open=100., high=102., low=98., close=100., volume=2_000_000.),
                         index=pd.date_range(end=expected_daily_date(datetime.now(timezone.utc)), periods=220, freq="B", tz=IST))
    visited = []
    updates = []

    async def market(provider):
        return {"realtime_available": False, "indices": []}

    async def history(provider, symbols, interval):
        assert interval == "1d"
        assert len(symbols) <= 25
        return {symbol: frame for symbol in symbols}

    async def analyze(provider, stocks, mode, context):
        assert len(stocks) <= 10
        visited.extend(stock.symbol for stock in stocks)
        return {"rows": [{"symbol": stock.symbol, "score": 80, "liquid": True,
                          "status": "REAL-TIME DATA UNAVAILABLE", "direction": "BUY"} for stock in stocks]}

    monkeypatch.setattr(service, "market", market)
    monkeypatch.setattr(service, "history", history)
    monkeypatch.setattr(service, "analyze", analyze)
    stocks = [SimpleNamespace(symbol=f"STOCK{index}") for index in range(53)]
    result = await service.scan_universe(SimpleNamespace(name="test", refresh_seconds=60), stocks, "swing", updates.append)
    assert visited == [stock.symbol for stock in stocks]
    assert result["processed"] == result["scan_total"] == 53
    assert result["eligible"] == 53
    assert len(result["rows"]) == 5
    assert result["status"] == "NO VALID TRADE SETUP"
    assert result["market"]["breadth"] == 0
    result = await service.scan_universe(SimpleNamespace(name="test", refresh_seconds=60), stocks[:1], "swing", updates.append)
    assert result["market"]["breadth"] is None


def test_requested_weights_total_100():
    assert list(SCORE_WEIGHTS.values()) == [15, 15, 20, 10, 10, 10, 5, 10, 5]
    assert sum(SCORE_WEIGHTS.values()) == 100


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_directional_score_and_qualified_trade(side):
    row = evaluate(side)
    assert row["score"] == 100
    assert row["status"] == f"CONFIRMED {side}"
    assert row["entry_zone"]


@pytest.mark.parametrize("timeframe", ["1W", "1D", "1H", "15M", "5M"])
def test_sell_cannot_bypass_timeframe_confirmation(timeframe):
    row = evaluate("SELL", lambda summaries: summaries[timeframe].update(trend="BULLISH"))
    assert not row["status"].startswith("CONFIRMED")
    assert row["entry_zone"] is None


def test_high_score_does_not_override_weak_volume():
    row = evaluate(change=lambda summaries: summaries["1D"].update(relative_volume=0.8))
    assert row["score"] >= 85
    assert row["entry_zone"] is None
    assert "Volume confirmation missing" in row["missing_confirmations"]


def test_delayed_data_never_produces_actionable_trade():
    row = evaluate(realtime=False)
    assert row["status"] == "REAL-TIME DATA UNAVAILABLE"
    assert row["entry_zone"] is None


def test_weekly_resistance_blocks_daily_trade():
    row = evaluate(change=lambda summaries: summaries["1W"].update(pivots=[{"kind": "high", "value": 101}]))
    assert row["risk_reward"] < 2
    assert row["entry_zone"] is None


def test_five_minute_vwap_disagreement_blocks_entry():
    row = evaluate(change=lambda summaries: summaries["5M"].update(vwap=101))
    assert row["entry_zone"] is None


def test_false_breakout_blocks_high_score():
    row = evaluate(change=lambda summaries: summaries["1D"].update(false_breakout=True))
    assert row["score"] == 100
    assert row["entry_zone"] is None


def test_extended_price_is_rejected():
    row = evaluate(change=lambda summaries: summaries["1D"].update(ema20=90))
    assert row["entry_zone"] is None


def test_price_action_uses_completed_candle_values():
    now = datetime(2026, 9, 30, 11, 0, tzinfo=IST)
    frame = pd.DataFrame(dict(open=100., high=102., low=98., close=100., volume=2_000_000.),
                         index=pd.date_range(end="2026-09-29", periods=220, freq="B", tz=IST))
    frame.iloc[-1] = [100, 104, 99, 101, 3_000_000]
    summary = summarize_timeframe(frame, "1D", now)
    assert summary["false_breakout"]
    assert not summary["breakout"]
    assert summary["liquidity_sweep"] == "BUY-SIDE"
    assert summary["supply_zone"][0] == 102


def test_top_five_per_direction_and_watch_only():
    rows = [{"symbol": f"{bucket}{index:02}", "direction": "SELL" if bucket == "SELL" else "BUY",
             "status": f"CONFIRMED {bucket}" if bucket != "WATCH" else "NO VALID TRADE SETUP",
             "liquid": True, "score": 100 - index} for bucket in ("BUY", "SELL", "WATCH") for index in range(40)]
    selected = top_candidates(rows)
    assert len(selected) == 15
    for bucket in ("BUY", "SELL", "WATCH"):
        assert [row["score"] for row in selected if row["bucket"] == bucket] == [100, 99, 98, 97, 96]


def test_below_65_and_illiquid_rows_are_hidden():
    assert top_candidates([{"symbol": "LOW", "liquid": True, "score": 64},
                           {"symbol": "ILLIQUID", "liquid": False, "score": 100}]) == []


def test_stale_high_score_cannot_displace_fresh_buy_results():
    from datetime import timezone

    old = [{"symbol": f"OLD{index}", "liquid": True, "score": 100, "status": "CONFIRMED BUY",
            "direction": "BUY", "timestamp": "2020-01-01T10:00:00+00:00"} for index in range(6)]
    current = {"symbol": "CURRENT", "liquid": True, "score": 90, "status": "CONFIRMED BUY",
               "direction": "BUY", "timestamp": datetime.now(timezone.utc).isoformat()}
    rows = top_candidates(old + [current])
    assert [row["symbol"] for row in rows if row["bucket"] == "BUY"] == ["CURRENT"]
    assert all(row.get("entry_zone") is None for row in rows if row["bucket"] == "WATCH")


@pytest.mark.asyncio
async def test_fourth_paper_position_is_rejected(db_session):
    from fastapi import HTTPException
    from app.api.routes_trading import open_position
    from app.schemas import PositionRequest

    db_session.add(Stock(symbol="TEST", sector="Technology"))
    db_session.add_all([PaperPosition(symbol=f"OPEN{index}", side="BUY", style="SWING", quantity=1,
                                     entry=100, stop_loss=99, target1=102) for index in range(3)])
    db_session.commit()
    with pytest.raises(HTTPException, match="three simultaneous"):
        await open_position(PositionRequest(symbol="TEST", entry=100, stop_loss=99, target1=102,
                                            quantity=1, acknowledge_paper=True), db_session)


@pytest.mark.asyncio
async def test_sector_warning_requires_acknowledgement(db_session):
    from fastapi import HTTPException
    from app.api.routes_trading import open_position
    from app.schemas import PositionRequest

    db_session.add_all([Stock(symbol=symbol, sector="Technology") for symbol in ("TEST", "OPEN")])
    db_session.add(PaperPosition(symbol="OPEN", side="BUY", style="SWING", quantity=1,
                                entry=100, stop_loss=99, target1=102))
    db_session.commit()
    payload = PositionRequest(symbol="TEST", entry=100, stop_loss=99, target1=102, quantity=1, acknowledge_paper=True)
    with pytest.raises(HTTPException, match="Sector concentration"):
        await open_position(payload, db_session)
    payload.acknowledge_correlation = True
    assert (await open_position(payload, db_session))["symbol"] == "TEST"


def test_alerts_only_on_state_changes(db_session):
    from app.api.routes_trading import previous_live, record_alerts

    previous_live.clear()
    row = evaluate()
    row.update(status="NO VALID TRADE SETUP", entry_zone=None)
    record_alerts(db_session, {"rows": [row]}, "swing")
    for minute in range(1, 4):
        row = {**row, "timestamp": f"2026-09-30T11:0{minute}:00+05:30"}
        record_alerts(db_session, {"rows": [row]}, "swing")
    assert db_session.query(TradingAlert).count() == 1
    row = {**row, "status": "CONFIRMED BUY", "timestamp": "2026-09-30T11:04:00+05:30"}
    record_alerts(db_session, {"rows": [row]}, "swing")
    row = {**row, "status": "NO VALID TRADE SETUP", "timestamp": "2026-09-30T11:05:00+05:30"}
    record_alerts(db_session, {"rows": [row]}, "swing")
    assert [alert.event_type for alert in db_session.query(TradingAlert).order_by(TradingAlert.id)] == ["EARLY WATCH", "CONFIRMATION", "INVALIDATED"]
    previous_live.clear()


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_intraday_opening_range_and_previous_day_breaks(side):
    now = datetime(2026, 9, 30, 11, 0, tzinfo=IST)
    primary = {"close": 104 if side == "BUY" else 96, "previous_close": 100, "timestamp": now.isoformat()}
    opening = pd.DataFrame(dict(open=100., high=102., low=98., close=100., volume=100_000.),
                           index=pd.date_range("2026-09-30 09:15", periods=3, freq="5min", tz=IST))
    daily = opening.iloc[:1].copy()
    daily.index = daily.index - pd.Timedelta(days=1)
    names = intraday_setups({"15M": primary, "5M": {}}, {"5M": opening, "1D": daily}, side, now)
    assert f"OPENING RANGE {'BREAKOUT' if side == 'BUY' else 'BREAKDOWN'}" in names
    assert any(name.startswith("PREVIOUS DAY") for name in names)
    names = intraday_setups({"15M": primary, "5M": {}}, {"5M": opening.iloc[:2], "1D": daily}, side, now)
    assert not any(name.startswith("OPENING RANGE") for name in names)