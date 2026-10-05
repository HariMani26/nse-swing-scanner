"""Tests for the transparent scoring engine."""
from __future__ import annotations

from app.services.indicators.calculator import LatestIndicators
from app.services.scanner.scoring import (
    compute_score,
    score_breakout,
    score_ema_trend,
    score_macd,
    score_market,
    score_news,
    score_rsi,
    score_volume,
    status_label_for,
)


def _ind(**overrides) -> LatestIndicators:
    base = dict(
        price=100.0,
        daily_change_pct=1.0,
        ema20=95.0,
        ema50=90.0,
        rsi14=62.0,
        macd=1.5,
        macd_signal=1.0,
        macd_hist=0.5,
        macd_hist_prev=0.3,
        volume=200_000.0,
        avg_volume20=100_000.0,
        atr14=2.0,
        high_52w=105.0,
        distance_from_high_pct=-4.76,
        recent_support=90.0,
        recent_resistance=98.0,
        closes_above_resistance_today=True,
        warnings=[],
    )
    base.update(overrides)
    return LatestIndicators(**base)


def test_ema_trend_full_points_when_stacked_bullish():
    score, reasons = score_ema_trend(_ind(price=100, ema20=95, ema50=90))
    assert score == 15.0
    assert reasons


def test_ema_trend_partial_points_when_ema20_below_ema50():
    score, _ = score_ema_trend(_ind(price=100, ema20=95, ema50=98))
    assert score == 7.0


def test_ema_trend_zero_when_price_below_both_emas():
    score, _ = score_ema_trend(_ind(price=80, ema20=95, ema50=90))
    assert score == 0.0


def test_rsi_scoring_bands():
    assert score_rsi(_ind(rsi14=65))[0] == 10.0
    assert score_rsi(_ind(rsi14=75))[0] == 6.0
    assert score_rsi(_ind(rsi14=55))[0] == 8.0
    assert score_rsi(_ind(rsi14=45))[0] == 4.0
    assert score_rsi(_ind(rsi14=35))[0] == 2.0
    assert score_rsi(_ind(rsi14=20))[0] == 3.0


def test_rsi_overbought_and_oversold_produce_warnings_not_rejection():
    _, _, warnings_overbought = score_rsi(_ind(rsi14=78))
    assert any("overbought" in w or "extended" in w for w in warnings_overbought)
    _, _, warnings_oversold = score_rsi(_ind(rsi14=25))
    assert any("oversold" in w for w in warnings_oversold)


def test_macd_bullish_with_all_confirmations():
    score, reasons = score_macd(_ind(macd=2.0, macd_signal=1.0, macd_hist=0.6, macd_hist_prev=0.3))
    assert score == 15.0
    assert len(reasons) == 3


def test_macd_bearish_scores_zero():
    score, reasons = score_macd(_ind(macd=0.5, macd_signal=1.0))
    assert score == 0.0
    assert "bearish" in reasons[0]


def test_volume_scoring_thresholds():
    assert score_volume(_ind(volume=250_000, avg_volume20=100_000))[0] == 15.0
    assert score_volume(_ind(volume=160_000, avg_volume20=100_000))[0] == 12.0
    assert score_volume(_ind(volume=125_000, avg_volume20=100_000))[0] == 8.0
    assert score_volume(_ind(volume=105_000, avg_volume20=100_000))[0] == 5.0
    assert score_volume(_ind(volume=50_000, avg_volume20=100_000))[0] == 2.0


def test_breakout_score_requires_confirmed_daily_close():
    score, reasons = score_breakout(_ind(closes_above_resistance_today=True, recent_resistance=98))
    assert score == 10.0
    assert "resistance" in reasons[0]


def test_breakout_score_near_52_week_high_without_breakout():
    score, _ = score_breakout(
        _ind(closes_above_resistance_today=False, distance_from_high_pct=-2.0, high_52w=105)
    )
    assert score == 7.0


def test_news_score_mapping_and_unavailable():
    assert score_news("strongly_positive")[0] == 20.0
    assert score_news("positive")[0] == 10.0
    assert score_news("neutral")[0] == 0.0
    assert score_news("negative")[0] == -10.0
    assert score_news("strongly_negative")[0] == -20.0
    score, reasons = score_news(None)
    assert score == 0.0
    assert reasons == ["News data unavailable"]
    score, reasons = score_news("unavailable")
    assert score == 0.0
    assert reasons == ["News data unavailable"]


def test_market_score_mapping():
    assert score_market("bullish")[0] == 10.0
    assert score_market("neutral")[0] == 5.0
    assert score_market("bearish")[0] == 0.0


def test_status_label_boundaries():
    assert status_label_for(80) == "STRONG SWING CANDIDATE"
    assert status_label_for(65) == "WATCH"
    assert status_label_for(50) == "NEUTRAL"
    assert status_label_for(49.9) == "AVOID / WEAK SETUP"


def test_compute_score_end_to_end_strong_candidate():
    ind = _ind()
    result = compute_score(ind, news_sentiment="positive", market_trend="bullish")
    assert result.total_score > 0
    assert result.technical_score <= 70
    assert result.news_score <= 20
    assert result.market_score <= 10
    assert result.status_label in (
        "STRONG SWING CANDIDATE",
        "WATCH",
        "NEUTRAL",
        "AVOID / WEAK SETUP",
    )


def test_compute_score_reduced_when_market_strongly_bearish():
    ind = _ind()
    bullish = compute_score(ind, news_sentiment="neutral", market_trend="bullish", market_change_pct=1.0)
    bearish = compute_score(ind, news_sentiment="neutral", market_trend="bearish", market_change_pct=-2.0)
    assert bearish.total_score < bullish.total_score
