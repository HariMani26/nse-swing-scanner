"""Shared pytest fixtures: in-memory SQLite session + synthetic OHLCV data."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_ohlcv(days: int = 300, trend: str = "up", seed: int = 42) -> pd.DataFrame:
    """Build a simple deterministic OHLCV series for indicator/scoring tests."""
    rng = np.random.default_rng(seed)
    drift = {"up": 0.0025, "down": -0.0025, "flat": 0.0}[trend]
    returns = rng.normal(drift, 0.01, size=days)
    close = 100 * np.cumprod(1 + returns)
    close = np.maximum(close, 1.0)
    high = close * 1.01
    low = close * 0.99
    open_ = close * 1.001
    volume = np.full(days, 100_000.0)

    idx = pd.bdate_range(end=pd.Timestamp.today(), periods=days)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
