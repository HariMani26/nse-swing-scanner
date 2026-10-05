"""Breakout / pullback setup detection.

All detection is based on daily closing prices only, never on intraday
highs/lows, so a brief intraday spike above resistance is never mistaken for
a confirmed breakout.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.indicators.calculator import LatestIndicators


@dataclass
class SetupDetection:
    setup_type: str  # "breakout" | "pullback" | "none"
    reasons: list[str]


def detect_setup(ind: LatestIndicators) -> SetupDetection:
    reasons: list[str] = []

    volume_ratio = ind.volume / ind.avg_volume20 if ind.avg_volume20 > 0 else 0.0
    uptrend = ind.ema20 > ind.ema50
    breakout_confirmed = ind.price > ind.recent_resistance and ind.recent_resistance > 0

    if breakout_confirmed and volume_ratio >= 1.2:
        reasons.append(
            f"Daily close ({ind.price}) confirmed above resistance ({ind.recent_resistance}) "
            f"with volume {round(volume_ratio, 2)}x average"
        )
        return SetupDetection(setup_type="breakout", reasons=reasons)

    near_support = ind.recent_support > 0 and ind.price <= ind.recent_support * 1.03
    near_ema20 = ind.ema20 > 0 and abs(ind.price - ind.ema20) / ind.ema20 <= 0.02
    healthy_rsi = 35 <= ind.rsi14 <= 62

    if uptrend and (near_support or near_ema20) and healthy_rsi:
        reasons.append(
            "Price pulled back near support/EMA20 within an established uptrend (EMA20 > EMA50)"
        )
        return SetupDetection(setup_type="pullback", reasons=reasons)

    return SetupDetection(setup_type="none", reasons=reasons)
