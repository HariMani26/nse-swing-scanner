"""Deterministic multi-timeframe calculations, evidence scores and cash risk limits."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from ta.trend import EMAIndicator

from app.services.indicators.calculator import add_indicators, validate_ohlcv

IST = ZoneInfo("Asia/Kolkata")
TIMEFRAMES = ("1W", "1D", "4H", "1H", "15M", "5M", "1M")
SCORE_WEIGHTS = {"Market alignment": 15, "Weekly structure": 15, "Daily structure": 20,
                 "1H confirmation": 10, "Volume": 10, "Breakout/Pullback": 10,
                 "15M/5M entry": 5, "Risk/Reward": 10, "Market/sector strength": 5}


def position_size(capital: float, risk_percent: float, entry: float, stop: float,
                  allocation: float, target: float | None = None, side: str = "BUY",
                  open_risk: float = 0, reserved_capital: float = 0) -> dict:
    values = (capital, risk_percent, entry, stop, allocation, open_risk, reserved_capital)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Risk inputs must be finite")
    if min(capital, entry, stop, allocation) <= 0 or not 0 < risk_percent <= 1:
        raise ValueError("Capital/prices/allocation must be positive; risk must be greater than 0 and at most 1%")
    if open_risk < 0 or reserved_capital < 0 or side not in ("BUY", "SELL"):
        raise ValueError("Invalid position side or existing exposure")
    if (side == "BUY" and stop >= entry) or (side == "SELL" and stop <= entry):
        raise ValueError("Stop must be below a BUY entry or above a SELL entry")
    if target is not None and (not math.isfinite(target) or target <= 0 or
            (side == "BUY" and target <= entry) or (side == "SELL" and target >= entry)):
        raise ValueError("Target must be on the profit side of the entry")
    per_share = abs(entry - stop)
    risk_budget = min(capital * risk_percent / 100, max(0, capital * 0.02 - open_risk))
    cash_budget = min(allocation, max(0, capital - reserved_capital))
    quantity = max(0, min(math.floor(risk_budget / per_share), math.floor(cash_budget / entry)))
    reward = abs(target - entry) if target is not None else None
    return {"capital": capital, "risk_percent": risk_percent, "risk_amount": round(risk_budget, 2),
            "quantity": quantity, "capital_required": round(quantity * entry, 2),
            "maximum_loss": round(quantity * per_share, 2),
            "potential_profit": round(quantity * reward, 2) if reward is not None else None,
            "risk_reward": round(reward / per_share, 2) if reward is not None else None,
            "available_capital": round(max(0, capital - reserved_capital), 2),
            "remaining_portfolio_risk": round(max(0, capital * 0.02 - open_risk), 2),
            "warning": "Planned loss excludes fees, slippage and gaps; actual loss can exceed the stop. No leverage assumed."}


def normalized_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or not validate_ohlcv(frame):
        return pd.DataFrame()
    result = frame[["open", "high", "low", "close", "volume"]].copy()
    result.index = pd.DatetimeIndex(result.index)
    result.index = result.index.tz_localize(IST) if result.index.tz is None else result.index.tz_convert(IST)
    result = result[~result.index.duplicated(keep="last")].sort_index()
    result = result.replace([np.inf, -np.inf], np.nan).dropna()
    valid = (result[["open", "high", "low", "close"]] > 0).all(axis=1) & (result.volume >= 0)
    valid &= (result.high >= result[["open", "close", "low"]].max(axis=1))
    valid &= (result.low <= result[["open", "close", "high"]].min(axis=1))
    return result.loc[valid]


def expected_daily_date(now: datetime) -> object:
    current = now.astimezone(IST)
    date = current.date() if current.hour >= 16 else current.date() - timedelta(days=1)
    while date.weekday() >= 5:
        date -= timedelta(days=1)
    return date


def completed_frame(frame: pd.DataFrame | None, timeframe: str, now: datetime) -> pd.DataFrame:
    result = normalized_frame(frame)
    if result.empty:
        return result
    current = now.astimezone(IST)
    if timeframe == "1D":
        return result[(result.index.date <= expected_daily_date(now)) & (result.index.dayofweek < 5)]
    if timeframe == "1W":
        daily = completed_frame(result, "1D", now)
        weekly = daily.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        end = weekly.index.normalize() + pd.Timedelta(hours=16)
        return weekly[end <= current]
    minutes = {"4H": 240, "1H": 60, "15M": 15, "5M": 5, "1M": 1}[timeframe]
    result = result[(result.index.dayofweek < 5)]
    result = result.between_time("09:15", "15:29")
    ends = result.index + pd.Timedelta(minutes=minutes)
    closes = result.index.normalize() + pd.Timedelta(hours=15, minutes=30)
    ends = pd.DatetimeIndex([min(end, close) for end, close in zip(ends, closes)])
    return result[ends <= current]


def four_hour_frame(hourly: pd.DataFrame | None, now: datetime) -> pd.DataFrame:
    source = completed_frame(hourly, "1H", now)
    if source.empty:
        return source
    grouped = source.resample("4h", origin="start_day", offset="9h15min")
    bars = grouped.agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    counts = grouped.close.count().reindex(bars.index)
    bars = bars[(counts == 4) | ((bars.index.hour == 13) & (counts == 3))]
    return completed_frame(bars, "4H", now)


def number(value) -> float | None:
    return round(float(value), 4) if pd.notna(value) and math.isfinite(float(value)) else None


def _pattern_quality(components: dict[str, float]) -> tuple[int, str | None]:
    total = max(0, min(100, round(sum(components.values()))))
    label = "STRONG PATTERN" if total >= 80 else "VALID PATTERN" if total >= 70 else "WATCH" if total >= 60 else None
    return total, label


def detect_double_pattern(frame: pd.DataFrame, highs: list[dict], lows: list[dict], last, atr: float | None,
                          volume_ratio: float | None, ema_up: bool, ema_down: bool) -> dict | None:
    """Classical W (double bottom) / M (double top) detection from confirmed fractal swing pivots.

    Requires two swing extremes plus a bounce pivot between them (never just two candles).
    """
    atr_value = atr if atr and math.isfinite(atr) else float(frame.close.iloc[-1]) * 0.01
    close, open_ = float(last.close), float(last.open)

    def neckline_between(start: pd.Timestamp, end: pd.Timestamp, column: str, extreme: str):
        segment = frame.loc[(frame.index > start) & (frame.index < end)]
        if segment.empty:
            return None
        idx = segment[column].idxmax() if extreme == "max" else segment[column].idxmin()
        return float(segment.loc[idx, column])

    def build(kind: str) -> dict | None:
        bullish = kind == "W"
        points = lows if bullish else highs
        if len(points) < 2:
            return None
        first, second = points[-2], points[-1]
        first_ts, second_ts = pd.Timestamp(first["timestamp"]), pd.Timestamp(second["timestamp"])
        tolerance = max(atr_value * 1.5, first["value"] * 0.025)
        if abs(second["value"] - first["value"]) > tolerance:
            return None
        holds = second["value"] >= first["value"] if bullish else second["value"] <= first["value"]
        neckline = neckline_between(first_ts, second_ts, "high" if bullish else "low", "max" if bullish else "min")
        if neckline is None:
            return None  # no bounce candle between the two extremes -> not a recognizable swing
        extremes_peak = max(first["value"], second["value"]) if bullish else min(first["value"], second["value"])
        bounce = (neckline - extremes_peak) if bullish else (extremes_peak - neckline)
        if bounce < atr_value:
            return None
        broken = close > neckline if bullish else close < neckline
        candle_ok = close > open_ if bullish else close < open_
        expansion = volume_ratio is not None and volume_ratio >= 1.2
        failed = close < second["value"] if bullish else close > second["value"]
        retest = False
        if broken:
            after = frame[frame.index > second_ts]
            retest = bool((after.low <= neckline * 1.003).any() and close > neckline) if bullish \
                else bool((after.high >= neckline * 0.997).any() and close < neckline)
        if broken and candle_ok and expansion and retest:
            stage = f"{kind} BREAKOUT"
        elif broken and candle_ok and expansion:
            stage = f"{kind} CONFIRMED"
        elif broken or failed:
            stage = f"{kind} FAILED"
        else:
            stage = f"{kind} FORMING"
        structure_points = 15 + (10 if holds else 0)
        neckline_points = 10 + (10 if bounce >= 2 * atr_value else 5)
        volume_points = 15 if expansion else 8 if volume_ratio is not None and volume_ratio >= 1 else 0
        trend_points = 15 if (bullish and not ema_up) or (not bullish and not ema_down) else 7
        breakout_points = 15 if broken and candle_ok else 7 if broken else 0
        risk = abs(close - second["value"]) or atr_value
        reward = abs(neckline + bounce - close) if broken else bounce
        risk_reward = reward / risk if risk else 0
        risk_reward_points = 10 if risk_reward >= 2 else 7 if risk_reward >= 1.5 else 4 if risk_reward >= 1 else 0
        score, quality = _pattern_quality({"structure": structure_points, "neckline": neckline_points,
                                           "volume": volume_points, "trend": trend_points,
                                           "breakout": breakout_points, "risk_reward": risk_reward_points})
        if quality is None and stage != f"{kind} FAILED":
            return None  # below WATCH threshold -> ignore per pattern quality rules
        return {"pattern": kind, "stage": stage, "score": score, "quality": quality,
                "neckline": number(neckline), "first_point": number(first["value"]), "second_point": number(second["value"]),
                "first_timestamp": first["timestamp"], "second_timestamp": second["timestamp"],
                "volume_confirmed": expansion, "retest_confirmed": retest, "holds": holds}

    # Prefer whichever pattern is more advanced (breakout/confirmed beats forming) when both would qualify.
    stage_rank = {"FORMING": 0, "FAILED": 1, "CONFIRMED": 2, "BREAKOUT": 3}
    candidates = [pattern for pattern in (build("W"), build("M")) if pattern is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda pattern: stage_rank[pattern["stage"].split(" ", 1)[1]])


def summarize_timeframe(frame: pd.DataFrame, timeframe: str, now: datetime) -> dict:
    result = {"timeframe": timeframe, "available": False, "timestamp": None, "stale": True,
              "trend": "UNAVAILABLE", "trendline": "UNAVAILABLE", "structure": "UNCONFIRMED", "pattern": None,
              "pivots": [], "support_line": [], "resistance_line": [], "reason": "Insufficient valid completed candles"}
    if frame.empty or len(frame) < 35:
        return result
    enriched = add_indicators(frame)
    for window in (9, 200):
        enriched[f"ema{window}"] = EMAIndicator(frame.close, window=window).ema_indicator()
    last, previous = enriched.iloc[-1], enriched.iloc[-2]
    stamp = frame.index[-1]
    current = now.astimezone(IST)
    if timeframe == "1D":
        stale = stamp.date() < expected_daily_date(now)
    elif timeframe == "1W":
        last_friday = expected_daily_date(now)
        last_friday -= timedelta(days=(last_friday.weekday() - 4) % 7)
        stale = stamp.date() < last_friday
    else:
        duration = {"4H": 240, "1H": 60, "15M": 15, "5M": 5, "1M": 1}[timeframe]
        maximum_age = 120 if timeframe == "1M" else 2 * duration * 60 + 120
        stale = stamp.date() != current.date() or (current - stamp).total_seconds() > maximum_age
    pivots = []
    highs, lows = [], []
    window = frame.tail(100)
    for index in range(3, len(window) - 3):
        candle = window.iloc[index]
        neighbours = window.iloc[index - 3:index + 4].drop(window.index[index])
        for kind, points in (("high", highs), ("low", lows)):
            value = float(candle[kind])
            extreme = value > neighbours[kind].max() if kind == "high" else value < neighbours[kind].min()
            if not extreme:
                continue
            label = "H" if kind == "high" else "L"
            if points:
                prior = points[-1]["value"]
                label = ("HH" if value > prior else "LH" if value < prior else "EH") if kind == "high" else ("HL" if value > prior else "LL" if value < prior else "EL")
            point = {"timestamp": window.index[index].isoformat(), "value": value, "label": label, "kind": kind}
            points.append(point)
            pivots.append(point)
    structure = f"{highs[-1]['label']}/{lows[-1]['label']}" if len(highs) >= 2 and len(lows) >= 2 else "UNCONFIRMED"
    ema_up = last.close > last.ema20 > last.ema50
    ema_down = last.close < last.ema20 < last.ema50
    trend = "BULLISH" if ema_up and structure == "HH/HL" else "BEARISH" if ema_down and structure == "LH/LL" else "SIDEWAYS"
    support = lows[-1]["value"] if lows else float(frame.low.iloc[-21:-1].min())
    resistance = highs[-1]["value"] if highs else float(frame.high.iloc[-21:-1].max())
    average_volume = float(frame.volume.iloc[-21:-1].mean())
    volume_ratio = float(last.volume) / average_volume if average_volume > 0 else None
    prior_close = float(previous.close)
    candle_range = float(last.high - last.low)
    body = abs(float(last.close - last.open))
    rejection = candle_range > 0 and float(min(last.open, last.close) - last.low) >= 2 * max(body, candle_range * 0.1) and last.close > last.open
    bearish_rejection = candle_range > 0 and float(last.high - max(last.open, last.close)) >= 2 * max(body, candle_range * 0.1) and last.close < last.open
    breakout = prior_close <= resistance < last.close
    breakdown = prior_close >= support > last.close
    false_breakout = bool(last.high > resistance and last.close <= resistance)
    false_breakdown = bool(last.low < support and last.close >= support)
    recent = frame.iloc[-6:-1]
    breakout_retest = bool((recent.close > resistance).any() and last.low <= resistance * 1.003 and
                          last.close > resistance and last.close > last.open)
    breakdown_retest = bool((recent.close < support).any() and last.high >= support * 0.997 and
                           last.close < support and last.close < last.open)
    session = frame[frame.index.date == stamp.date()]
    cumulative_volume = float(session.volume.sum())
    vwap = float((((session.high + session.low + session.close) / 3) * session.volume).sum() / cumulative_volume) if cumulative_volume > 0 and timeframe not in ("1D", "1W") else None
    pullback = bool(last.ema20 > last.ema50 and min(abs(last.close - last.ema20), abs(last.close - last.ema50), abs(last.close - support)) <= last.close * 0.02)
    projected_high = projected_low = prior_projected_high = prior_projected_low = None
    for points, kind in ((highs, "high"), (lows, "low")):
        if len(points) >= 2:
            start, end = points[-2:]
            start_time, end_time = pd.Timestamp(start["timestamp"]), pd.Timestamp(end["timestamp"])
            slope = (end["value"] - start["value"]) / (end_time - start_time).total_seconds()
            projected = end["value"] + slope * (stamp - end_time).total_seconds()
            prior_projected = end["value"] + slope * (frame.index[-2] - end_time).total_seconds()
            if kind == "high":
                projected_high = projected
                prior_projected_high = prior_projected
            else:
                projected_low = projected
                prior_projected_low = prior_projected
    pattern = detect_double_pattern(frame, highs, lows, last, last.atr14, volume_ratio, ema_up, ema_down)
    result.update(
        available=True, timestamp=stamp.isoformat(), stale=stale, trend=trend, structure=structure,
        trendline="RISING" if structure == "HH/HL" else "FALLING" if structure == "LH/LL" else "MIXED",
        pivots=sorted(pivots, key=lambda point: point["timestamp"]), support_line=lows[-2:], resistance_line=highs[-2:],
        close=number(last.close), open=number(last.open), high=number(last.high), low=number(last.low),
        previous_close=number(previous.close),
        previous_vwap=number((((session.high.iloc[:-1] + session.low.iloc[:-1] + session.close.iloc[:-1]) / 3) * session.volume.iloc[:-1]).sum() / session.volume.iloc[:-1].sum()) if len(session) > 1 and session.volume.iloc[:-1].sum() > 0 and timeframe not in ("1D", "1W") else None,
        support=number(support), resistance=number(resistance), breakout_level=number(resistance),
        breakdown_level=number(support), breakout=bool(breakout), breakdown=bool(breakdown), pullback=pullback,
        false_breakout=false_breakout, false_breakdown=false_breakdown,
        breakout_retest=breakout_retest, breakdown_retest=breakdown_retest,
        break_of_structure="BULLISH" if breakout and structure == "HH/HL" else "BEARISH" if breakdown and structure == "LH/LL" else "NONE",
        change_of_character="BULLISH" if breakout and structure == "LH/LL" else "BEARISH" if breakdown and structure == "HH/HL" else "NONE",
        liquidity_sweep="SELL-SIDE" if false_breakdown else "BUY-SIDE" if false_breakout else "NONE",
        demand_zone=[number(support - (last.atr14 or 0) * 0.25), number(support)],
        supply_zone=[number(resistance), number(resistance + (last.atr14 or 0) * 0.25)],
        trend_strength="STRONG " + trend if trend in ("BULLISH", "BEARISH") and pd.notna(last.ema200) and
                   (last.ema50 > last.ema200 if trend == "BULLISH" else last.ema50 < last.ema200) else trend,
        bullish_rejection=bool(rejection), bearish_rejection=bool(bearish_rejection),
        price_action="BULLISH REJECTION" if rejection else "BEARISH REJECTION" if bearish_rejection else "BULLISH CANDLE" if last.close > last.open else "BEARISH CANDLE",
        gap_percent=number((float(last.open) / prior_close - 1) * 100),
        ema9=number(last.ema9), ema20=number(last.ema20), ema50=number(last.ema50), ema200=number(last.ema200),
        ema_status="BULLISH" if ema_up else "BEARISH" if ema_down else "MIXED",
        rsi=number(last.rsi14), macd=number(last.macd), macd_signal=number(last.macd_signal),
        macd_histogram=number(last.macd_hist), atr=number(last.atr14), vwap=number(vwap) if vwap is not None else None,
        volume=number(last.volume), relative_volume=number(volume_ratio) if volume_ratio is not None else None,
        volume_status="HIGH" if volume_ratio is not None and volume_ratio >= 1.5 else "HEALTHY" if volume_ratio is not None and volume_ratio >= 1 else "LOW",
        momentum_candle=bool(candle_range > 0 and body / candle_range >= 0.6 and volume_ratio is not None and volume_ratio >= 1.2),
        bearish_pullback=bool(ema_down and min(abs(last.close - last.ema20), abs(last.close - last.ema50), abs(last.close - resistance)) <= last.close * 0.02),
        selling_volume_decreasing=bool(frame.volume.iloc[-4:-1].mean() < frame.volume.iloc[-21:-4].mean()),
        ema_crossover=bool(previous.ema20 <= previous.ema50 and last.ema20 > last.ema50),
        ema_crossunder=bool(previous.ema20 >= previous.ema50 and last.ema20 < last.ema50),
        rsi_confirmation=bool(previous.rsi14 < 50 <= last.rsi14 or previous.rsi14 > 50 >= last.rsi14),
        trendline_breakout=bool(projected_high is not None and prior_close <= prior_projected_high and last.close > projected_high),
        trendline_breakdown=bool(projected_low is not None and prior_close >= prior_projected_low and last.close < projected_low),
        pattern=pattern,
        reason="Calculated from completed provider candles; pivots require three bars on each side.",
        candles=[{"timestamp": index.isoformat(), "open": number(candle.open), "high": number(candle.high),
                  "low": number(candle.low), "close": number(candle.close), "volume": number(candle.volume),
                  "ema20": number(candle.ema20), "ema50": number(candle.ema50), "ema200": number(candle.ema200)}
                 for index, candle in enriched.tail(160).iterrows()],
    )
    return result