"""Technical indicator calculations built on pandas + the `ta` library.

All functions are pure (DataFrame in, DataFrame/values out) so they can be
unit tested without any network or database dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
from ta.volatility import AverageTrueRange

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def validate_ohlcv(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False
    return all(c in df.columns for c in REQUIRED_COLUMNS)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with EMA20/EMA50/RSI14/MACD/ATR14 columns added."""
    if not validate_ohlcv(df):
        raise ValueError("DataFrame missing required OHLCV columns")

    out = df.copy()
    out["ema20"] = EMAIndicator(close=out["close"], window=20).ema_indicator()
    out["ema50"] = EMAIndicator(close=out["close"], window=50).ema_indicator()
    out["rsi14"] = RSIIndicator(close=out["close"], window=14).rsi()

    macd_calc = MACD(close=out["close"], window_slow=26, window_fast=12, window_sign=9)
    out["macd"] = macd_calc.macd()
    out["macd_signal"] = macd_calc.macd_signal()
    out["macd_hist"] = macd_calc.macd_diff()

    if len(out) >= 15:
        atr_calc = AverageTrueRange(high=out["high"], low=out["low"], close=out["close"], window=14)
        out["atr14"] = atr_calc.average_true_range()
    else:
        out["atr14"] = float("nan")

    out["avg_volume20"] = out["volume"].rolling(window=20, min_periods=1).mean()
    out["pct_change"] = out["close"].pct_change() * 100
    out["rolling_52w_high"] = out["high"].rolling(window=252, min_periods=1).max()

    return out


def get_52_week_high(df: pd.DataFrame) -> float:
    window = df.tail(252)
    return float(window["high"].max())


def distance_from_high_pct(price: float, high_52w: float) -> float:
    if high_52w <= 0:
        return 0.0
    return round((price - high_52w) / high_52w * 100, 2)


def find_swing_points(df: pd.DataFrame, order: int = 3, lookback: int = 90) -> Tuple[List[float], List[float]]:
    """Return (swing_low_prices, swing_high_prices) found in the trailing `lookback` bars.

    A swing high/low is a local extreme compared to `order` bars on each side -
    a simple, explainable pivot-point method (no black-box pattern detection).
    """
    window = df.tail(lookback).reset_index(drop=True)
    highs = window["high"].to_numpy()
    lows = window["low"].to_numpy()
    n = len(window)

    swing_highs: List[float] = []
    swing_lows: List[float] = []

    for i in range(order, n - order):
        h_slice = highs[i - order : i + order + 1]
        l_slice = lows[i - order : i + order + 1]
        if highs[i] == h_slice.max() and highs[i] > 0:
            swing_highs.append(float(highs[i]))
        if lows[i] == l_slice.min() and lows[i] > 0:
            swing_lows.append(float(lows[i]))

    return swing_lows, swing_highs


def recent_support_resistance(df: pd.DataFrame, order: int = 3, lookback: int = 90) -> Tuple[float, float]:
    """Approximate the nearest recent support (below price) and resistance (above price).

    Falls back to the trailing lookback window's low/high when no clean pivot
    is found on the correct side of the current price.
    """
    if df.empty:
        return 0.0, 0.0

    current_price = float(df["close"].iloc[-1])
    swing_lows, swing_highs = find_swing_points(df, order=order, lookback=lookback)
    window = df.tail(lookback)

    supports_below = [s for s in swing_lows if s < current_price]
    resistances_above = [r for r in swing_highs if r > current_price]

    support = max(supports_below) if supports_below else float(window["low"].min())
    resistance = min(resistances_above) if resistances_above else float(window["high"].max())

    return round(support, 2), round(resistance, 2)


@dataclass
class LatestIndicators:
    price: float
    daily_change_pct: float
    ema20: float
    ema50: float
    rsi14: float
    macd: float
    macd_signal: float
    macd_hist: float
    macd_hist_prev: float
    volume: float
    avg_volume20: float
    atr14: float
    high_52w: float
    distance_from_high_pct: float
    recent_support: float
    recent_resistance: float
    closes_above_resistance_today: bool
    warnings: List[str] = field(default_factory=list)


def summarize_latest(df: pd.DataFrame) -> LatestIndicators:
    """Compute indicators and return the latest snapshot used by the scorer."""
    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    prev_hist = enriched["macd_hist"].iloc[-2] if len(enriched) > 1 else last["macd_hist"]

    high_52w = get_52_week_high(enriched)
    support, resistance = recent_support_resistance(enriched)
    price = float(last["close"])

    warnings: List[str] = []
    for col in ("ema20", "ema50", "rsi14", "macd", "macd_signal", "atr14"):
        if pd.isna(last[col]):
            warnings.append(f"Insufficient history to compute {col}")

    def safe(v: float) -> float:
        return 0.0 if pd.isna(v) else round(float(v), 2)

    return LatestIndicators(
        price=round(price, 2),
        daily_change_pct=safe(last["pct_change"]),
        ema20=safe(last["ema20"]),
        ema50=safe(last["ema50"]),
        rsi14=safe(last["rsi14"]),
        macd=safe(last["macd"]),
        macd_signal=safe(last["macd_signal"]),
        macd_hist=safe(last["macd_hist"]),
        macd_hist_prev=safe(prev_hist),
        volume=safe(last["volume"]),
        avg_volume20=safe(last["avg_volume20"]),
        atr14=safe(last["atr14"]),
        high_52w=round(high_52w, 2),
        distance_from_high_pct=distance_from_high_pct(price, high_52w),
        recent_support=support,
        recent_resistance=resistance,
        closes_above_resistance_today=price > resistance,
        warnings=warnings,
    )
