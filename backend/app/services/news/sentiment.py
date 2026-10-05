"""Very simple, explainable keyword-based sentiment classifier for headlines.

This is NOT a machine-learning model - it is a transparent keyword scan so
the resulting sentiment label can always be explained. It intentionally
errs towards "neutral" when it is unsure rather than guessing.
"""
from __future__ import annotations

from typing import List

STRONG_POSITIVE_WORDS = [
    "record profit", "record high", "beats estimates", "wins order", "big order",
    "upgraded", "outperform", "strong growth", "surge", "rally", "bags order",
    "raises guidance",
]
POSITIVE_WORDS = [
    "profit", "growth", "order win", "expansion", "partnership", "upgrade",
    "positive", "gains", "contract", "approval", "launch", "increase", "rises",
]
STRONG_NEGATIVE_WORDS = [
    "fraud", "scam", "probe", "raid", "downgraded to sell", "plunge", "crashes",
    "default", "insolvency", "resigns amid", "regulatory action", "banned",
]
NEGATIVE_WORDS = [
    "loss", "decline", "falls", "downgrade", "lawsuit", "investigation", "penalty",
    "delay", "cut guidance", "weak", "drop", "concern", "layoff",
]


def classify_headline(headline: str) -> str:
    text = headline.lower()

    if any(w in text for w in STRONG_NEGATIVE_WORDS):
        return "strongly_negative"
    if any(w in text for w in STRONG_POSITIVE_WORDS):
        return "strongly_positive"
    if any(w in text for w in NEGATIVE_WORDS):
        return "negative"
    if any(w in text for w in POSITIVE_WORDS):
        return "positive"
    return "neutral"


_RANK = {
    "strongly_negative": -2,
    "negative": -1,
    "neutral": 0,
    "positive": 1,
    "strongly_positive": 2,
}
_REVERSE_RANK = {v: k for k, v in _RANK.items()}


def aggregate_sentiment(sentiments: List[str]) -> str:
    """Combine several headline sentiments into one overall label (average, rounded)."""
    if not sentiments:
        return "neutral"
    avg = sum(_RANK.get(s, 0) for s in sentiments) / len(sentiments)
    rounded = max(-2, min(2, round(avg)))
    return _REVERSE_RANK[rounded]
