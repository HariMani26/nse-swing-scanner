"""Bounded provider requests and multi-timeframe screening without synthetic data."""
from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone

import httpx
import pandas as pd

from app.services.market_data.base import MarketDataProvider
from app.services.scanner.trading_analysis import (
    IST, SCORE_WEIGHTS, completed_frame, expected_daily_date, four_hour_frame, normalized_frame, number, summarize_timeframe,
)
from app.utils.market_hours import is_market_open

INDEX_SYMBOLS = {"NIFTY": "^NSEI", "BANK NIFTY": "^NSEBANK", "NIFTY 100": "^CNX100",
                 "NIFTY 500": "^CRSLDX", "INDIA VIX": "^INDIAVIX"}
SECTOR_INDICES = {"Technology": "^CNXIT", "Healthcare": "^CNXPHARMA", "Consumer Defensive": "^CNXFMCG",
                  "Energy": "^CNXENERGY", "Basic Materials": "^CNXMETAL", "Real Estate": "^CNXREALTY",
                  "Financial Services": "^CNXFINANCE"}


class TradingService:
    def __init__(self):
        self._cache: dict[tuple, tuple[float, object]] = {}
        self._lock = asyncio.Lock()
        self._metadata: dict[tuple, tuple[float, dict]] = {}
        self._members: dict[str, dict] = {}
        self._members_attempt: dict[str, float] = {}

    async def constituents(self, group: str) -> dict:
        cached = self._members.get(group)
        if cached and time.monotonic() - self._members_attempt.get(group, 0) < (86400 if not cached["error"] else 300):
            return cached
        self._members_attempt[group] = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}) as client:
                response = await client.get("https://www.nseindia.com/api/NextApi/apiClient/marketWatchApi",
                                            params={"functionName": "getIndicesData", "symbol": group})
                response.raise_for_status()
                payload = response.json()
            expected = {"NIFTY 50": 50, "NIFTY 100": 100, "NIFTY 500": 500}[group]
            rows = payload.get("data", {}).get("data", [])
            if not any(isinstance(row, dict) and row.get("symbol") == group and row.get("priority") == 1 for row in rows):
                raise ValueError("Requested index not identified in response")
            members = {row["symbol"] for row in rows if isinstance(row, dict) and isinstance(row.get("symbol"), str) and row["symbol"] != group}
            if len(members) != expected:
                raise ValueError("Incomplete index membership")
            result = {"symbols": sorted(members), "error": None, "source": "NSE JSON", "verified_at": datetime.now(timezone.utc).isoformat()}
        except Exception:
            result = {"symbols": [], "error": "Verified index constituents unavailable from NSE. Select stocks explicitly from Watchlist; no index membership is assumed.", "source": "NSE JSON", "verified_at": None}
        self._members[group] = result
        return result

    async def history(self, provider: MarketDataProvider, symbols: list[str], interval: str) -> dict:
        ttl = 900 if interval == "1d" else 300 if interval == "60m" else max(1, provider.refresh_seconds)
        async with self._lock:
            missing = [symbol for symbol in symbols if (provider.name, interval, symbol) not in self._cache or
                       time.monotonic() - self._cache[(provider.name, interval, symbol)][0] >= ttl]
            if missing:
                fetched = await provider.get_timeframe_history(missing, interval)
                for symbol in missing:
                    self._cache[(provider.name, interval, symbol)] = (time.monotonic(), fetched.get(symbol))
                while len(self._cache) > 1200:
                    self._cache.pop(next(iter(self._cache)))
            return {symbol: self._cache.get((provider.name, interval, symbol), (0, None))[1] for symbol in symbols}

    async def metadata(self, provider: MarketDataProvider, symbol: str) -> dict:
        key = (provider.name, symbol)
        ttl = max(1, min(60, provider.refresh_seconds)) if provider.supports_realtime else 86400
        if key not in self._metadata or time.monotonic() - self._metadata[key][0] > ttl:
            self._metadata[key] = (time.monotonic(), await provider.get_stock_metadata(symbol))
            while len(self._metadata) > 1200:
                self._metadata.pop(next(iter(self._metadata)))
        return self._metadata[key][1]

    async def market(self, provider: MarketDataProvider) -> dict:
        now = datetime.now(timezone.utc)
        daily = await self.history(provider, list(INDEX_SYMBOLS.values()), "1d")
        hourly = await self.history(provider, [symbol for name, symbol in INDEX_SYMBOLS.items() if name != "INDIA VIX"], "60m")
        indices = []
        for label, symbol in INDEX_SYMBOLS.items():
            frame = completed_frame(daily.get(symbol), "1D", now)
            summary = summarize_timeframe(frame, "1D", now)
            intraday = summarize_timeframe(completed_frame(hourly.get(symbol), "1H", now), "1H", now)
            indices.append({"name": label, "symbol": symbol, "daily": summary, "hourly": intraday,
                            "value": number(frame.close.iloc[-1]) if not frame.empty else None,
                            "timestamp": frame.index[-1].isoformat() if not frame.empty else None})
        clear = all(index["daily"].get("trend") == "BULLISH" and not index["daily"]["stale"] for index in indices[:4])
        bearish = all(index["daily"].get("trend") == "BEARISH" and not index["daily"]["stale"] for index in indices[:4])
        available = all(index["daily"]["available"] and not index["daily"]["stale"] for index in indices[:4])
        return {"indices": indices, "status": "BULLISH" if clear else "BEARISH" if bearish else "SIDEWAYS" if available else "UNAVAILABLE", "breadth": None,
                "breadth_status": "Unavailable from connected provider", "source": provider.name,
                "data_label": "LIVE DATA" if provider.supports_realtime and not provider.is_delayed else "DELAYED DATA",
                "realtime_available": provider.supports_realtime and not provider.is_delayed,
                "market_open": is_market_open(now), "refresh_seconds": max(1, provider.refresh_seconds)}

    async def swing_overview(self, provider: MarketDataProvider, stocks: list, publish) -> dict:
        result = {"rows": [], "overview_rows": [], "market": None, "source": provider.name,
                  "realtime_available": False, "refresh_seconds": 900,
                  "scan_timestamp": datetime.now(timezone.utc).isoformat(), "processed": 0,
                  "scan_total": len(stocks), "stage": "SCANNING DAILY / WEEKLY"}
        publish(result)
        for start in range(0, len(stocks), 25):
            batch = stocks[start:start + 25]
            histories = await self.history(provider, [stock.symbol for stock in batch], "1d")
            now = datetime.now(timezone.utc)
            stock_data = [(stock.symbol, stock.company_name, histories.get(stock.symbol)) for stock in batch]
            rows = await asyncio.to_thread(lambda: [swing_overview_row(symbol, company, frame, now)
                                                    for symbol, company, frame in stock_data])
            result = {**result, "overview_rows": result["overview_rows"] + rows,
                      "processed": start + len(batch)}
            publish(result)
        result["stage"] = "COMPLETE"
        return result

    async def scan_universe(self, provider: MarketDataProvider, stocks: list, mode: str, publish) -> dict:
        market = await self.market(provider)
        result = {"rows": [], "market": market, "source": provider.name,
                  "realtime_available": market["realtime_available"], "refresh_seconds": max(60, provider.refresh_seconds),
                  "scan_timestamp": datetime.now(timezone.utc).isoformat(), "processed": 0,
                  "scan_total": len(stocks), "eligible": 0, "excluded": 0, "stage": "LIQUIDITY / HISTORY",
                  "status": "SCANNING", "coverage": "ACTIVE ONLINE NSE CATALOGUE"}
        publish(result)
        eligible = []
        advances = declines = unchanged = 0
        for start in range(0, len(stocks), 25):
            batch = stocks[start:start + 25]
            histories = await self.history(provider, [stock.symbol for stock in batch], "1d")
            now = datetime.now(timezone.utc)
            for stock in batch:
                frame = completed_frame(histories.get(stock.symbol), "1D", now)
                fresh = not frame.empty and frame.index[-1].date() == expected_daily_date(now)
                if fresh and len(frame) >= 2:
                    change = frame.close.iloc[-1] - frame.close.iloc[-2]
                    advances += int(change > 0)
                    declines += int(change < 0)
                    unchanged += int(change == 0)
                if fresh and len(frame) >= 200 and frame.volume.tail(20).mean() >= 100_000 and (frame.close * frame.volume).tail(20).mean() >= 100_000_000:
                    eligible.append(stock)
            result = {**result, "processed": start + len(batch), "eligible": len(eligible),
                      "excluded": start + len(batch) - len(eligible)}
            publish(result)
        breadth_count = advances + declines + unchanged
        market = {**market, "breadth": (advances - declines) / breadth_count * 100 if len(stocks) >= 50 and breadth_count and breadth_count >= len(stocks) * 0.8 else None,
                  "breadth_status": f"Completed daily catalogue breadth: {advances} advances / {declines} declines / {unchanged} unchanged; {breadth_count}/{len(stocks)} covered"}
        result = {**result, "market": market, "stage": "MULTI-TIMEFRAME CONFIRMATION", "processed": len(stocks) - len(eligible)}
        candidates = []
        for start in range(0, len(eligible), 10):
            batch = eligible[start:start + 10]
            analysis = await self.analyze(provider, batch, mode, market)
            candidates.extend(analysis["rows"])
            result = {**result, "rows": top_candidates(candidates), "processed": len(stocks) - len(eligible) + start + len(batch),
                      "alert_rows": analysis["rows"]}
            publish(result)
        return {**result, "rows": top_candidates(candidates), "alert_rows": [], "stage": "COMPLETE",
                "processed": len(stocks), "status": "QUALIFIED SETUPS" if any(row["status"].startswith("CONFIRMED") for row in candidates)
                else "NO VALID TRADE SETUP", "scan_timestamp": datetime.now(timezone.utc).isoformat()}

    async def analyze(self, provider: MarketDataProvider, stocks: list, mode: str, market_context=None) -> dict:
        now = datetime.now(timezone.utc)
        symbols = [stock.symbol for stock in stocks]
        intervals = ("1d", "60m", "15m", "5m", "1m")
        histories = {}
        for interval in intervals:
            histories[interval] = await self.history(provider, symbols, interval)
        market = market_context or await self.market(provider)
        nifty_daily = await self.history(provider, ["^NSEI"], "1d")
        rows = []
        for stock in stocks:
            metadata = await self.metadata(provider, stock.symbol)
            now = datetime.now(timezone.utc)
            sector = metadata.get("sector")
            sector_symbol = "^NSEBANK" if "bank" in (metadata.get("industry") or "").lower() else SECTOR_INDICES.get(sector)
            sector_summary = {"trend": "UNAVAILABLE", "stale": True}
            if sector_symbol:
                sector_frames = await self.history(provider, [sector_symbol], "1d" if mode == "swing" else "60m")
                sector_timeframe = "1D" if mode == "swing" else "1H"
                sector_summary = summarize_timeframe(completed_frame(sector_frames.get(sector_symbol), sector_timeframe, now), sector_timeframe, now)
            frames = {"1D": completed_frame(histories["1d"].get(stock.symbol), "1D", now),
                      "1W": completed_frame(histories["1d"].get(stock.symbol), "1W", now),
                      "4H": four_hour_frame(histories["60m"].get(stock.symbol), now)}
            for timeframe, interval in (("1H", "60m"), ("15M", "15m"), ("5M", "5m"), ("1M", "1m")):
                frames[timeframe] = completed_frame(histories[interval].get(stock.symbol), timeframe, now)
            summaries = {timeframe: summarize_timeframe(frame, timeframe, now) for timeframe, frame in frames.items()}
            row = evaluate_stock(stock.symbol, stock.company_name, sector, sector_summary, summaries,
                                 frames, nifty_daily.get("^NSEI"), metadata, market, provider, mode, now)
            rows.append(row)
        rows.sort(key=lambda row: (row["liquid"], row["score"]), reverse=True)
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank
        return {"rows": rows, "market": market, "source": provider.name,
                "realtime_available": market["realtime_available"], "refresh_seconds": max(1, provider.refresh_seconds),
                "status": "REAL-TIME DATA UNAVAILABLE" if mode == "intraday" and not market["realtime_available"] else "CALCULATED INDICATORS / POTENTIAL SETUPS",
                "scan_timestamp": now.isoformat()}


