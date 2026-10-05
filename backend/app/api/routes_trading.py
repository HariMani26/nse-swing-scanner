"""Trading analysis jobs, evidence alerts and explicitly paper-only portfolio records."""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import hashlib
import json
import logging
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_market_provider_dep
from app.database import get_db, session_scope
from app.models import PaperPosition, Stock, TradingAlert
from app.schemas import ClosePositionRequest, PositionRequest, RiskRequest
from app.services.market_data.base import MarketDataProvider
from app.services.scanner.trading_analysis import IST, expected_daily_date, position_size
from app.services.scanner.trading_service import top_candidates, trading_service

router = APIRouter(prefix="/api/trading", tags=["trading"])
jobs: dict[tuple, asyncio.Task] = {}
reports: dict[tuple, dict] = {}
attempts: dict[tuple, float] = {}
job_errors: dict[tuple, str] = {}
queue = asyncio.Semaphore(1)
overview_queue = asyncio.Semaphore(1)
paper_lock = asyncio.Lock()
previous_live: dict[tuple, dict] = {}
logger = logging.getLogger(__name__)


def record_alerts(db: Session, report: dict, mode: str):
    for row in report["rows"]:
        if not row["live"] or row.get("cmp") is None:
            continue
        key = (mode, row["symbol"])
        previous = previous_live.get(key)
        previous_live[key] = row
        if previous is not None and previous["timestamp"] == row["timestamp"]:
            continue
        events = []
        confirmed = row["status"].startswith("CONFIRMED")
        old_confirmed = previous is not None and previous["status"].startswith("CONFIRMED")
        if confirmed and (not old_confirmed or previous.get("direction") != row.get("direction")):
            events.append("CONFIRMATION")
        elif old_confirmed and not confirmed:
            events.append("INVALIDATED")
        elif not confirmed and row["liquid"] and row["score"] >= 65 and (previous is None or previous["score"] < 65):
            events.append("EARLY WATCH")
        if previous and old_confirmed and confirmed and previous.get("entry_zone"):
            lower, upper = previous["entry_zone"]
            if not lower <= previous["cmp"] <= upper and lower <= row["cmp"] <= upper:
                events.append("ENTRY")
        positions = db.query(PaperPosition).filter(PaperPosition.symbol == row["symbol"], PaperPosition.closed_at.is_(None)).all()
        for position in positions:
            buy = position.side == "BUY"
            stopped = row["cmp"] <= position.stop_loss if buy else row["cmp"] >= position.stop_loss
            if stopped:
                events.append(f"STOP LOSS #{position.id}")
            else:
                for label, target in (("TARGET 1", position.target1), ("TARGET 2", position.target2)):
                    if target is not None and (row["cmp"] >= target if buy else row["cmp"] <= target):
                        events.append(f"{label} #{position.id}")
        for event in events:
            identity = f"position:{event}" if "#" in event else f"{mode}:{row['symbol']}:{event}:{row['timestamp']}"
            event_key = hashlib.sha256(identity.encode()).hexdigest()
            if not db.query(TradingAlert).filter(TradingAlert.event_key == event_key).first():
                details = {field: row.get(field) for field in ("status", "reason", "entry_zone", "stop_loss", "target1", "target2", "risk_reward", "vwap", "relative_volume")}
                db.add(TradingAlert(event_key=event_key, symbol=row["symbol"], event_type=event,
                                    provider_timestamp=row["timestamp"], price=row["cmp"], details_json=json.dumps(details)))
    db.commit()


async def calculate_report(key, provider, symbols, mode, full_universe=False, qualified=False):
    try:
        async with (overview_queue if full_universe else queue):
            with session_scope() as db:
                stocks = db.query(Stock).filter(Stock.symbol.in_(symbols), Stock.is_active.is_(True), Stock.source != "csv_import").all()
                stocks.sort(key=lambda stock: stock.symbol)
                if qualified:
                    def publish(update):
                        record_alerts(db, {"rows": update.get("alert_rows", [])}, mode)
                        reports[key] = {name: value for name, value in update.items() if name != "alert_rows"}
                    result = await trading_service.scan_universe(provider, stocks, mode, publish)
                    result.pop("alert_rows", None)
                elif full_universe:
                    result = await trading_service.swing_overview(provider, stocks, lambda update: reports.__setitem__(key, update))
                else:
                    result = await trading_service.analyze(provider, stocks, mode)
                    record_alerts(db, result, mode)
            reports[key] = result
            job_errors.pop(key, None)
    except Exception:
        logger.exception("Trading analysis failed for %s", symbols)
        job_errors[key] = "Analysis unavailable from the connected provider. No current signal is available."
    finally:
        attempts[key] = time.monotonic()


