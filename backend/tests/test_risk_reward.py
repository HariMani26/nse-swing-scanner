"""Tests for risk/reward and entry/stop/target calculation."""
from __future__ import annotations

from app.services.indicators.calculator import LatestIndicators
from app.services.scanner.risk_reward import (
    MINIMUM_ACCEPTABLE_RR,
    compute_risk_reward,
)


def _ind(**overrides) -> LatestIndicators:
    base = dict(
        price=100.0,
        daily_change_pct=1.0,
        ema20=97.0,
        ema50=93.0,
        rsi14=58.0,
        macd=1.2,
        macd_signal=0.8,
        macd_hist=0.4,
        macd_hist_prev=0.2,
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


def test_no_setup_returns_no_trade_idea():
    rr = compute_risk_reward("none", _ind())
    assert rr.entry is None
    assert rr.stop_loss is None
    assert rr.risk_reward is None
    assert rr.warnings


def test_breakout_entry_is_above_resistance():
    rr = compute_risk_reward("breakout", _ind(price=100, recent_resistance=99))
    assert rr.entry is not None
    assert rr.entry >= 99


def test_breakout_stop_loss_is_below_entry():
    rr = compute_risk_reward("breakout", _ind())
    assert rr.stop_loss < rr.entry


def test_breakout_risk_reward_meets_preferred_ratio_when_possible():
    rr = compute_risk_reward("breakout", _ind(atr14=1.0, recent_support=97))
    assert rr.risk_reward is None or rr.risk_reward >= MINIMUM_ACCEPTABLE_RR


def test_pullback_entry_near_price_and_stop_below_support():
    rr = compute_risk_reward(
        "pullback", _ind(price=95, ema20=95, recent_support=93, recent_resistance=105, atr14=1.5)
    )
    assert rr.entry == 95.0
    assert rr.stop_loss < 93.0
    assert rr.target1 >= rr.entry + (rr.entry - rr.stop_loss) * 2 - 0.01


def test_poor_risk_reward_does_not_force_a_trade():
    # Support extremely close to price -> tiny theoretical risk, but resistance
    # also very close -> poor reward. Force a bad setup via near-zero ATR and
    # resistance right above price.
    ind = _ind(
        price=100,
        recent_support=99.9,
        recent_resistance=100.2,
        atr14=0.01,
        ema20=99,
        ema50=95,
        rsi14=50,
    )
    rr = compute_risk_reward("pullback", ind)
    if rr.risk_reward is not None:
        assert rr.risk_reward >= MINIMUM_ACCEPTABLE_RR
    else:
        assert rr.entry is None
        assert rr.warnings


def test_risk_reward_ratio_calculation_is_consistent():
    rr = compute_risk_reward("breakout", _ind())
    if rr.risk_reward is not None:
        risk = rr.entry - rr.stop_loss
        reward = rr.target1 - rr.entry
        assert abs(rr.risk_reward - reward / risk) < 0.05
