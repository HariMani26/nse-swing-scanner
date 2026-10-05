"""Transparent 0-100 scoring engine.

Technical = 70 pts, News = 20 pts, Market/sector = 10 pts.
Every point awarded is accompanied by a human-readable reason so the UI can
show exactly why a stock was (or wasn't) shortlisted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.services.indicators.calculator import LatestIndicators

TECHNICAL_MAX = 70
NEWS_MAX = 20
MARKET_MAX = 10

STRONG_CANDIDATE_MIN = 80
WATCH_MIN = 65
NEUTRAL_MIN = 50


@dataclass
class ScoreBreakdown:
    ema_score: float
    rsi_score: float
    macd_score: float
    volume_score: float
    breakout_score: float
    support_resistance_score: float
    technical_score: float
    news_score: float
    market_score: float
    total_score: float
    status_label: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def score_ema_trend(ind: LatestIndicators) -> Tuple[float, List[str]]:
    if ind.price > ind.ema20 > ind.ema50:
        return 15.0, ["Price above EMA20 and EMA20 above EMA50 (strong uptrend)"]
    if ind.price > ind.ema20 and ind.ema20 <= ind.ema50:
        return 7.0, ["Price above EMA20 but EMA20 below EMA50 (early-stage trend)"]
    if ind.ema20 > ind.ema50 and ind.price <= ind.ema20 and ind.price >= ind.ema50:
        return 5.0, ["Price pulled back below EMA20 within a broader EMA20>EMA50 uptrend"]
    return 0.0, ["Price below both EMA20 and EMA50 (no uptrend confirmation)"]


def score_rsi(ind: LatestIndicators) -> Tuple[float, List[str], List[str]]:
    reasons, warnings = [], []
    rsi = ind.rsi14
    if 60 <= rsi <= 70:
        reasons.append(f"RSI {rsi} shows strong momentum (60-70)")
        return 10.0, reasons, warnings
    if rsi > 70:
        warnings.append(f"RSI {rsi} is extended/overbought - momentum may cool off")
        return 6.0, reasons, warnings
    if 50 <= rsi < 60:
        reasons.append(f"RSI {rsi} is in a healthy bullish range (50-60)")
        return 8.0, reasons, warnings
    if 40 <= rsi < 50:
        reasons.append(f"RSI {rsi} is neutral")
        return 4.0, reasons, warnings
    if 30 <= rsi < 40:
        warnings.append(f"RSI {rsi} is weak")
        return 2.0, reasons, warnings
    warnings.append(f"RSI {rsi} is oversold - possible reversal candidate, not an automatic buy")
    return 3.0, reasons, warnings


def score_macd(ind: LatestIndicators) -> Tuple[float, List[str]]:
    reasons = []
    score = 0.0
    if ind.macd > ind.macd_signal:
        score += 8.0
        reasons.append("MACD above signal line (bullish)")
        if ind.macd > 0:
            score += 4.0
            reasons.append("MACD above zero (additional bullish confirmation)")
        if ind.macd_hist > ind.macd_hist_prev:
            score += 3.0
            reasons.append("MACD histogram increasing (momentum building)")
    else:
        reasons.append("MACD below signal line (bearish)")
    return round(min(score, 15.0), 2), reasons


def score_volume(ind: LatestIndicators) -> Tuple[float, List[str]]:
    if ind.avg_volume20 <= 0:
        return 0.0, ["Volume history unavailable"]
    ratio = ind.volume / ind.avg_volume20
    if ratio >= 2.0:
        return 15.0, [f"Volume {round(ratio, 2)}x average (strong participation)"]
    if ratio >= 1.5:
        return 12.0, [f"Volume {round(ratio, 2)}x average (above-average participation)"]
    if ratio >= 1.2:
        return 8.0, [f"Volume {round(ratio, 2)}x average"]
    if ratio >= 1.0:
        return 5.0, [f"Volume {round(ratio, 2)}x average (in line with normal activity)"]
    return 2.0, [f"Volume {round(ratio, 2)}x average (below average - low-volume move)"]


def score_breakout(ind: LatestIndicators) -> Tuple[float, List[str]]:
    if ind.closes_above_resistance_today and ind.recent_resistance > 0:
        return 10.0, [
            f"Daily close {ind.price} confirmed above recent resistance {ind.recent_resistance}"
        ]
    if ind.high_52w > 0:
        distance = abs(ind.distance_from_high_pct)
        if distance <= 3:
            return 7.0, [f"Within {distance}% of 52-week high ({ind.high_52w})"]
        if distance <= 7:
            return 4.0, [f"Approaching 52-week high, {distance}% away ({ind.high_52w})"]
    return 0.0, []


def score_support_resistance(ind: LatestIndicators) -> Tuple[float, List[str]]:
    if ind.recent_support <= 0 or ind.recent_resistance <= 0:
        return 0.0, ["Not enough history to identify support/resistance zones"]

    near_support = ind.price <= ind.recent_support * 1.03
    near_resistance_breakout = ind.closes_above_resistance_today
    if near_support or near_resistance_breakout:
        return 5.0, [
            f"Price is positioned near a well-defined support ({ind.recent_support}) "
            f"or resistance ({ind.recent_resistance}) zone"
        ]
    return 2.0, ["Price is between identified support/resistance zones"]


def score_news(sentiment: Optional[str]) -> Tuple[float, List[str]]:
    mapping = {
        "strongly_positive": 20.0,
        "positive": 10.0,
        "neutral": 0.0,
        "negative": -10.0,
        "strongly_negative": -20.0,
    }
    if sentiment is None or sentiment == "unavailable":
        return 0.0, ["News data unavailable"]
    score = mapping.get(sentiment, 0.0)
    return score, [f"News sentiment: {sentiment.replace('_', ' ')}"]


def score_market(trend: str) -> Tuple[float, List[str]]:
    mapping = {"bullish": 10.0, "neutral": 5.0, "bearish": 0.0}
    score = mapping.get(trend, 5.0)
    return score, [f"Overall market trend is {trend}"]


def status_label_for(score: float) -> str:
    if score >= STRONG_CANDIDATE_MIN:
        return "STRONG SWING CANDIDATE"
    if score >= WATCH_MIN:
        return "WATCH"
    if score >= NEUTRAL_MIN:
        return "NEUTRAL"
    return "AVOID / WEAK SETUP"


def compute_score(
    ind: LatestIndicators,
    news_sentiment: Optional[str],
    market_trend: str,
    market_change_pct: float = 0.0,
) -> ScoreBreakdown:
    reasons: List[str] = []
    warnings: List[str] = list(ind.warnings)

    ema_score, ema_reasons = score_ema_trend(ind)
    rsi_score, rsi_reasons, rsi_warnings = score_rsi(ind)
    macd_score, macd_reasons = score_macd(ind)
    volume_score, volume_reasons = score_volume(ind)
    breakout_score, breakout_reasons = score_breakout(ind)
    sr_score, sr_reasons = score_support_resistance(ind)

    reasons += ema_reasons + rsi_reasons + macd_reasons + volume_reasons + breakout_reasons + sr_reasons
    warnings += rsi_warnings

    technical_score = round(
        ema_score + rsi_score + macd_score + volume_score + breakout_score + sr_score, 2
    )

    news_score, news_reasons = score_news(news_sentiment)
    market_score, market_reasons = score_market(market_trend)
    reasons += news_reasons + market_reasons

    total_score = technical_score + news_score + market_score

    # Dampen the score further when the broad market is strongly bearish.
    if market_trend == "bearish" and market_change_pct <= -1.0:
        warnings.append("Market trend is strongly bearish - score reduced accordingly")
        total_score *= 0.85

    total_score = round(max(0.0, min(100.0, total_score)), 2)

    if ind.recent_resistance > 0 and ind.price < ind.recent_resistance and (
        ind.recent_resistance - ind.price
    ) / ind.price <= 0.02:
        warnings.append(f"Resistance nearby at {ind.recent_resistance}")

    return ScoreBreakdown(
        ema_score=ema_score,
        rsi_score=rsi_score,
        macd_score=macd_score,
        volume_score=volume_score,
        breakout_score=breakout_score,
        support_resistance_score=sr_score,
        technical_score=technical_score,
        news_score=news_score,
        market_score=market_score,
        total_score=total_score,
        status_label=status_label_for(total_score),
        reasons=reasons,
        warnings=warnings,
    )
