"""Confidence scoring helpers shared by all extractors.

Confidence is deterministic and explainable — no ML, no randomness.
Combines support (observation count) and consistency (low variance).
"""
from __future__ import annotations


def support_score(occurrences: int, window_days: int) -> float:
    """Map occurrence count to [0, 1]."""
    if window_days <= 0:
        return 0.0
    return min(1.0, occurrences / window_days)


def consistency_score(stddev: float, tolerance: float) -> float:
    """Map dispersion to [0, 1]."""
    if tolerance <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (stddev / (tolerance * 2))))


def combine(support: float, consistency: float) -> float:
    """Final confidence = support * consistency, clamped to [0, 1]."""
    return round(max(0.0, min(1.0, support * consistency)), 3)
