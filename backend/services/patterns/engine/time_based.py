"""Time-based pattern extraction.

Discovers statements like "living_room_light usually turns ON around 19:00"
by clustering the time of day of repeated (device, action) events.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

from services.patterns.models import Event, TimePattern
from services.patterns.engine import confidence as conf


def _minutes_of_day(ts: datetime) -> int:
    return ts.hour * 60 + ts.minute


def _fmt_hhmm(total_minutes: float) -> str:
    m = int(round(total_minutes)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def extract_time_patterns(
    household_id: str, events: list[Event]
) -> list[TimePattern]:
    bucket = settings.time_bucket_minutes

    # (device_id, action) -> list[minutes_of_day]
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for ev in events:
        groups[(ev.device_id, ev.action.value)].append(_minutes_of_day(ev.timestamp))

    patterns: list[TimePattern] = []
    for (device_id, action), minutes in groups.items():
        if len(minutes) < settings.min_pattern_occurrences:
            continue

        bucket_counts: dict[int, list[int]] = defaultdict(list)
        for m in minutes:
            bucket_counts[m // bucket].append(m)
        dominant_bucket = max(bucket_counts, key=lambda b: len(bucket_counts[b]))
        center = dominant_bucket * bucket + bucket / 2
        cluster = [m for m in minutes if abs(m - center) <= bucket]

        if len(cluster) < settings.min_pattern_occurrences:
            continue

        mean_minute = statistics.mean(cluster)
        stddev = statistics.pstdev(cluster) if len(cluster) > 1 else 0.0

        support = conf.support_score(len(cluster), settings.analysis_window_days)
        consistency = conf.consistency_score(stddev, tolerance=bucket)
        score = conf.combine(support, consistency)
        if score < settings.min_confidence:
            continue

        pattern_id = f"TIME#{device_id}#{action}"
        patterns.append(
            TimePattern(
                pattern_id=pattern_id,
                household_id=household_id,
                device=device_id,
                action=action,
                usual_time=_fmt_hhmm(mean_minute),
                window_minutes=max(bucket, int(math.ceil(stddev)) or bucket),
                occurrences=len(cluster),
                confidence=score,
            )
        )
    return patterns