@router.get("/screen")
async def screen(
    mode: Literal["swing", "intraday"] = "swing",
    group: Literal["ALL NSE", "NIFTY 50", "NIFTY 100", "NIFTY 500", "SELECTED"] = "NIFTY 50",
    symbols: str = Query("", max_length=350), offset: int = Query(0, ge=0),
    limit: int = Query(5, ge=1, le=10), db: Session = Depends(get_db),
    full_universe: bool = False,
    qualified: bool = False,
    provider: MarketDataProvider = Depends(get_market_provider_dep),
):
    membership_error = None
    verified_at = None
    if group == "ALL NSE":
        universe = [stock.symbol for stock in db.query(Stock).filter(Stock.is_active.is_(True), Stock.source == "upstox_nse").order_by(Stock.symbol)]
        if not universe:
            membership_error = "Online NSE catalogue unavailable. No universe was assumed."
    elif group == "SELECTED":
        universe = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()))[:10]
        if not universe:
            membership_error = "Select up to 10 online watchlist stocks for analysis."
    else:
        membership = await trading_service.constituents(group)
        universe, membership_error = membership["symbols"], membership["error"]
        verified_at = membership["verified_at"]
    full_universe = qualified or (full_universe and mode == "swing")
    selection = universe if full_universe else universe[offset:offset + limit]
    active = {stock.symbol for stock in db.query(Stock).filter(Stock.symbol.in_(selection), Stock.is_active.is_(True), Stock.source != "csv_import")}
    unavailable = [symbol for symbol in selection if symbol not in active]
    selection = [symbol for symbol in selection if symbol in active]
    if unavailable:
        membership_error = "Not in active online NSE catalogue: " + ", ".join(unavailable)
    key = (provider.name, mode, tuple(selection), full_universe, qualified)
    refresh_seconds = max(60, provider.refresh_seconds) if qualified else 900 if full_universe else max(1, provider.refresh_seconds)
    if selection and (key not in jobs or jobs[key].done()) and time.monotonic() - attempts.get(key, float("-inf")) >= refresh_seconds:
        active_jobs = sum(not task.done() for task in jobs.values())
        if active_jobs < 4:
            if len(jobs) >= 100:
                expired = next((old for old, task in jobs.items() if task.done()), None)
                if expired is not None:
                    jobs.pop(expired, None)
                    reports.pop(expired, None)
                    attempts.pop(expired, None)
            jobs[key] = asyncio.create_task(calculate_report(key, provider, selection, mode, full_universe, qualified))
    result = copy.deepcopy(reports.get(key, {"rows": [], "market": None, "source": provider.name,
                           "realtime_available": provider.supports_realtime and not provider.is_delayed,
                           "refresh_seconds": refresh_seconds, "scan_timestamp": None,
                           "overview_rows": [], "processed": 0, "scan_total": len(selection), "stage": "QUEUED"}))
    now = dt.datetime.now(dt.timezone.utc)
    for row in result.get("overview_rows", []):
        stamp = dt.datetime.fromisoformat(row["timestamp"]) if row.get("timestamp") else None
        if not stamp or stamp.astimezone(IST).date() < expected_daily_date(now):
            row.update(group="EXCLUDED", stale=True, setup="NO CLEAR SETUP", reason="Daily history unavailable or stale")
    for row in result["rows"]:
        stamp = dt.datetime.fromisoformat(row["timestamp"]) if row.get("timestamp") else None
        if not stamp or not 0 <= (now - stamp).total_seconds() <= 120 or job_errors.get(key):
            row.update(status="REAL-TIME DATA UNAVAILABLE", signal_label="POTENTIAL SETUP",
                       live=False, data_label="STALE / UNAVAILABLE", entry_zone=None, stop_loss=None,
                       target1=None, target2=None, invalidation=None, invalidation_reason=None, categories=["WATCHLIST"], bucket="WATCH")
            row["missing_confirmations"] = list(dict.fromkeys(row["missing_confirmations"] + ["Fresh price and analysis required before entry"]))
    if qualified:
        result["rows"] = top_candidates(result["rows"])
    result.update(group=group, total=len(universe), offset=0 if full_universe else offset, analyzed=len(selection),
                  index_verified_at=verified_at, error=membership_error or job_errors.get(key),
                  refreshing=key in jobs and not jobs[key].done(),
                  status=("QUALIFIED SETUPS" if any(row["status"].startswith("CONFIRMED") for row in result["rows"]) else "NO VALID TRADE SETUP") if qualified else "SWING WATCHLIST" if full_universe and result.get("overview_rows") else "REAL-TIME DATA UNAVAILABLE" if mode == "intraday" and not result["realtime_available"] else "NO CLEAR SETUP" if not result["rows"] else "POTENTIAL SETUPS",
                  alert_status="ACTIVE WHILE THIS VIEW IS MONITORED" if result["realtime_available"] else "LIVE ALERTS DISABLED: REAL-TIME DATA UNAVAILABLE")
    return result


