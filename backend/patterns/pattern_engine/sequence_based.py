"""Sequence-based pattern extraction.

Goal: discover recurring *ordered chains* of events that happen close together
in time, e.g. the "son leaves for college" departure routine:

    son_room presence:LEAVE -> son_room_fan:OFF -> son_room_light:OFF

Algorithm (deterministic)
=========================
1. Sort all events chronologically.
2. Slice the timeline into *sessions*: consecutive events whose gaps are below
   ``MAX_GAP_MINUTES`` belong to the same session (a burst of related activity).
3. Represent each session as a tuple of "device:action" steps.
4. Count identical session signatures across days.
5. A signature seen on >= min_pattern_occurrences distinct days becomes a
   SequencePattern; confidence scales with how reliably the chain repeats.

The approach is intentionally simple and explainable. It captures the
"door opens, then everything switches off" style routines from the brief
without any learning model.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime

from patterns.app.config import get_settings
from patterns.models.events import Event
from patterns.models.patterns import SequencePattern
from patterns.pattern_engine import confidence as conf

# Events within this many minutes of each other form one logical session.
MAX_GAP_MINUTES = 10
# Ignore trivially short sessions — a routine needs at least this many steps.
MIN_SEQUENCE_LENGTH = 2
# Cap session length so a busy evening doesn't create a giant unique signature.
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
    # Heuristic human label for common departure routine.
    joined = " -> ".join(signature)
    has_leave_or_open = any(s.endswith(":LEAVE") or s.endswith(":OPEN") for s in signature)
    all_off = all(s.endswith(":OFF") for s in signature[1:]) if len(signature) > 1 else False
    if has_leave_or_open and all_off:
        return "Departure routine: home secured / devices switched off"
    return joined


def extract_sequence_patterns(
    household_id: str, events: list[Event]
) -> list[SequencePattern]:
    s = get_settings()
    sessions = _sessionize(events)

    # signature -> list of session start minutes-of-day (for usual_time)
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
        if len(starts) < s.min_pattern_occurrences:
            continue
        mean_start = statistics.mean(starts)
        stddev = statistics.pstdev(starts) if len(starts) > 1 else 0.0

        support = conf.support_score(len(starts), s.analysis_window_days)
        consistency = conf.consistency_score(stddev, tolerance=s.time_bucket_minutes)
        score = conf.combine(support, consistency)
        if score < s.min_confidence:
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