def top_candidates(rows):
    current = datetime.now(timezone.utc)
    fresh_rows = []
    for row in rows:
        stamp = datetime.fromisoformat(row["timestamp"]) if row.get("timestamp") else None
        if stamp and row["status"].startswith("CONFIRMED") and not 0 <= (current - stamp).total_seconds() <= 120:
            row = {**row, "status": "REAL-TIME DATA UNAVAILABLE", "live": False, "signal_label": "POTENTIAL SETUP",
                   "data_label": "STALE / UNAVAILABLE", "entry_zone": None, "stop_loss": None, "target1": None,
                   "target2": None, "invalidation": None, "invalidation_reason": None, "categories": ["WATCHLIST"],
                   "missing_confirmations": list(dict.fromkeys(row.get("missing_confirmations", []) + ["Fresh price and analysis required before entry"]))}
        fresh_rows.append(row)
    ranked = sorted((row for row in fresh_rows if row["liquid"] and row["score"] >= 65),
                    key=lambda row: (-row["score"], row["symbol"]))
    selected = []
    for bucket in ("BUY", "SELL", "WATCH"):
        members = [row for row in ranked if (row["direction"] if row["status"].startswith("CONFIRMED") else "WATCH") == bucket]
        selected.extend({**row, "rank": rank, "bucket": bucket} for rank, row in enumerate(members[:5], 1))
    return selected


