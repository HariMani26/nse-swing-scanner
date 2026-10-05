"""Tests for EMA / RSI / MACD / ATR indicator calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.indicators.calculator import (
    add_indicators,
    distance_from_high_pct,
    get_52_week_high,
    recent_support_resistance,
    summarize_latest,
    validate_ohlcv,
)
from tests.conftest import make_ohlcv


def test_validate_ohlcv_requires_all_columns():
    df = pd.DataFrame({"open": [1], "high": [1], "low": [1], "close": [1]})
    assert validate_ohlcv(df) is False
    assert validate_ohlcv(None) is False
    assert validate_ohlcv(make_ohlcv(10)) is True


def test_ema_matches_pandas_ewm():
    df = make_ohlcv(120, trend="up")
    enriched = add_indicators(df)
    expected_ema20 = df["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    pd.testing.assert_series_equal(
        enriched["ema20"].reset_index(drop=True),
        expected_ema20.reset_index(drop=True),
        check_names=False,
        atol=1e-6,
    )


def test_rsi_is_bounded_between_0_and_100():
    df = make_ohlcv(150, trend="up")
    enriched = add_indicators(df)
    rsi = enriched["rsi14"].dropna()
    assert (rsi >= 0).all()
    assert (rsi <= 100).all()


def test_rsi_higher_in_uptrend_than_downtrend():
    up = add_indicators(make_ohlcv(150, trend="up", seed=1))
    down = add_indicators(make_ohlcv(150, trend="down", seed=1))
    assert up["rsi14"].iloc[-1] > down["rsi14"].iloc[-1]


def test_macd_components_present_and_histogram_is_difference():
    df = make_ohlcv(150, trend="up")
    enriched = add_indicators(df)
    last = enriched.iloc[-1]
    assert abs(last["macd_hist"] - (last["macd"] - last["macd_signal"])) < 1e-6


def test_atr_is_non_negative():
    df = make_ohlcv(150, trend="up")
    enriched = add_indicators(df)
    atr = enriched["atr14"].dropna()
    assert (atr >= 0).all()


def test_52_week_high_and_distance():
    df = make_ohlcv(300, trend="up")
    high = get_52_week_high(df)
    assert high == df.tail(252)["high"].max()

    dist = distance_from_high_pct(price=high, high_52w=high)
    assert dist == 0.0

    dist_below = distance_from_high_pct(price=high * 0.9, high_52w=high)
    assert dist_below < 0


def test_recent_support_resistance_bounds_price():
    df = make_ohlcv(200, trend="flat")
    support, resistance = recent_support_resistance(df)
    price = df["close"].iloc[-1]
    assert support <= price or support > 0
    assert resistance >= price or resistance > 0
    assert support < resistance


def test_summarize_latest_returns_all_fields():
    df = make_ohlcv(300, trend="up")
    latest = summarize_latest(df)
    assert latest.price > 0
    assert latest.ema20 > 0
    assert latest.ema50 > 0
    assert 0 <= latest.rsi14 <= 100
    assert latest.high_52w >= latest.price * 0
    assert isinstance(latest.warnings, list)


def test_summarize_latest_flags_insufficient_history():
    df = make_ohlcv(5, trend="up")
    latest = summarize_latest(df)
    assert any("Insufficient history" in w for w in latest.warnings)
