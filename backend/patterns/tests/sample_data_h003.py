"""Third synthetic scenario (household H003) — full Indian-context intelligence.

This household exercises EVERY Indian-context feature on the brief, each modelled
as a deterministic, learnable **event stream** the existing extractors already
understand — NO new algorithm is required. Ordinary appliances (fans, lights,
doors) are mixed in so the engine learns the whole home together.

The point of this file: show, per feature, *what kind of event* models it and
*how the engine flags it*. Every feature below resolves to one of the three
existing pattern kinds (TimePattern / SequencePattern / DurationPattern) and one
of the existing anomaly detectors.

╔══════════════════════════════════════════════════════════════════════════════
║  FEATURE → EVENT MODEL → LEARNED PATTERN → ANOMALY IT ENABLES
╠══════════════════════════════════════════════════════════════════════════════
║  1. Water motor / overhead tank
║       water_motor · MOTOR · ON→OFF ~15 min, ~09:30   → DurationPattern
║       → DURATION_EXCEEDED when run > 2× usual ("tank may already be full").
║  2. Elderly parent care
║       grandpa_activity · ACTIVITY · ACTIVE ~06:45     → TimePattern(ACTIVE)
║       → INACTIVITY when the morning activity ping is absent.
║  3. Child tuition / school return
║       ananya_presence · PRESENCE · ARRIVE ~18:15      → TimePattern(ARRIVE)
║       → MISSED_ARRIVAL when she hasn't returned.
║  4. Morning pooja
║       pooja_lamp:ON → temple_bell:ON → bhajan_speaker:ON ~07:00
║                                                       → SequencePattern (+ a
║       pooja_lamp ON TimePattern) → MISSED_ROUTINE reminder if pooja not begun.
║  5. Domestic helper / caretaker
║       maid_presence · PRESENCE · ARRIVE ~09:00, LEAVE ~11:00 → TimePattern
║       → UNEXPECTED_ACTIVITY when an arrival lands far outside the window.
║  6. Elderly medicine adherence
║       grandma_medicine · MEDICINE · TAKEN ~21:00      → TimePattern(TAKEN)
║       → MISSED_MEDICINE when the dose isn't confirmed.
║  7. Power-cut / inverter
║       inverter · OTHER · ON→OFF ~45 min, ~20:00       → DurationPattern
║       → DURATION_EXCEEDED when it runs far longer ("inverter battery is low").
║  8. Rain / clothesline
║       terrace_clothesline · OTHER · OFF ~17:30 (clothes brought in daily)
║                                                       → TimePattern(OFF)
║       → DEVICE_LEFT_ON when clothes are still out well past the usual time.
║  9. Gas-stove monitoring
║       kitchen_gas_stove · OTHER · ON→OFF ~30 min, ~18:30 → DurationPattern
║       → DURATION_EXCEEDED when the stove is left running (unattended).
║ 10. Evening chai routine
║       chai_kettle:ON → kitchen_light:ON ~17:00        → SequencePattern (+ a
║       chai_kettle ON TimePattern) → MISSED_ROUTINE reminder ("time for chai").
║ 11. Daily delivery (milk / newspaper) coordination
║       milk_delivery · PRESENCE · ARRIVE ~06:00        → TimePattern(ARRIVE)
║       → MISSED_ARRIVAL when the daily delivery doesn't show.
║ 12. Household chore coordination (drinking-water can refill)
║       water_can_refill · OTHER · ON→OFF (momentary) ~20:30 → TimePattern(ON)
║       → MISSED_ROUTINE when today's chore hasn't been done (assign to whoever
║         is home via ``people_home`` at the orchestrator).
║
║  Plus ordinary appliances so the home is realistic:
║       son departure  : main_door:OPEN → son_room_fan:OFF → son_room_light:OFF
║       porch security : porch_light ON ~19:20, OFF ~22:30
╚══════════════════════════════════════════════════════════════════════════════

Times are spaced > MAX_GAP_MINUTES (10) apart except inside the three INTENDED
sequences (pooja, chai, son departure) so unrelated evening events never merge
into a spurious, repeating session signature.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from patterns.models.events import DeviceAction, DeviceType, EventCreate

HOUSEHOLD = "H003"
_rng = random.Random(13)  # deterministic, independent of H001/H002 RNGs


def _at(day: datetime, hour: int, minute: int, jitter: int = 0) -> datetime:
    minute += _rng.randint(-jitter, jitter) if jitter else 0
    base = day.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(minutes=minute)


def generate(
    days: int = 30,
    *,
    include_unexpected_entry: bool = True,
    include_motor_anomaly: bool = True,
    include_left_on: bool = True,
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

        # 11) Daily milk delivery ~06:00 (coordination / "did it arrive?").
        add("milk_delivery", DeviceType.PRESENCE, "entrance", DeviceAction.ARRIVE,
            _at(day, 6, 0, jitter=8), triggered_by="milkman")

        # 2) Elderly morning activity ~06:45 (grandpa moves around / wakes).
        add("grandpa_activity", DeviceType.ACTIVITY, "grandpa_room",
            DeviceAction.ACTIVE, _at(day, 6, 45, jitter=8), triggered_by="grandpa")

        # 4) Morning pooja burst ~07:00 (lamp → bell → bhajan within minutes);
        #    lamp switched off ~07:30 (well after the burst, so it is not part
        #    of the pooja session signature).
        p_on = _at(day, 7, 0, jitter=5)
        add("pooja_lamp", DeviceType.LIGHT, "pooja_room", DeviceAction.ON, p_on,
            triggered_by="mother")
        add("temple_bell", DeviceType.OTHER, "pooja_room", DeviceAction.ON,
            p_on + timedelta(minutes=1), triggered_by="mother")
        add("bhajan_speaker", DeviceType.OTHER, "pooja_room", DeviceAction.ON,
            p_on + timedelta(minutes=2), triggered_by="mother")
        add("pooja_lamp", DeviceType.LIGHT, "pooja_room", DeviceAction.OFF,
            p_on + timedelta(minutes=30 + _rng.randint(-3, 3)), triggered_by="mother")
        # Bell & bhajan are switched off when the pooja ends (~07:30) so they do
        # not linger as 'active' devices for the rest of the day.
        add("temple_bell", DeviceType.OTHER, "pooja_room", DeviceAction.OFF,
            p_on + timedelta(minutes=31 + _rng.randint(-3, 3)), triggered_by="mother")
        add("bhajan_speaker", DeviceType.OTHER, "pooja_room", DeviceAction.OFF,
            p_on + timedelta(minutes=32 + _rng.randint(-3, 3)), triggered_by="mother")

        # (ordinary) Son departure ~08:00 (door + fan + light). Tight, stable
        # spacing keeps the OPEN → fan OFF → light OFF order for the sequence.
        add("main_door", DeviceType.DOOR, "entrance", DeviceAction.OPEN,
            _at(day, 8, 0, jitter=2), triggered_by="son")
        add("son_room_fan", DeviceType.FAN, "son_room", DeviceAction.OFF,
            _at(day, 8, 4, jitter=1), triggered_by="son")
        add("son_room_light", DeviceType.LIGHT, "son_room", DeviceAction.OFF,
            _at(day, 8, 7, jitter=1), triggered_by="son")
        # Door is pulled shut a little after the departure burst (separate
        # session, so the 3-step departure sequence stays intact) so it does not
        # linger 'open' all day.
        add("main_door", DeviceType.DOOR, "entrance", DeviceAction.CLOSE,
            _at(day, 8, 20, jitter=3), triggered_by="son")

        # 5) Domestic helper arrives ~09:00, leaves ~11:00.
        add("maid_presence", DeviceType.PRESENCE, "entrance", DeviceAction.ARRIVE,
            _at(day, 9, 0, jitter=10), triggered_by="maid")
        add("maid_presence", DeviceType.PRESENCE, "entrance", DeviceAction.LEAVE,
            _at(day, 11, 0, jitter=10), triggered_by="maid")

        # 1) Overhead-tank water motor ~15 min run ~09:30.
        m_on = _at(day, 9, 30, jitter=8)
        add("water_motor", DeviceType.MOTOR, "utility", DeviceAction.ON, m_on)
        add("water_motor", DeviceType.MOTOR, "utility", DeviceAction.OFF,
            m_on + timedelta(minutes=15 + _rng.randint(-2, 2)))

        # 10) Evening chai routine ~17:00 (kettle → kitchen light). The kettle
        #     also has a short ~5 min duration; kitchen light is switched off
        #     late evening so it does not pair across days.
        c_on = _at(day, 17, 0, jitter=6)
        add("chai_kettle", DeviceType.OTHER, "kitchen", DeviceAction.ON, c_on,
            triggered_by="mother")
        add("kitchen_light", DeviceType.LIGHT, "kitchen", DeviceAction.ON,
            c_on + timedelta(minutes=2), triggered_by="mother")
        add("chai_kettle", DeviceType.OTHER, "kitchen", DeviceAction.OFF,
            c_on + timedelta(minutes=5 + _rng.randint(-1, 1)), triggered_by="mother")

        # 8) Clothesline: clothes are brought in (OFF) ~17:30 every day. Tracking
        #    only the bring-in gives a TimePattern(OFF) with NO duration pattern,
        #    so "clothes still out past 17:30" surfaces as DEVICE_LEFT_ON.
        add("terrace_clothesline", DeviceType.OTHER, "terrace", DeviceAction.OFF,
            _at(day, 17, 30, jitter=6), triggered_by="mother")

        # 3) Child returns from tuition ~18:15.
        add("ananya_presence", DeviceType.PRESENCE, "entrance", DeviceAction.ARRIVE,
            _at(day, 18, 15, jitter=8), triggered_by="ananya")

        # 9) Gas stove dinner cooking ~18:30, ~30 min → DurationPattern.
        g_on = _at(day, 18, 30, jitter=6)
        add("kitchen_gas_stove", DeviceType.OTHER, "kitchen", DeviceAction.ON, g_on,
            triggered_by="mother")
        add("kitchen_gas_stove", DeviceType.OTHER, "kitchen", DeviceAction.OFF,
            g_on + timedelta(minutes=30 + _rng.randint(-4, 4)), triggered_by="mother")

        # (ordinary) Evening security / porch light ON ~19:20, OFF ~22:30.
        add("porch_light", DeviceType.LIGHT, "porch", DeviceAction.ON,
            _at(day, 19, 20, jitter=5))

        # 7) Power-cut / inverter: evening outage ~20:00, runs ~45 min →
        #    DurationPattern. Running far longer ⇒ battery draining.
        i_on = _at(day, 20, 0, jitter=6)
        add("inverter", DeviceType.OTHER, "utility", DeviceAction.ON, i_on)
        add("inverter", DeviceType.OTHER, "utility", DeviceAction.OFF,
            i_on + timedelta(minutes=45 + _rng.randint(-5, 5)))

        # 12) Household chore — refill the 20 L drinking-water can ~20:30
        #     (momentary ON→OFF so it never lingers as an active device).
        w_on = _at(day, 20, 30, jitter=6)
        add("water_can_refill", DeviceType.OTHER, "kitchen", DeviceAction.ON, w_on,
            triggered_by="maid")
        add("water_can_refill", DeviceType.OTHER, "kitchen", DeviceAction.OFF,
            w_on + timedelta(minutes=1), triggered_by="maid")

        # 6) Elderly evening medicine ~21:00.
        add("grandma_medicine", DeviceType.MEDICINE, "grandma_room",
            DeviceAction.TAKEN, _at(day, 21, 0, jitter=8), triggered_by="grandma")

        # (ordinary) Porch light off / kitchen light off late evening ~22:30.
        add("porch_light", DeviceType.LIGHT, "porch", DeviceAction.OFF,
            _at(day, 22, 30, jitter=8))
        add("kitchen_light", DeviceType.LIGHT, "kitchen", DeviceAction.OFF,
            _at(day, 22, 35, jitter=8), triggered_by="mother")

    # ───────────── TODAY: inject concrete current-state anomalies ─────────────
    # (These power the LIVE /context/H003 endpoint. The demo script instead
    #  builds explicit per-feature states so every detector can be shown.)
    if include_unexpected_entry:
        # Helper "arrives" at 02:30 — far outside the usual ~09:00 window.
        add("maid_presence", DeviceType.PRESENCE, "entrance", DeviceAction.ARRIVE,
            today.replace(hour=2, minute=30, tzinfo=timezone.utc), triggered_by="maid")

    if include_motor_anomaly:
        # Water motor switched ON 40 min ago and never stopped (usual ~15 min) →
        # likely forgotten / overhead tank may be overflowing.
        forty_ago = datetime.now(timezone.utc) - timedelta(minutes=40)
        add("water_motor", DeviceType.MOTOR, "utility", DeviceAction.ON, forty_ago)

    if include_left_on:
        # Son switched the fan/light ON at 07:30 and left without turning them
        # off → they should be off by ~08:00 (learned departure OFF time).
        morning = today.replace(hour=7, minute=30, tzinfo=timezone.utc)
        add("son_room_fan", DeviceType.FAN, "son_room", DeviceAction.ON, morning,
            triggered_by="son")
        add("son_room_light", DeviceType.LIGHT, "son_room", DeviceAction.ON, morning,
            triggered_by="son")

    return events
