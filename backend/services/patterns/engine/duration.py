"""Duration-based pattern extraction.

Learns how long a device normally stays on so the system can flag anomalies
like "water motor running 45 min vs usual 15 min".
"""
from __future__ import annotations

import statistics
from collections import defaultdict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

from services.patterns.models import Event, DurationPattern
from services.patterns.engine import confidence as conf

ON_ACTIONS = {"ON", "OPEN"}
OFF_ACTIONS = {"OFF", "CLOSE"}


def _runtimes_per_device(events: list[Event]) -> dict[str, list[float]]:
    by_device: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        by_device[ev.device_id].append(ev)

    runtimes: dict[str, list[float]] = defaultdict(list)
    for device_id, dev_events in by_device.items():
        dev_events.sort(key=lambda e: e.timestamp)
        on_ts = None
        for ev in dev_events:
            if ev.action.value in ON_ACTIONS:
                on_ts = ev.timestamp
            elif ev.action.value in OFF_ACTIONS and on_ts is not None:
                minutes = (ev.timestamp - on_ts).total_seconds() / 60.0
                if minutes > 0:
                    runtimes[device_id].append(minutes)
                on_ts = None
    return runtimes


def extract_duration_patterns(
    household_id: str, events: list[Event]
) -> list[DurationPattern]:
    patterns: list[DurationPattern] = []

    for device_id, runtimes in _runtimes_per_device(events).items():
        if len(runtimes) < settings.min_pattern_occurrences:
            continue
        mean = statistics.mean(runtimes)
        stddev = statistics.pstdev(runtimes) if len(runtimes) > 1 else 0.0

        support = conf.support_score(len(runtimes), settings.analysis_window_days)
        consistency = conf.consistency_score(stddev, tolerance=max(mean * 0.25, 1.0))
        score = conf.combine(support, consistency)
        if score < settings.min_confidence:
            continue

        patterns.append(
            DurationPattern(
                pattern_id=f"DUR#{device_id}",
                household_id=household_id,
                device=device_id,
                usual_duration_minutes=round(mean, 1),
                stddev_minutes=round(stddev, 1),
                occurrences=len(runtimes),
                confidence=score,
            )
        )
    return patterns
