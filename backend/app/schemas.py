"""Pydantic schemas for API request/response payloads."""
from __future__ import annotations

import datetime as dt
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class StockCreate(BaseModel):
    symbol: str
    company_name: str = ""
    sector: str = ""


class RiskRequest(BaseModel):
    capital: float = Field(300000, gt=0, le=1000000000, allow_inf_nan=False)
    risk_percent: float = Field(0.5, gt=0, le=1, allow_inf_nan=False)
    allocation: float = Field(300000, gt=0, allow_inf_nan=False)
    entry: float = Field(..., gt=0, allow_inf_nan=False)
    stop_loss: float = Field(..., gt=0, allow_inf_nan=False)
    target1: float = Field(..., gt=0, allow_inf_nan=False)
    side: Literal["BUY", "SELL"] = "BUY"


class PositionRequest(RiskRequest):
    symbol: str = Field(..., min_length=1, max_length=32)
    style: Literal["SWING", "INTRADAY"] = "SWING"
    target2: Optional[float] = Field(None, gt=0, allow_inf_nan=False)
    quantity: int = Field(..., gt=0)
    acknowledge_paper: bool = False
    acknowledge_correlation: bool = False


class ClosePositionRequest(BaseModel):
    exit_price: float = Field(..., gt=0, allow_inf_nan=False)
    reason: str = Field("Manual paper exit", max_length=255)


class StockOut(BaseModel):
    id: int
    symbol: str
    company_name: str
    sector: str
    source: str
    is_active: bool

    class Config:
        from_attributes = True


class NewsItemOut(BaseModel):
    headline: str
    source: str
    url: str
    published_at: dt.datetime
    sentiment: str
    provider: str

    class Config:
        from_attributes = True


class ScanResultOut(BaseModel):
    symbol: str
    company_name: str
    sector: str

    data_available: bool
    error_message: str

    price: float
    daily_change_pct: float
    ema20: float
    ema50: float
    rsi14: float
    macd: float
    macd_signal: float
    macd_hist: float
    volume: float
    avg_volume20: float
    atr14: float
    high_52w: float
    distance_from_high_pct: float
    recent_support: float
    recent_resistance: float

    technical_score: float
    news_score: float
    market_score: float
    total_score: float
    status_label: str

    setup_type: str
    entry: Optional[float]
    stop_loss: Optional[float]
    target1: Optional[float]
    target2: Optional[float]
    risk_reward: Optional[float]

    reasons: List[str]
    warnings: List[str]
    news_sentiment: str

    data_source: str
    data_timestamp: dt.datetime

    class Config:
        from_attributes = True


class MarketContextOut(BaseModel):
    nifty50_value: float
    nifty50_change_pct: float
    nifty500_value: float
    nifty500_change_pct: float
    trend: str
    source: str
    fetched_at: dt.datetime
    is_market_open: bool

    class Config:
        from_attributes = True


class ScanRunOut(BaseModel):
    id: int
    started_at: dt.datetime
    finished_at: Optional[dt.datetime]
    status: str
    stocks_scanned: int
    stocks_failed: int
    trigger: str

    class Config:
        from_attributes = True


class DashboardOut(BaseModel):
    last_scan: Optional[ScanRunOut]
    market: MarketContextOut
    candidates: List[ScanResultOut]


class TrendPointOut(BaseModel):
    date: str
    value: float


class SwingPointOut(TrendPointOut):
    kind: str
    label: str


class DailyAnalysisOut(BaseModel):
    trend: str
    signal: str
    as_of: Optional[str]
    reason: str
    pivots: List[SwingPointOut]
    support_line: List[TrendPointOut]
    resistance_line: List[TrendPointOut]
    support: Optional[float]
    resistance: Optional[float]
    volume_ratio: Optional[float]
    entry: Optional[float]
    stop_loss: Optional[float]
    target: Optional[float]
    risk_reward: Optional[float]


class StockQuoteOut(BaseModel):
    symbol: str
    price: Optional[float]
    change_pct: Optional[float]
    source: str
    is_delayed: bool
    timestamp: Optional[str]
    fetched_at: Optional[str]
    age_seconds: Optional[int]
    is_stale: bool
    market_open: bool
    refresh_seconds: int
    error: Optional[str]


class StockDetailOut(BaseModel):
    stock: StockOut
    latest_result: Optional[ScanResultOut]
    news: List[NewsItemOut]
    candles: List["CandleOut"]
    daily_analysis: DailyAnalysisOut
    data_source: str


class CandleOut(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None


StockDetailOut.model_rebuild()


class CsvPreviewOut(BaseModel):
    columns: List[str]
    rows: List[dict]
    row_count: int


class CsvImportRequest(BaseModel):
    column_mapping: dict = Field(..., description="Maps target field -> CSV column name, e.g. {'symbol': 'Symbol'}")
    mode: str = Field("add", description="'add' to append to universe, 'replace' to replace it")
    rows: List[dict] = Field(..., description="Raw CSV rows as returned by the preview endpoint")


class CsvImportResult(BaseModel):
    imported: int
    skipped: int
    mode: str
    total_universe: int