def swing_overview_row(symbol, company, history, now):
    frame = completed_frame(history, "1D", now)
    daily = summarize_timeframe(frame, "1D", now)
    weekly = summarize_timeframe(completed_frame(history, "1W", now), "1W", now)
    average_volume = number(frame.volume.tail(20).mean()) if len(frame) >= 20 else None
    turnover = number((frame.close * frame.volume).tail(20).mean()) if len(frame) >= 20 else None
    liquid = bool(turnover is not None and turnover >= 100_000_000 and average_volume is not None and average_volume >= 100_000)
    valid = daily["available"] and not daily["stale"]
    close = daily.get("close")
    atr = daily.get("atr") or 0
    lows = [point["value"] for point in daily["pivots"] if point["kind"] == "low"]
    highs = [point["value"] for point in daily["pivots"] if point["kind"] == "high"]
    support = max((value for value in lows if close and value <= close), default=None)
    resistance = min((value for value in highs if close and value >= close), default=None)

    def level_evidence(level, points):
        if not level or not close:
            return {"level": None, "touches": 0, "distance_percent": None, "strong": False}
        tolerance = max(atr * 0.5, level * 0.005)
        touches = sum(abs(value - level) <= tolerance for value in points)
        distance = abs(close - level) / close * 100
        return {"level": number(level), "touches": touches, "distance_percent": number(distance),
                "strong": touches >= 2 and distance <= 3}

    support_evidence = level_evidence(support, lows)
    resistance_evidence = level_evidence(resistance, highs)
    direction = daily.get("trend")
    if not valid or not liquid:
        group = "EXCLUDED"
    elif direction == "BULLISH":
        group = "BULLISH"
    elif direction == "BEARISH":
        group = "BEARISH"
    else:
        group = "NEUTRAL"
    setup = "BUY SUPPORT WATCH" if group == "BULLISH" and support_evidence["strong"] else "SELL / EXIT RESISTANCE WATCH" if group == "BEARISH" and resistance_evidence["strong"] else "TREND WATCH" if group in ("BULLISH", "BEARISH") else "NO CLEAR SETUP"
    reason = "Daily history unavailable or stale" if not valid else "Below liquidity thresholds" if not liquid else f"Daily {daily['structure']}; weekly {weekly['trend']}; {daily.get('ema_status', 'UNAVAILABLE')} EMA alignment"
    return {"symbol": symbol, "company_name": company, "group": group, "setup": setup,
            "close": close, "timestamp": daily["timestamp"], "stale": not valid, "liquid": liquid,
            "daily_trend": daily["trend"], "weekly_trend": weekly["trend"], "weekly_stale": weekly["stale"],
            "support": support_evidence, "resistance": resistance_evidence,
            "rsi": daily.get("rsi"), "relative_volume": daily.get("relative_volume"),
            "average_turnover": turnover, "reason": reason,
            "data_label": "COMPLETED DAILY CANDLE", "signal_label": "POTENTIAL SETUP"}


