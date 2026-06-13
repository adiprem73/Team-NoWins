"""Synthetic 30-day event generator for household H001.

Produces a realistic history that exercises every extractor:
  * Time pattern   : porch_light ON ~19:00 daily (Example 2)
  * Sequence       : son departure ~08:00 (presence LEAVE -> fan OFF -> light OFF) (Example 1)
  * Duration       : water_motor runs ~15 min daily (Example 4)
  * Arrival routine: living_room_ac ON ~17:45 before mother arrives 18:00 (Example 3)

Also produces a "today" snapshot that deliberately leaves the son's fan & light
ON past 08:00 so the context builder reports a departure anomaly.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from patterns.models.events import DeviceAction, DeviceType, EventCreate

HOUSEHOLD = "H001"
random.seed(42)  # deterministic sample data


def _at(day: datetime, hour: int, minute: int, jitter: int = 0) -> datetime:
    minute += random.randint(-jitter, jitter) if jitter else 0
    base = day.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(minutes=minute)


def generate(days: int = 30, *, include_today_anomaly: bool = True) -> list[EventCreate]:
    events: list[EventCreate] = []
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for d in range(days, 0, -1):
        day = today - timedelta(days=d)

        # --- Son departure routine ~08:00 ---
        # Spacing > jitter keeps the LEAVE -> fan OFF -> light OFF order stable
        # so the sequence extractor sees one consistent signature.
        events += [
            EventCreate(household_id=HOUSEHOLD, device_id="son_presence",
                        device_type=DeviceType.PRESENCE, room="son_room",
                        action=DeviceAction.LEAVE, triggered_by="son",
                        timestamp=_at(day, 8, 0, jitter=2)),
            EventCreate(household_id=HOUSEHOLD, device_id="son_room_fan",
                        device_type=DeviceType.FAN, room="son_room",
                        action=DeviceAction.OFF, triggered_by="son",
                        timestamp=_at(day, 8, 4, jitter=1)),
            EventCreate(household_id=HOUSEHOLD, device_id="son_room_light",
                        device_type=DeviceType.LIGHT, room="son_room",
                        action=DeviceAction.OFF, triggered_by="son",
                        timestamp=_at(day, 8, 7, jitter=1)),
        ]

        # --- Water motor ~15 min run mid-morning ---
        motor_on = _at(day, 9, 0, jitter=10)
        events += [
            EventCreate(household_id=HOUSEHOLD, device_id="water_motor",
                        device_type=DeviceType.MOTOR, room="utility",
                        action=DeviceAction.ON, triggered_by="system",
                        timestamp=motor_on),
            EventCreate(household_id=HOUSEHOLD, device_id="water_motor",
                        device_type=DeviceType.MOTOR, room="utility",
                        action=DeviceAction.OFF, triggered_by="system",
                        timestamp=motor_on + timedelta(minutes=15 + random.randint(-2, 2))),
        ]

        # --- Living room AC ON ~17:45 before mother arrives 18:00 ---
        events += [
            EventCreate(household_id=HOUSEHOLD, device_id="living_room_ac",
                        device_type=DeviceType.AC, room="living_room",
                        action=DeviceAction.ON, triggered_by="father",
                        timestamp=_at(day, 17, 45, jitter=8)),
            EventCreate(household_id=HOUSEHOLD, device_id="mother_presence",
                        device_type=DeviceType.PRESENCE, room="entrance",
                        action=DeviceAction.ARRIVE, triggered_by="mother",
                        timestamp=_at(day, 18, 0, jitter=10)),
        ]

        # --- Porch light ON ~19:00, OFF ~23:00 ---
        events += [
            EventCreate(household_id=HOUSEHOLD, device_id="porch_light",
                        device_type=DeviceType.LIGHT, room="porch",
                        action=DeviceAction.ON, triggered_by="system",
                        timestamp=_at(day, 19, 0, jitter=6)),
            EventCreate(household_id=HOUSEHOLD, device_id="porch_light",
                        device_type=DeviceType.LIGHT, room="porch",
                        action=DeviceAction.OFF, triggered_by="system",
                        timestamp=_at(day, 23, 0, jitter=10)),
        ]

    if include_today_anomaly:
        # Today: son turned devices ON in the morning but DID NOT switch them
        # off when leaving -> they should still be active well past 08:00.
        today_morning = today.replace(hour=7, minute=30, tzinfo=timezone.utc)
        events += [
            EventCreate(household_id=HOUSEHOLD, device_id="son_room_fan",
                        device_type=DeviceType.FAN, room="son_room",
                        action=DeviceAction.ON, triggered_by="son",
                        timestamp=today_morning),
            EventCreate(household_id=HOUSEHOLD, device_id="son_room_light",
                        device_type=DeviceType.LIGHT, room="son_room",
                        action=DeviceAction.ON, triggered_by="son",
                        timestamp=today_morning),
            EventCreate(household_id=HOUSEHOLD, device_id="son_presence",
                        device_type=DeviceType.PRESENCE, room="son_room",
                        action=DeviceAction.LEAVE, triggered_by="son",
                        timestamp=today.replace(hour=8, minute=5, tzinfo=timezone.utc)),
        ]

    return events
