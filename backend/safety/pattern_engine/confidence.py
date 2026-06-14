"""Confidence scoring helpers shared by all extractors.

Design decision
===============
Confidence must be *deterministic* and explainable — no ML, no randomness.
We combine two intuitive signals:

* **Support**  — how many times the behaviour was observed. More observations
  over the window => more trustworthy. Saturates so a routine seen 30/30 days
  isn't unfairly penalised vs one seen 50 times.
* **Consistency** — how tightly the observations cluster (low variance in time
  or duration => high consistency).

The final score is the product, clamped to [0, 1]. Using a product means a
pattern needs *both* enough evidence *and* regularity to score highly.
"""
from __future__ import annotations


def support_score(occurrences: int, window_days: int) -> float:
    """Map occurrence count to [0, 1].

    We treat "happens roughly daily" (occurrences ~= window_days) as full
    support. Capped at 1.0 so very chatty devices don't overflow.
    """
    if window_days <= 0:
        return 0.0
    return min(1.0, occurrences / window_days)


def consistency_score(stddev: float, tolerance: float) -> float:
    """Map dispersion to [0, 1].

    ``stddev`` and ``tolerance`` share units (minutes). A spread at or below the
    tolerance scores ~1.0; larger spreads decay linearly toward 0.
    """
    if tolerance <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (stddev / (tolerance * 2))))


def combine(support: float, consistency: float) -> float:
    """Final confidence = support * consistency, clamped to [0, 1]."""
    return round(max(0.0, min(1.0, support * consistency)), 3)
