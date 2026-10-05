"""Confirmed daily swing structure and volume-backed breakout signals."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.services.indicators.calculator import add_indicators, validate_ohlcv


def completed_daily_candles(df: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    current = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Kolkata"))
    dates = pd.DatetimeIndex(df.index)
    if dates.tz is not None:
        dates = dates.tz_convert("Asia/Kolkata")
    complete = (dates.date < current.date()) | (
        (dates.date == current.date()) & (current.hour >= 16)
    )
    return df.loc[complete & (dates.dayofweek < 5)].sort_index()


def analyze_daily_trend(df: pd.DataFrame, now: datetime | None = None) -> dict:
    result = {
        "trend": "unavailable", "signal": "WAIT", "as_of": None,
        "reason": "At least 25 completed daily candles are required.",
        "pivots": [], "support_line": [], "resistance_line": [],
        "support": None, "resistance": None, "volume_ratio": None,
        "entry": None, "stop_loss": None, "target": None, "risk_reward": None,
    }
    if not validate_ohlcv(df):
        return result
    completed = completed_daily_candles(df, now)
    if completed.empty:
        return result
    result["as_of"] = completed.index[-1].strftime("%Y-%m-%d")
    if len(completed) < 25:
        return result
    values = completed[["open", "high", "low", "close", "volume"]]
    if not np.isfinite(values.to_numpy(dtype=float)).all() or (values["close"] <= 0).any():
        result["reason"] = "Invalid candle data; no actionable signal."
        return result

    window = completed.tail(90)
    highs, lows = [], []
    for position in range(3, len(window) - 3):
        row = window.iloc[position]
        neighbours = window.iloc[position - 3:position + 4].drop(window.index[position])
        date = window.index[position].strftime("%Y-%m-%d")
        for kind, column, points in (("high", "high", highs), ("low", "low", lows)):
            value = float(row[column])
            extreme = value > neighbours[column].max() if kind == "high" else value < neighbours[column].min()
            if extreme:
                label = "H" if kind == "high" else "L"
                if points:
                    if value == points[-1]["value"]:
                        label = "EH" if kind == "high" else "EL"
                    elif kind == "high":
                        label = "HH" if value > points[-1]["value"] else "LH"
                    else:
                        label = "HL" if value > points[-1]["value"] else "LL"
                points.append({"date": date, "value": value, "kind": kind, "label": label})

    result["pivots"] = sorted(highs + lows, key=lambda point: (point["date"], point["kind"]))
    result["support_line"] = [{"date": point["date"], "value": point["value"]} for point in lows[-2:]]
    result["resistance_line"] = [{"date": point["date"], "value": point["value"]} for point in highs[-2:]]
    if len(highs) < 2 or len(lows) < 2:
        result["reason"] = "Waiting for two confirmed swing highs and lows."
        return result

    bullish = highs[-1]["label"] == "HH" and lows[-1]["label"] == "HL"
    bearish = highs[-1]["label"] == "LH" and lows[-1]["label"] == "LL"
    result["trend"] = "bullish" if bullish else "bearish" if bearish else "sideways"
    support, resistance = lows[-1]["value"], highs[-1]["value"]
    result.update(support=support, resistance=resistance)
    average = float(completed["volume"].iloc[-21:-1].mean())
    ratio = float(completed["volume"].iloc[-1]) / average if average > 0 else 0
    result["volume_ratio"] = round(ratio, 2)
    result["reason"] = "No new volume-confirmed daily breakout or breakdown."
    current = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Asia/Kolkata"))
    if (current.date() - completed.index[-1].date()).days > 7:
        result["reason"] = "Daily history is stale; no actionable signal."
        return result

    close, previous = float(completed["close"].iloc[-1]), float(completed["close"].iloc[-2])
    buy = bullish and previous <= resistance < close
    sell = bearish and previous >= support > close
    if ratio < 1.2 or not (buy or sell):
        return result
    atr = float(add_indicators(completed)["atr14"].iloc[-1])
    stop = min(support, close - atr) if buy else max(resistance, close + atr)
    risk = abs(close - stop)
    if not np.isfinite(risk) or risk <= 0:
        return result
    result.update(
        signal="BUY" if buy else "SELL",
        reason=("Higher highs and higher lows; close broke resistance" if buy else
                "Lower highs and lower lows; close broke support") + f" with {ratio:.2f}x volume.",
        entry=round(close, 2), stop_loss=round(stop, 2),
        target=round(close + 2 * risk if buy else close - 2 * risk, 2), risk_reward=2.0,
    )
    if result["target"] <= 0:
        result.update(signal="WAIT", reason="No valid positive-price target.", entry=None,
                      stop_loss=None, target=None, risk_reward=None)
    return result