def intraday_setups(summaries, frames, side, now):
    primary, five = summaries["15M"], summaries["5M"]
    buying = side == "BUY"
    close, previous = primary.get("close"), primary.get("previous_close")
    if close is None or previous is None:
        return []
    names = []
    direction = "BREAKOUT" if buying else "BREAKDOWN"

    def crossed(level):
        return level is not None and (previous <= level < close if buying else previous >= level > close)

    session = frames["5M"]
    session = session[session.index.date == now.astimezone(IST).date()] if not session.empty else session
    opening = session.between_time("09:15", "09:29") if not session.empty else session
    expected = pd.date_range(pd.Timestamp(now.astimezone(IST).date(), tz=IST) + pd.Timedelta(hours=9, minutes=15), periods=3, freq="5min")
    if all(stamp in opening.index for stamp in expected) and primary.get("timestamp") and pd.Timestamp(primary["timestamp"]).time() >= datetime.strptime("09:30", "%H:%M").time():
        level = float(opening.high.max() if buying else opening.low.min())
        if crossed(level):
            names.append(f"OPENING RANGE {direction}")
    previous_days = frames["1D"]
    previous_days = previous_days[previous_days.index.date < now.astimezone(IST).date()]
    if not previous_days.empty and crossed(float(previous_days.iloc[-1]["high" if buying else "low"])):
        names.append(f"PREVIOUS DAY {'HIGH' if buying else 'LOW'} {direction}")
    vwap, previous_vwap = primary.get("vwap"), primary.get("previous_vwap")
    if vwap and previous_vwap and (previous <= previous_vwap and close > vwap if buying else previous >= previous_vwap and close < vwap):
        names.append(f"VWAP {direction}")
    if primary.get("breakout_retest" if buying else "breakdown_retest"):
        names.insert(0, f"{direction} + RETEST")
    rejection = "bullish_rejection" if buying else "bearish_rejection"
    if primary.get("pullback" if buying else "bearish_pullback") and primary.get("selling_volume_decreasing") and five.get(rejection):
        names.append("TREND PULLBACK" if buying else "BEARISH TREND PULLBACK")
    if primary.get("momentum_candle") and (primary.get("relative_volume") or 0) >= 2 and (close > primary.get("open", close) if buying else close < primary.get("open", close)):
        names.append("HIGH VOLUME MOMENTUM" if buying else "HIGH VOLUME SELLING")
    if primary.get("breakout" if buying else "breakdown"):
        names.append(direction)
    return names


