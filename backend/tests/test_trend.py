from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from app.services.scanner.trend import analyze_daily_trend, completed_daily_candles


def trend_history(bearish=False):
    positions = np.arange(62)
    closes = 100 + positions * 0.3 + 5 * np.sin(positions * 2 * np.pi / 12)
    if bearish:
        closes = 200 - closes
    frame = pd.DataFrame({"open": closes, "high": closes + 1, "low": closes - 1,
                          "close": closes, "volume": 1000.0},
                         index=pd.bdate_range("2026-06-01", periods=62))
    frame.iloc[-1, frame.columns.get_loc("close")] = 65 if bearish else 130
    frame.iloc[-1, frame.columns.get_loc("high")] = 66 if bearish else 131
    frame.iloc[-1, frame.columns.get_loc("low")] = 64 if bearish else 129
    frame.iloc[-1, frame.columns.get_loc("volume")] = 1500
    return frame


@pytest.mark.parametrize("bearish,signal,trend", [(False, "BUY", "bullish"), (True, "SELL", "bearish")])
def test_confirmed_structure_and_volume_signal(bearish, signal, trend):
    frame = trend_history(bearish)
    now = frame.index[-1].to_pydatetime().replace(hour=12, tzinfo=timezone.utc)
    result = analyze_daily_trend(frame, now)
    assert result["signal"] == signal
    assert result["trend"] == trend
    assert result["risk_reward"] == 2
    assert len(result["support_line"]) == len(result["resistance_line"]) == 2
    assert all(point["date"] <= frame.index[-4].strftime("%Y-%m-%d") for point in result["pivots"])


def test_low_volume_and_stale_history_wait():
    frame = trend_history()
    now = frame.index[-1].to_pydatetime().replace(hour=12, tzinfo=timezone.utc)
    frame.iloc[-1, frame.columns.get_loc("volume")] = 1000
    assert analyze_daily_trend(frame, now)["signal"] == "WAIT"
    frame.iloc[-1, frame.columns.get_loc("volume")] = 1500
    assert analyze_daily_trend(frame, datetime(2026, 10, 1, tzinfo=timezone.utc))["signal"] == "WAIT"


def test_intraday_candle_does_not_change_daily_signal():
    frame = trend_history()
    now = frame.index[-1].to_pydatetime().replace(hour=8, tzinfo=timezone.utc)
    result = analyze_daily_trend(frame, now)
    assert result == analyze_daily_trend(frame.iloc[:-1], now)
    assert result["signal"] == "WAIT"
    assert len(completed_daily_candles(frame, now)) == len(frame) - 1


def test_missing_and_flat_history_wait():
    assert analyze_daily_trend(pd.DataFrame())["signal"] == "WAIT"
    frame = trend_history()
    frame.loc[:, ["open", "high", "low", "close"]] = 100.0
    assert analyze_daily_trend(frame)["pivots"] == []