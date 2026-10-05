"""Risk/reward and trade-level (entry / stop / targets) calculation.

The scanner never forces a trade idea: if the computed risk/reward ratio
falls below the minimum acceptable threshold, entry/stop/targets are left
empty and a warning is attached instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.services.indicators.calculator import LatestIndicators

PREFERRED_MIN_RR = 2.0
MINIMUM_ACCEPTABLE_RR = 1.5
ATR_STOP_MULTIPLIER = 1.5


@dataclass
class RiskReward:
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    target1: Optional[float] = None
    target2: Optional[float] = None
    risk_reward: Optional[float] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def _round2(v: float) -> float:
    return round(float(v), 2)


def compute_risk_reward(setup_type: str, ind: LatestIndicators) -> RiskReward:
    if setup_type == "breakout":
        return _breakout_risk_reward(ind)
    if setup_type == "pullback":
        return _pullback_risk_reward(ind)
    return RiskReward(warnings=["No qualifying breakout or pullback setup identified today."])


def _breakout_risk_reward(ind: LatestIndicators) -> RiskReward:
    entry = max(ind.price, ind.recent_resistance * 1.002 if ind.recent_resistance > 0 else ind.price)

    atr_stop = entry - ind.atr14 * ATR_STOP_MULTIPLIER
    support_stop = ind.recent_support if 0 < ind.recent_support < entry else atr_stop
    # Use the tighter (higher) of the two technically-justified stops.
    stop_loss = max(atr_stop, support_stop) if atr_stop > 0 or support_stop > 0 else entry * 0.95
    stop_loss = min(stop_loss, entry * 0.995)  # ensure stop is meaningfully below entry

    risk = entry - stop_loss
    if risk <= 0:
        return RiskReward(warnings=["Could not derive a valid stop loss below entry."])

    target1 = entry + risk * PREFERRED_MIN_RR
    target2 = entry + risk * 3

    rr = (target1 - entry) / risk
    warnings: List[str] = []
    if rr < MINIMUM_ACCEPTABLE_RR:
        return RiskReward(
            warnings=[
                f"Risk/reward ({round(rr, 2)}:1) is below the minimum acceptable "
                f"{MINIMUM_ACCEPTABLE_RR}:1 - no trade idea generated."
            ]
        )
    if rr < PREFERRED_MIN_RR:
        warnings.append(f"Risk/reward ({round(rr, 2)}:1) is below the preferred 1:{PREFERRED_MIN_RR}.")

    return RiskReward(
        entry=_round2(entry),
        stop_loss=_round2(stop_loss),
        target1=_round2(target1),
        target2=_round2(target2),
        risk_reward=round(rr, 2),
        warnings=warnings,
    )


def _pullback_risk_reward(ind: LatestIndicators) -> RiskReward:
    entry = ind.price
    atr_buffer = ind.atr14 * 0.75
    support_floor = ind.recent_support if ind.recent_support > 0 else entry * 0.97
    stop_loss = min(support_floor, entry) - atr_buffer

    risk = entry - stop_loss
    if risk <= 0:
        return RiskReward(warnings=["Could not derive a valid stop loss below entry."])

    resistance_target = ind.recent_resistance if ind.recent_resistance > entry else 0
    target1 = max(resistance_target, entry + risk * PREFERRED_MIN_RR)
    target2 = max(target1, entry + risk * 3)

    rr = (target1 - entry) / risk
    warnings: List[str] = []
    if rr < MINIMUM_ACCEPTABLE_RR:
        return RiskReward(
            warnings=[
                f"Risk/reward ({round(rr, 2)}:1) is below the minimum acceptable "
                f"{MINIMUM_ACCEPTABLE_RR}:1 - no trade idea generated."
            ]
        )
    if rr < PREFERRED_MIN_RR:
        warnings.append(f"Risk/reward ({round(rr, 2)}:1) is below the preferred 1:{PREFERRED_MIN_RR}.")

    return RiskReward(
        entry=_round2(entry),
        stop_loss=_round2(stop_loss),
        target1=_round2(target1),
        target2=_round2(target2),
        risk_reward=round(rr, 2),
        warnings=warnings,
    )
