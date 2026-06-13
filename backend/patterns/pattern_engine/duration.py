"""Duration-based pattern extraction.

Goal: learn how long a device *normally* stays on, so the system can later flag
"water motor running 45 min vs usual 15 min" style anomalies.

Algorithm (deterministic)
=========================
1. For each device, walk its events in chronological order and pair each ON
   with the next OFF to compute a runtime (minutes).
2. Collect all runtimes per device.
3. Compute mean & stddev; emit a DurationPattern when there is enough support.

Confidence here rewards consistency: a device that always runs ~15 min scores
high; one whose runtime is all over the place scores low.
"""
from __future__ import annotations

import statistics
from collections import defaultdict

from patterns.app.config import get_settings
from patterns.models.events import Event
from patterns.models.patterns import DurationPattern
from patterns.pattern_engine import confidence as conf

ON_ACTIONS = {"ON", "OPEN"}
OFF_ACTIONS = {"OFF", "CLOSE"}


def _runtimes_per_device(events: list[Event]) -> dict[str, list[tuple[float, int]]]:
    """device -> list of (runtime_minutes, start_minute_of_day) pairs.

    Pairing each ON with the next OFF gives both *how long* the device ran and
    *when* it started — so a duration pattern can say not just "runs ~15 min"
    but "runs ~15 min, usually starting around 09:00".
    """
    by_device: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        by_device[ev.device_id].append(ev)

    runtimes: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for device_id, dev_events in by_device.items():
        dev_events.sort(key=lambda e: e.timestamp)
        on_ts = None
        for ev in dev_events:
            if ev.action.value in ON_ACTIONS:
                on_ts = ev.timestamp
            elif ev.action.value in OFF_ACTIONS and on_ts is not None:
                minutes = (ev.timestamp - on_ts).total_seconds() / 60.0
                if minutes > 0:
                    start_min = on_ts.hour * 60 + on_ts.minute
                    runtimes[device_id].append((minutes, start_min))
                on_ts = None
    return runtimes


def _fmt_hhmm(total_minutes: float) -> str:
    m = int(round(total_minutes)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def extract_duration_patterns(
    household_id: str, events: list[Event]
) -> list[DurationPattern]:
    s = get_settings()
    patterns: list[DurationPattern] = []

    for device_id, samples in _runtimes_per_device(events).items():
        if len(samples) < s.min_pattern_occurrences:
            continue
        runtimes = [r for r, _ in samples]
        start_mins = [st for _, st in samples]
        mean = statistics.mean(runtimes)
        stddev = statistics.pstdev(runtimes) if len(runtimes) > 1 else 0.0

        support = conf.support_score(len(runtimes), s.analysis_window_days)
        # Tolerance scales with the mean: 25% of typical runtime.
        consistency = conf.consistency_score(stddev, tolerance=max(mean * 0.25, 1.0))
        score = conf.combine(support, consistency)
        if score < s.min_confidence:
            continue

        patterns.append(
            DurationPattern(
                pattern_id=f"DUR#{device_id}",
                household_id=household_id,
                device=device_id,
                usual_duration_minutes=round(mean, 1),
                stddev_minutes=round(stddev, 1),
                usual_start_time=_fmt_hhmm(statistics.mean(start_mins)),
                occurrences=len(runtimes),
                confidence=score,
            )
        )
    return patterns
