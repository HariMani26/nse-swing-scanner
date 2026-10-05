"""Helpers to convert ORM rows into API response schemas."""
from __future__ import annotations

import json

from app.models import ScanResult
from app.schemas import ScanResultOut


def scan_result_to_out(row: ScanResult) -> ScanResultOut:
    return ScanResultOut(
        symbol=row.symbol,
        company_name=row.company_name,
        sector=row.sector,
        data_available=row.data_available,
        error_message=row.error_message,
        price=row.price,
        daily_change_pct=row.daily_change_pct,
        ema20=row.ema20,
        ema50=row.ema50,
        rsi14=row.rsi14,
        macd=row.macd,
        macd_signal=row.macd_signal,
        macd_hist=row.macd_hist,
        volume=row.volume,
        avg_volume20=row.avg_volume20,
        atr14=row.atr14,
        high_52w=row.high_52w,
        distance_from_high_pct=row.distance_from_high_pct,
        recent_support=row.recent_support,
        recent_resistance=row.recent_resistance,
        technical_score=row.technical_score,
        news_score=row.news_score,
        market_score=row.market_score,
        total_score=row.total_score,
        status_label=row.status_label,
        setup_type=row.setup_type,
        entry=row.entry,
        stop_loss=row.stop_loss,
        target1=row.target1,
        target2=row.target2,
        risk_reward=row.risk_reward,
        reasons=json.loads(row.reasons_json or "[]"),
        warnings=json.loads(row.warnings_json or "[]"),
        news_sentiment=row.news_sentiment,
        data_source=row.data_source,
        data_timestamp=row.data_timestamp,
    )
