"""Tests for breakout/pullback setup detection (daily-close based only)."""
from __future__ import annotations

from app.services.indicators.calculator import LatestIndicators
from app.services.scanner.breakout import detect_setup


def _ind(**overrides) -> LatestIndicators:
    base = dict(
        price=100.0,
        daily_change_pct=1.0,
        ema20=97.0,
        ema50=93.0,
        rsi14=55.0,
        macd=1.0,
        macd_signal=0.5,
        macd_hist=0.3,
        macd_hist_prev=0.1,
        volume=200_000.0,
        avg_volume20=100_000.0,
        atr14=2.0,
        high_52w=110.0,
        distance_from_high_pct=-9.0,
        recent_support=94.0,
        recent_resistance=99.0,
        closes_above_resistance_today=True,
        warnings=[],
    )
    base.update(overrides)
    return LatestIndicators(**base)


def test_confirmed_breakout_needs_close_above_resistance_and_volume():
    setup = detect_setup(_ind(price=101, recent_resistance=99, volume=200_000, avg_volume20=100_000))
    assert setup.setup_type == "breakout"


def test_breakout_rejected_on_low_volume():
    setup = detect_setup(_ind(price=101, recent_resistance=99, volume=100_000, avg_volume20=100_000))
    assert setup.setup_type != "breakout"


def test_price_above_resistance_intraday_only_not_confirmed():
    # Daily close is at/below resistance -> not a confirmed breakout even if
    # an intraday high pierced it (intraday highs are never used for this check).
    setup = detect_setup(_ind(price=98, recent_resistance=99))
    assert setup.setup_type != "breakout"


def test_pullback_detected_near_ema20_in_uptrend():
    setup = detect_setup(
        _ind(price=97.5, ema20=97.0, ema50=93.0, recent_support=94, recent_resistance=105, rsi14=50)
    )
    assert setup.setup_type == "pullback"


def test_no_setup_when_downtrend():
    setup = detect_setup(
        _ind(price=90, ema20=93, ema50=97, recent_support=80, recent_resistance=95, rsi14=40)
    )
    assert setup.setup_type == "none"
