"""Sequence-based pattern extraction.

Discovers recurring ordered chains of events that happen close together,
e.g. the "son leaves for college" departure routine.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from config import settings

from services.patterns.models import Event, SequencePattern
from services.patterns.engine import confidence as conf

# Events within this many minutes of each other form one logical session.
MAX_GAP_MINUTES = 10
MIN_SEQUENCE_LENGTH = 2
MAX_SEQUENCE_LENGTH = 6


def _sessionize(events: list[Event]) -> list[list[Event]]:
    ordered = sorted(events, key=lambda e: e.timestamp)
    sessions: list[list[Event]] = []
    current: list[Event] = []
    last_ts: datetime | None = None
    for ev in ordered:
        if last_ts is not None and (ev.timestamp - last_ts).total_seconds() > MAX_GAP_MINUTES * 60:
            if current:
                sessions.append(current)
            current = []
        current.append(ev)
        last_ts = ev.timestamp
    if current:
        sessions.append(current)
    return sessions


def _signature(session: list[Event]) -> tuple[str, ...]:
    steps = [f"{e.device_id}:{e.action.value}" for e in session]
    return tuple(steps[:MAX_SEQUENCE_LENGTH])


def _describe(signature: tuple[str, ...]) -> str:
    joined = " -> ".join(signature)
    has_leave_or_open = any(s.endswith(":LEAVE") or s.endswith(":OPEN") for s in signature)
    all_off = all(s.endswith(":OFF") for s in signature[1:]) if len(signature) > 1 else False
    if has_leave_or_open and all_off:
        return "Departure routine: home secured / devices switched off"
    return joined


def extract_sequence_patterns(
    household_id: str, events: list[Event]
) -> list[SequencePattern]:
    sessions = _sessionize(events)

    # signature -> list of session start minutes-of-day
    sig_times: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for session in sessions:
        if len(session) < MIN_SEQUENCE_LENGTH:
            continue
        sig = _signature(session)
        start = session[0].timestamp
        sig_times[sig].append(start.hour * 60 + start.minute)

    patterns: list[SequencePattern] = []
    idx = 1
    for sig, starts in sig_times.items():
        if len(starts) < settings.min_pattern_occurrences:
            continue
        mean_start = statistics.mean(starts)
        stddev = statistics.pstdev(starts) if len(starts) > 1 else 0.0

        support = conf.support_score(len(starts), settings.analysis_window_days)
        consistency = conf.consistency_score(stddev, tolerance=settings.time_bucket_minutes)
        score = conf.combine(support, consistency)
        if score < settings.min_confidence:
            continue

        usual = f"{int(mean_start) // 60:02d}:{int(mean_start) % 60:02d}"
        patterns.append(
            SequencePattern(
                pattern_id=f"SEQ#{idx:03d}",
                household_id=household_id,
                description=_describe(sig),
                steps=list(sig),
                usual_time=usual,
                occurrences=len(starts),
                confidence=score,
            )
        )
        idx += 1
    return patterns
