"""SQLAlchemy ORM models."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


class Stock(Base):
    """A single entry in the tracked stock universe / watchlist."""

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), default="")
    sector: Mapped[str] = mapped_column(String(128), default="")
    source: Mapped[str] = mapped_column(String(64), default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    style: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(Integer)
    entry: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target1: Mapped[float] = mapped_column(Float)
    target2: Mapped[float | None] = mapped_column(Float, nullable=True)
    opened_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str] = mapped_column(String(255), default="")


class TradingAlert(Base):
    __tablename__ = "trading_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(255), unique=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    provider_timestamp: Mapped[str] = mapped_column(String(64))
    price: Mapped[float] = mapped_column(Float)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class PriceBar(Base):
    """Cached daily OHLCV bar for a symbol."""

    __tablename__ = "price_bars"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_price_bar_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    date: Mapped[str] = mapped_column(String(10), index=True, nullable=False)  # YYYY-MM-DD
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), default="mock")
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class NewsItem(Base):
    """Cached news headline for a symbol."""

    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    headline: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024), default="")
    published_at: Mapped[dt.datetime] = mapped_column(DateTime)
    sentiment: Mapped[str] = mapped_column(String(16), default="neutral")  # positive/neutral/negative
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class MarketContextSnapshot(Base):
    """Snapshot of overall market trend (NIFTY 50 / NIFTY 500)."""

    __tablename__ = "market_context"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nifty50_value: Mapped[float] = mapped_column(Float, default=0.0)
    nifty50_change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    nifty500_value: Mapped[float] = mapped_column(Float, default=0.0)
    nifty500_change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    trend: Mapped[str] = mapped_column(String(16), default="neutral")  # bullish/neutral/bearish
    source: Mapped[str] = mapped_column(String(64), default="mock")
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ScanRun(Base):
    """A single execution of the scanner across the whole universe."""

    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running/completed/failed
    stocks_scanned: Mapped[int] = mapped_column(Integer, default=0)
    stocks_failed: Mapped[int] = mapped_column(Integer, default=0)
    trigger: Mapped[str] = mapped_column(String(16), default="manual")  # manual/scheduled

    results: Mapped[list["ScanResult"]] = relationship(back_populates="scan_run")


class ScanResult(Base):
    """Scoring output for one symbol in a given scan run."""

    __tablename__ = "scan_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_run_id: Mapped[int] = mapped_column(ForeignKey("scan_runs.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), default="")
    sector: Mapped[str] = mapped_column(String(128), default="")

    data_available: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str] = mapped_column(String(255), default="")

    price: Mapped[float] = mapped_column(Float, default=0.0)
    daily_change_pct: Mapped[float] = mapped_column(Float, default=0.0)
    ema20: Mapped[float] = mapped_column(Float, default=0.0)
    ema50: Mapped[float] = mapped_column(Float, default=0.0)
    rsi14: Mapped[float] = mapped_column(Float, default=0.0)
    macd: Mapped[float] = mapped_column(Float, default=0.0)
    macd_signal: Mapped[float] = mapped_column(Float, default=0.0)
    macd_hist: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    avg_volume20: Mapped[float] = mapped_column(Float, default=0.0)
    atr14: Mapped[float] = mapped_column(Float, default=0.0)
    high_52w: Mapped[float] = mapped_column(Float, default=0.0)
    distance_from_high_pct: Mapped[float] = mapped_column(Float, default=0.0)
    recent_support: Mapped[float] = mapped_column(Float, default=0.0)
    recent_resistance: Mapped[float] = mapped_column(Float, default=0.0)

    technical_score: Mapped[float] = mapped_column(Float, default=0.0)
    news_score: Mapped[float] = mapped_column(Float, default=0.0)
    market_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    status_label: Mapped[str] = mapped_column(String(32), default="AVOID / WEAK SETUP")

    setup_type: Mapped[str] = mapped_column(String(16), default="none")  # breakout/pullback/none
    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    target1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target2: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward: Mapped[float | None] = mapped_column(Float, nullable=True)

    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    news_sentiment: Mapped[str] = mapped_column(String(32), default="unavailable")

    data_source: Mapped[str] = mapped_column(String(64), default="mock")
    data_timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)

    scan_run: Mapped["ScanRun"] = relationship(back_populates="results")
