"""Time-based pattern extraction.

Goal: discover statements like "living_room_light usually turns ON around
19:00" purely by clustering the *time of day* of repeated (device, action)
events across the analysis window.

Algorithm (deterministic)
=========================
1. Group events by (device_id, action).
2. For each group, convert every event's local time to "minutes since
   midnight".
3. Bucket those minutes into fixed-width buckets (default 30 min) and pick the
   dominant bucket (the routine candidate).
4. Compute the mean & stddev of the times that fall in / near that bucket.
5. Score confidence from support (count) and consistency (stddev).
6. Emit a TimePattern when occurrences and confidence clear the thresholds.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime

from patterns.app.config import get_settings
from patterns.models.events import Event
from patterns.models.patterns import TimePattern
from patterns.pattern_engine import confidence as conf


def _minutes_of_day(ts: datetime) -> int:
    return ts.hour * 60 + ts.minute


def _fmt_hhmm(total_minutes: float) -> str:
    m = int(round(total_minutes)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def extract_time_patterns(
    household_id: str, events: list[Event]
) -> list[TimePattern]:
    s = get_settings()
    bucket = s.time_bucket_minutes

    # (device_id, action) -> list[minutes_of_day]
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    # Keep a representative device_type/action for output.
    for ev in events:
        groups[(ev.device_id, ev.action.value)].append(_minutes_of_day(ev.timestamp))

    patterns: list[TimePattern] = []
    for (device_id, action), minutes in groups.items():
        if len(minutes) < s.min_pattern_occurrences:
            continue

        # Find the dominant time bucket, then gather every observation within
        # one bucket-width of that bucket's centre. The sliding window prevents
        # events that straddle a bucket boundary (e.g. 18:58 vs 19:02 around a
        # 19:00 routine) from being split across two buckets and losing support.
        bucket_counts: dict[int, list[int]] = defaultdict(list)
        for m in minutes:
            bucket_counts[m // bucket].append(m)
        dominant_bucket = max(bucket_counts, key=lambda b: len(bucket_counts[b]))
        center = dominant_bucket * bucket + bucket / 2
        cluster = [m for m in minutes if abs(m - center) <= bucket]

        if len(cluster) < s.min_pattern_occurrences:
            continue

        mean_minute = statistics.mean(cluster)
        stddev = statistics.pstdev(cluster) if len(cluster) > 1 else 0.0

        support = conf.support_score(len(cluster), s.analysis_window_days)
        consistency = conf.consistency_score(stddev, tolerance=bucket)
        score = conf.combine(support, consistency)
        if score < s.min_confidence:
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