@router.get("/market")
async def market(provider: MarketDataProvider = Depends(get_market_provider_dep)):
    return await trading_service.market(provider)


@router.get("/alerts")
def alerts(db: Session = Depends(get_db)):
    rows = db.query(TradingAlert).order_by(TradingAlert.id.desc()).limit(100).all()
    return [{"id": row.id, "symbol": row.symbol, "event": row.event_type, "timestamp": row.provider_timestamp,
             "price": row.price, "details": json.loads(row.details_json)} for row in rows]


def portfolio_exposure(db):
    positions = db.query(PaperPosition).filter(PaperPosition.closed_at.is_(None)).all()
    return (sum(abs(position.entry - position.stop_loss) * position.quantity for position in positions),
            sum(position.entry * position.quantity for position in positions))


def calculate_risk(payload: RiskRequest, db):
    open_risk, reserved = portfolio_exposure(db)
    try:
        return position_size(payload.capital, payload.risk_percent, payload.entry, payload.stop_loss,
                             payload.allocation, payload.target1, payload.side, open_risk, reserved)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/risk/size")
def risk_size(payload: RiskRequest, db: Session = Depends(get_db)):
    return calculate_risk(payload, db)


def position_out(position):
    return {field: getattr(position, field) for field in ("id", "symbol", "side", "style", "quantity", "entry", "stop_loss", "target1", "target2", "opened_at", "closed_at", "exit_price", "realized_pnl", "exit_reason")}


@router.get("/positions")
def positions(closed: bool = False, db: Session = Depends(get_db)):
    query = db.query(PaperPosition)
    query = query.filter(PaperPosition.closed_at.is_not(None)) if closed else query.filter(PaperPosition.closed_at.is_(None))
    return [position_out(position) for position in query.order_by(PaperPosition.id.desc()).all()]


@router.post("/positions")
async def open_position(payload: PositionRequest, db: Session = Depends(get_db)):
    if not payload.acknowledge_paper:
        raise HTTPException(422, "Paper-trading acknowledgement is required. No broker order will be placed.")
    if payload.style == "SWING" and payload.side == "SELL":
        raise HTTPException(422, "Overnight short selling of cash equities is not supported")
    symbol = payload.symbol.strip().upper()
    if not db.query(Stock).filter(Stock.symbol == symbol, Stock.is_active.is_(True), Stock.source != "csv_import").first():
        raise HTTPException(404, "Stock must exist in the active online watchlist")
    async with paper_lock:
        opened = db.query(PaperPosition).filter(PaperPosition.closed_at.is_(None)).all()
        if len(opened) >= 3:
            raise HTTPException(409, "Maximum three simultaneous positions")
        stock = db.query(Stock).filter(Stock.symbol == symbol).one()
        sectors = {item.sector for item in db.query(Stock).filter(Stock.symbol.in_([position.symbol for position in opened]))}
        if opened and (not stock.sector or "" in sectors or stock.sector in sectors) and not payload.acknowledge_correlation:
            raise HTTPException(409, "Sector concentration risk: same-sector or unknown exposure. Explicit acknowledgement required.")
        sizing = calculate_risk(payload, db)
        if payload.quantity > sizing["quantity"]:
            raise HTTPException(422, "Quantity exceeds cash, per-trade risk or the 2% portfolio-risk cap")
        if abs(payload.target1 - payload.entry) / abs(payload.entry - payload.stop_loss) < 2:
            raise HTTPException(422, "Paper position requires at least 1:2 planned reward/risk")
        if payload.target2 is not None and ((payload.side == "BUY" and payload.target2 < payload.target1) or (payload.side == "SELL" and payload.target2 > payload.target1)):
            raise HTTPException(422, "Target 2 must be beyond Target 1")
        position = PaperPosition(symbol=symbol, side=payload.side, style=payload.style,
                                 quantity=payload.quantity, entry=payload.entry, stop_loss=payload.stop_loss,
                                 target1=payload.target1, target2=payload.target2)
        db.add(position)
        db.commit()
        db.refresh(position)
        return position_out(position)


@router.post("/positions/{position_id}/close")
async def close_position(position_id: int, payload: ClosePositionRequest, db: Session = Depends(get_db)):
    async with paper_lock:
        position = db.get(PaperPosition, position_id)
        if position is None:
            raise HTTPException(404, "Paper position not found")
        if position.closed_at is not None:
            raise HTTPException(409, "Paper position already closed")
        position.exit_price = payload.exit_price
        position.closed_at = dt.datetime.utcnow()
        position.exit_reason = payload.reason
        position.realized_pnl = round((payload.exit_price - position.entry) * position.quantity * (1 if position.side == "BUY" else -1), 2)
        db.commit()
        return position_out(position)