def evaluate_stock(symbol, company, sector, sector_summary, summaries, frames, nifty_frame,
                   metadata, market, provider, mode, now):
    daily, weekly, hourly, five, fifteen = (summaries[key] for key in ("1D", "1W", "1H", "5M", "15M"))
    primary = daily if mode == "swing" else fifteen
    daily_frame = frames["1D"]
    avg_turnover = float((daily_frame.close * daily_frame.volume).tail(20).mean()) if len(daily_frame) >= 20 else 0
    avg_volume = float(daily_frame.volume.tail(20).mean()) if len(daily_frame) >= 20 else 0
    liquid = avg_turnover >= 100_000_000 and avg_volume >= 100_000 and not daily["stale"]
    minute = normalized_frame(frames["1M"])
    cmp = number(minute.close.iloc[-1]) if not minute.empty else None
    quote_timestamp = minute.index[-1].isoformat() if not minute.empty else None
    quote_fresh = not minute.empty and minute.index[-1].date() == now.astimezone(IST).date() and 0 <= (now - minute.index[-1]).total_seconds() <= 120
    realtime = provider.supports_realtime and not provider.is_delayed and quote_fresh and is_market_open(now)
    missing = []
    if not liquid:
        missing.append("Liquidity requires 20-day average turnover >= INR 10 crore and volume >= 100,000 shares")
    required = ("1W", "1D", "1H", "15M", "5M") if mode == "swing" else ("1D", "1H", "15M", "5M")
    for timeframe in required:
        if not summaries[timeframe]["available"] or summaries[timeframe]["stale"]:
            missing.append(f"{timeframe} current completed candles unavailable")
    for timeframe in (("1W", "1D") if mode == "swing" else ("1D",)):
        if summaries[timeframe].get("ema200") is None:
            missing.append(f"{timeframe} EMA200 history insufficient")
    if not quote_fresh:
        missing.append("Current exchange-timestamped price unavailable")
    if not is_market_open(now):
        missing.append("Outside regular NSE session; no current actionable setup")
    if not realtime:
        missing.append("REAL-TIME DATA UNAVAILABLE")
    if sector_summary.get("stale") or sector_summary.get("trend") not in ("BULLISH", "BEARISH"):
        missing.append("Sector direction unavailable or unclear")
    market_key = "daily" if mode == "swing" else "hourly"
    index_summaries = [item[market_key] for item in market["indices"] if item["name"] != "INDIA VIX"]
    market_available = len(index_summaries) >= 4 and all(item.get("available") and not item["stale"] for item in index_summaries)
    market_up = market_available and all(item.get("trend") == "BULLISH" for item in index_summaries)
    market_down = market_available and all(item.get("trend") == "BEARISH" for item in index_summaries)
    if not market_available:
        missing.append("NIFTY 50/100/500 and BANK NIFTY confirmation unavailable")
    vix = next((item for item in market["indices"] if item["name"] == "INDIA VIX"), None)
    if vix and not vix["daily"]["stale"] and vix.get("value") is not None and vix["value"] >= 25:
        missing.append("Elevated INDIA VIX (>= 25); risk-off filter active")
    if not vix or vix["daily"]["stale"] or vix.get("value") is None:
        missing.append("INDIA VIX unavailable")
    if market.get("breadth") is None:
        missing.append("Market breadth unavailable")
    bid, ask = metadata.get("bid"), metadata.get("ask")
    spread = (ask - bid) / ((ask + bid) / 2) * 100 if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and 0 < bid <= ask else None
    try:
        spread_stamp = datetime.fromisoformat(str(metadata.get("quote_timestamp")).replace("Z", "+00:00"))
        spread_fresh = 0 <= (now - spread_stamp).total_seconds() <= 120
    except (TypeError, ValueError):
        spread_fresh = False
    if not spread_fresh:
        spread = None
    if spread is None or spread > 0.2:
        missing.append("Reliable tight bid/ask spread unconfirmed")
    relative_strength = None
    nifty = completed_frame(nifty_frame, "1D", now)
    if len(nifty) > 20 and len(daily_frame) > 20:
        stock_closes = daily_frame.close.copy()
        index_closes = nifty.close.copy()
        stock_closes.index = stock_closes.index.date
        index_closes.index = index_closes.index.date
        aligned = pd.concat([stock_closes.rename("stock"), index_closes.rename("index")], axis=1).dropna()
        if len(aligned) > 20:
            relative_strength = number(((aligned.stock.iloc[-1] / aligned.stock.iloc[-21] - 1) - (aligned["index"].iloc[-1] / aligned["index"].iloc[-21] - 1)) * 100)
    aligned_buy = all(summaries[key].get("trend") == "BULLISH" for key in required)
    aligned_sell = all(summaries[key].get("trend") == "BEARISH" for key in required)
    volume_ok = (primary.get("relative_volume") or 0) >= 1.2
    entry = cmp
    support, resistance, atr = primary.get("support"), primary.get("resistance"), primary.get("atr")
    side = "SELL" if daily.get("trend") == "BEARISH" else "BUY"
    direction = "BULLISH" if side == "BUY" else "BEARISH"
    structure = "HH/HL" if side == "BUY" else "LH/LL"
    stop = target1 = target2 = risk_reward = None
    zone = None
    if entry and support and resistance and atr and atr > 0:
        zone = [max(0.01, entry - 0.05 * atr), entry + 0.05 * atr]
        entry = zone[1] if side == "BUY" else zone[0]
        if side == "BUY":
            stop = min(support - 0.2 * atr, entry - atr)
            risk = entry - stop
            overhead = [point["value"] for summary in (weekly, daily, primary) for point in summary.get("pivots", []) if point["kind"] == "high" and point["value"] > entry]
            target1 = min(overhead) if overhead else entry + 2 * risk
            target2 = max(entry + 3 * risk, target1 + risk)
        else:
            stop = max(resistance + 0.2 * atr, entry + atr)
            risk = stop - entry
            below = [point["value"] for summary in (weekly, daily, primary) for point in summary.get("pivots", []) if point["kind"] == "low" and point["value"] < entry]
            target1 = max(below) if below else entry - 2 * risk
            target2 = min(entry - 3 * risk, target1 - risk)
        risk_reward = abs(target1 - entry) / risk if risk > 0 else None
        if min(stop, target1, target2) <= 0:
            stop = target1 = target2 = risk_reward = None
    room = risk_reward is not None and risk_reward >= 2
    if not room:
        missing.append("At least 1:2 risk/reward with room to opposing support/resistance is unconfirmed")
    if atr and entry and atr / entry > 0.05 and not (volume_ok and (primary.get("breakout") or primary.get("breakdown"))):
        missing.append("Abnormal volatility without breakout/volume confirmation")
    if not volume_ok:
        missing.append("Volume confirmation missing")
    if not (aligned_buy if side == "BUY" else aligned_sell):
        missing.append("Weekly/daily/setup/entry timeframe alignment incomplete" if mode == "swing" else "Daily/hourly/15-minute/5-minute alignment incomplete")
    direction_ok = (side == "BUY" and market_up and sector_summary.get("trend") == "BULLISH") or (side == "SELL" and market_down and sector_summary.get("trend") == "BEARISH")
    sideways = market_available and not market_up and not market_down
    if not direction_ok and not sideways:
        missing.append("Market and sector do not confirm this direction")
    if market.get("breadth") is not None and ((side == "BUY" and market["breadth"] <= -20) or (side == "SELL" and market["breadth"] >= 20)):
        missing.append("Market breadth strongly opposes this direction")
    breakout = bool(primary.get("breakout" if side == "BUY" else "breakdown") or
                    primary.get("breakout_retest" if side == "BUY" else "breakdown_retest"))
    rejection_key = "bullish_rejection" if side == "BUY" else "bearish_rejection"
    pullback = bool(primary.get("pullback") and primary.get("selling_volume_decreasing") and
                    any(summary.get(rejection_key) for summary in (fifteen, five))) if side == "BUY" else bool(
                        primary.get("bearish_pullback") and primary.get("selling_volume_decreasing") and
                        any(summary.get(rejection_key) for summary in (fifteen, five)))
    rejection_level = support if side == "BUY" else resistance
    reversal = bool(primary.get(rejection_key) and hourly.get("trend") == direction and rejection_level and cmp and abs(cmp - rejection_level) / cmp <= 0.03)
    intraday_names = intraday_setups(summaries, frames, side, now) if mode == "intraday" else []
    setup_ok = (breakout or pullback or reversal) if mode == "swing" else bool(intraday_names)
    entry_ok = all(summary.get("trend") == direction and summary.get("structure") == structure and
                   summary.get("ema_status") == direction and (summary.get("relative_volume") or 0) >= 1 and summary.get("vwap") and cmp and
                   (cmp > summary["vwap"] if side == "BUY" else cmp < summary["vwap"])
                   for summary in (fifteen, five))
    entry_ok = entry_ok and any(five.get(key) for key in ("momentum_candle", rejection_key,
                                                         "breakout" if side == "BUY" else "breakdown",
                                                         "breakout_retest" if side == "BUY" else "breakdown_retest"))
    if (hourly.get("relative_volume") or 0) < 1:
        missing.append("1H volume confirmation missing")
    healthy_daily = daily.get("trend") == direction and daily.get("structure") == structure and daily.get("ema_status") == direction
    if not healthy_daily:
        missing.append("Daily price structure and EMA alignment do not confirm direction")
    if not setup_ok:
        missing.append("No confirmed breakout, pullback or rejection setup")
    if not entry_ok:
        missing.append("15M/5M structure, EMA and VWAP entry confirmation incomplete")
    if side == "SELL" and mode == "swing" and not breakout:
        missing.append("Support breakdown required for SELL")
    if primary.get("false_breakout" if side == "BUY" else "false_breakdown"):
        missing.append("False breakout or breakdown detected")
    if atr and cmp and primary.get("ema20") and abs(cmp - primary["ema20"]) > 3 * atr:
        missing.append("Price extended more than three ATR from EMA20")
    evidence = {
        "Market alignment": market_up if side == "BUY" else market_down,
        "Weekly structure": weekly.get("trend") == direction and weekly.get("structure") == structure and not weekly.get("stale"),
        "Daily structure": healthy_daily and not daily.get("stale"),
        "1H confirmation": hourly.get("trend") == direction and hourly.get("structure") == structure and not hourly.get("stale"),
        "Volume": volume_ok, "Breakout/Pullback": setup_ok,
        "15M/5M entry": bool(entry_ok) and not five.get("stale") and not fifteen.get("stale"),
        "Risk/Reward": room,
        "Market/sector strength": sector_summary.get("trend") == direction and not sector_summary.get("stale") and
                                  relative_strength is not None and (relative_strength >= 0 if side == "BUY" else relative_strength <= 0),
    }
    descriptions = {
        "Market alignment": f"Market confirmation for {direction}",
        "Weekly structure": f"Weekly {weekly.get('structure')}; {weekly.get('trend')}",
        "Daily structure": f"Daily {daily.get('structure')}; EMA {daily.get('ema_status')}",
        "1H confirmation": f"1H {hourly.get('structure')}; {hourly.get('trend')}",
        "Volume": f"Setup relative volume {primary.get('relative_volume')}; minimum 1.2",
        "Breakout/Pullback": f"Breakout/breakdown {breakout}; pullback {pullback}; rejection {reversal}",
        "15M/5M entry": "Both entry timeframes must confirm structure, EMA and VWAP",
        "Risk/Reward": f"Target 1 reward/risk {number(risk_reward)}; minimum 2",
        "Market/sector strength": f"Sector {sector_summary.get('trend')}; relative strength {relative_strength}",
    }
    breakdown = [{"component": key, "points": weight if evidence[key] else 0, "maximum": weight,
                  "reason": descriptions[key]} for key, weight in SCORE_WEIGHTS.items()]
    score = sum(item["points"] for item in breakdown)
    if sideways and not (score >= 85 and (primary.get("relative_volume") or 0) >= 1.5 and evidence["Market/sector strength"]):
        missing.append("Sideways market: exceptional 85-point setup with sector strength and volume required")
    if score < 75:
        missing.append("Score below the 75-point trade threshold")
    grade = "A+ SETUP" if score >= 85 else "A SETUP" if score >= 75 else "WATCHLIST" if score >= 65 else "HIDE"
    status = "NO VALID TRADE SETUP"
    if not realtime:
        status = "REAL-TIME DATA UNAVAILABLE"
    elif not liquid:
        status = "AVOID"
    elif not missing:
        status = "CONFIRMED " + side
    setup = "BREAKOUT" if breakout and side == "BUY" else "BREAKDOWN" if breakout else "PULLBACK" if pullback else "REVERSAL" if reversal else "NONE"
    if status.startswith("CONFIRMED"):
        categories = [f"{setup} {side}"]
        if mode == "intraday" and intraday_names:
            categories.extend(intraday_names)
        if score >= 85:
            categories.append(f"STRONG {side}")
    else:
        categories = ["WATCHLIST"] if liquid and score >= 65 else ["NO TRADE"]
    if not status.startswith("CONFIRMED"):
        entry_zone = None
        stop = target1 = target2 = None
    else:
        entry_zone = [round(price, 2) for price in zone] if zone else None
    session = frames["1M"]
    session = session[session.index.date == now.astimezone(IST).date()] if not session.empty else session
    opening = session.between_time("09:15", "09:29") if not session.empty else session
    previous_sessions = daily_frame[daily_frame.index.date < now.astimezone(IST).date()] if not daily_frame.empty else daily_frame
    reference = previous_sessions.iloc[-1] if not previous_sessions.empty else None
    return {"symbol": symbol, "company_name": company, "sector": sector or "UNAVAILABLE", "cmp": cmp,
            "timestamp": quote_timestamp, "signal_timestamp": primary.get("timestamp"),
            "data_label": "LIVE DATA" if realtime else "DELAYED DATA" if quote_fresh else "STALE / UNAVAILABLE",
            "signal_label": "SIGNAL" if realtime and status.startswith("CONFIRMED") else "POTENTIAL SETUP",
            "live": realtime, "liquid": liquid, "average_turnover": round(avg_turnover, 2),
            "average_volume": round(avg_volume), "spread_percent": number(spread) if spread is not None else None,
            "timeframes": summaries, "sector_trend": sector_summary.get("trend"), "relative_strength_nifty": relative_strength,
            "trend": primary.get("trend"), "trendline": primary.get("trendline"), "support": support,
            "resistance": resistance, "breakout_level": resistance, "entry_zone": entry_zone,
            "stop_loss": number(stop), "target1": number(target1), "target2": number(target2),
            "risk_reward": number(risk_reward), "volume_status": primary.get("volume_status", "UNAVAILABLE"),
            "rsi": primary.get("rsi"), "macd": primary.get("macd"), "ema_status": primary.get("ema_status"),
            "vwap": primary.get("vwap"), "volume": primary.get("volume"), "relative_volume": primary.get("relative_volume"),
            "score": score, "grade": grade, "direction": side, "setup": intraday_names[0] if intraday_names else setup, "market_trend": market.get("status"),
            "qualification_reasons": [item["reason"] for item in breakdown if item["points"]],
            "score_breakdown": breakdown, "missing_confirmations": missing,
            "invalidation": number(support if side == "BUY" else resistance) if entry_zone else None,
            "invalidation_reason": "Stop breached, opposing structure, lost volume/entry confirmation, or stale market data" if entry_zone else None,
            "risk_level": "HIGH" if missing or not liquid else "MODERATE",
            "status": status, "categories": categories or ["SWING WATCHLIST" if mode == "swing" else "WATCH"],
            "reason": "; ".join(missing) if missing else "Aligned timeframes, liquidity, volume, sector, market and reward/risk confirmed",
            "previous_day_high": number(reference.high) if reference is not None else None,
            "previous_day_low": number(reference.low) if reference is not None else None,
            "previous_day_close": number(reference.close) if reference is not None else None,
            "today_open": number(session.open.iloc[0]) if not session.empty else None,
            "today_high": number(session.high.max()) if not session.empty else None,
            "today_low": number(session.low.min()) if not session.empty else None,
            "opening_range_high": number(opening.high.max()) if len(opening) >= 15 else None,
            "opening_range_low": number(opening.low.min()) if len(opening) >= 15 else None,
            "opening_range_status": "CONFIRMED" if len(opening) >= 15 else "UNAVAILABLE / INCOMPLETE"}


trading_service = TradingService()