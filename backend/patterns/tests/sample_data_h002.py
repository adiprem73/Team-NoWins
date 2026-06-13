"""Second synthetic scenario (household H002) — AC / motor / light focused.

Where ``sample_data.py`` (H001) centres on a son's departure routine, this
scenario stresses the engine with a *different* device mix and richer routines
so every extractor and every anomaly detector is exercised independently.

Learned behaviour over 30 days
==============================
TIME patterns
  * garden_light   ON  ~06:30, OFF ~07:30   (morning garden light)
  * porch_light    ON  ~19:15, OFF ~22:30   (evening security light)
  * bedroom_ac     ON  ~22:00, OFF ~06:00   (overnight AC)
SEQUENCE pattern
  * "evening arrival": front_door OPEN -> living_room_light ON -> living_room_ac ON
DURATION patterns
  * borewell_motor runs ~20 min daily
  * bedroom_ac     runs ~8 h overnight

"Today" anomalies (toggle via flags)
====================================
  * include_motor_anomaly : borewell_motor still ON for 60 min (usual ~20) ->
                            duration_exceeded
  * include_ac_left_on    : living_room_ac left ON long past its usual OFF ->
                            device_left_on / departure-style anomaly
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from patterns.models.events import DeviceAction, DeviceType, EventCreate

HOUSEHOLD = "H002"
_rng = random.Random(7)  # deterministic, independent of H001's RNG


def _at(day: datetime, hour: int, minute: int, jitter: int = 0) -> datetime:
    minute += _rng.randint(-jitter, jitter) if jitter else 0
    base = day.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(minutes=minute)


def generate(
    days: int = 30,
    *,
    include_motor_anomaly: bool = True,
    include_ac_left_on: bool = True,
) -> list[EventCreate]:
    events: list[EventCreate] = []
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    def add(device_id, device_type, room, action, ts, triggered_by="system"):
        events.append(
            EventCreate(
                household_id=HOUSEHOLD,
                device_id=device_id,
                device_type=device_type,
                room=room,
                action=action,
                triggered_by=triggered_by,
                timestamp=ts,
            )
        )

    for d in range(days, 0, -1):
        day = today - timedelta(days=d)

        # --- Morning garden light ON ~06:30, OFF ~07:30 (1 h duration) ---
        g_on = _at(day, 6, 30, jitter=8)
        add("garden_light", DeviceType.LIGHT, "garden", DeviceAction.ON, g_on)
        add("garden_light", DeviceType.LIGHT, "garden", DeviceAction.OFF,
            g_on + timedelta(minutes=60 + _rng.randint(-5, 5)))

        # --- Borewell motor ~20 min run mid-morning ---
        m_on = _at(day, 8, 0, jitter=10)
        add("borewell_motor", DeviceType.MOTOR, "utility", DeviceAction.ON, m_on)
        add("borewell_motor", DeviceType.MOTOR, "utility", DeviceAction.OFF,
            m_on + timedelta(minutes=20 + _rng.randint(-3, 3)))

        # --- Evening arrival sequence ~18:30 ---
        # front_door OPEN -> living_room_light ON -> living_room_ac ON
        d_open = _at(day, 18, 30, jitter=6)
        add("front_door", DeviceType.DOOR, "entrance", DeviceAction.OPEN, d_open,
            triggered_by="father")
        add("living_room_light", DeviceType.LIGHT, "living_room", DeviceAction.ON,
            d_open + timedelta(minutes=2), triggered_by="father")
        add("living_room_ac", DeviceType.AC, "living_room", DeviceAction.ON,
            d_open + timedelta(minutes=4), triggered_by="father")
        # ...turned off later in the evening (~22:45) so AC has an OFF time.
        add("living_room_ac", DeviceType.AC, "living_room", DeviceAction.OFF,
            _at(day, 22, 45, jitter=10), triggered_by="father")
        add("living_room_light", DeviceType.LIGHT, "living_room", DeviceAction.OFF,
            _at(day, 22, 50, jitter=10), triggered_by="father")

        # --- Porch security light ON ~19:15, OFF ~22:30 ---
        # Deliberately offset from the 18:30 arrival burst by > MAX_GAP_MINUTES
        # so it doesn't merge into the arrival session and scramble its
        # sequence signature.
        add("porch_light", DeviceType.LIGHT, "porch", DeviceAction.ON,
            _at(day, 19, 15, jitter=5))
        add("porch_light", DeviceType.LIGHT, "porch", DeviceAction.OFF,
            _at(day, 22, 30, jitter=8))

        # --- Overnight bedroom AC ON ~22:00, OFF ~06:00 next morning ---
        ac_on = _at(day, 22, 0, jitter=10)
        add("bedroom_ac", DeviceType.AC, "bedroom", DeviceAction.ON, ac_on,
            triggered_by="mother")
        add("bedroom_ac", DeviceType.AC, "bedroom", DeviceAction.OFF,
            ac_on + timedelta(hours=8, minutes=_rng.randint(-20, 20)),
            triggered_by="mother")

    # ---------------- TODAY: inject anomalies ----------------
    if include_motor_anomaly:
        # Motor switched ON 60 min ago and never stopped (usual ~20 min).
        sixty_ago = datetime.now(timezone.utc) - timedelta(minutes=60)
        add("borewell_motor", DeviceType.MOTOR, "utility", DeviceAction.ON, sixty_ago)

    if include_ac_left_on:
        # Living-room AC turned on this morning and left running (usual OFF ~22:45).
        morning = today.replace(hour=7, minute=0, tzinfo=timezone.utc)
        add("living_room_ac", DeviceType.AC, "living_room", DeviceAction.ON, morning,
            triggered_by="father")

    return events
