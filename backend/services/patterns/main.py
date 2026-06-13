"""Pattern Recognition Microservice — Time-based device pattern learning."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Query, Depends, status
from services.auth import get_current_user
from services.patterns.models import Event, EventCreate, HouseholdState, ContextObject
from services.patterns import services
from services.patterns.context_builder import build_context
from services.patterns.dynamo import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        create_tables()
    except Exception:
        pass
    yield


app = FastAPI(title="MoodSense — Pattern Recognition Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"service": "pattern-recognition", "status": "ok"}


@app.post("/events", response_model=Event, status_code=status.HTTP_201_CREATED)
def ingest_event(payload: EventCreate, user=Depends(get_current_user)):
    event = services.store_event(payload)
    services.apply_event(event)
    return event


@app.get("/events")
def list_events(
    household_id: str = Query(...),
    since: datetime | None = Query(None),
    limit: int | None = Query(None, ge=1, le=1000),
    user=Depends(get_current_user),
):
    if since and since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return services.get_events(household_id, since=since, limit=limit)


@app.get("/state/{household_id}", response_model=HouseholdState)
def get_state(household_id: str, user=Depends(get_current_user)):
    return services.get_state(household_id)


@app.post("/patterns/{household_id}/extract")
def extract_patterns(household_id: str, user=Depends(get_current_user)):
    patterns = services.extract_and_store(household_id)
    return {
        "household_id": household_id,
        "extracted": len(patterns),
        "patterns": [p.model_dump(mode="json") for p in patterns],
    }


@app.get("/patterns/{household_id}")
def list_patterns(household_id: str, user=Depends(get_current_user)):
    patterns = services.get_patterns(household_id)
    return {
        "household_id": household_id,
        "count": len(patterns),
        "patterns": [p.model_dump(mode="json") for p in patterns],
    }


@app.get("/context/{household_id}", response_model=ContextObject)
def get_context(household_id: str, user=Depends(get_current_user)):
    state = services.get_state(household_id)
    patterns = services.get_patterns(household_id)
    recent = services.get_recent_events(household_id, 1)
    return build_context(state, patterns, recent)


@app.post("/seed/{household_id}")
def seed_data(household_id: str, user=Depends(get_current_user)):
    """
    Seed 30 days of realistic household device events for demo purposes.
    Simulates a family routine: son leaves for college, parents go to work,
    devices turn on/off at consistent times with natural variance.
    """
    import random
    from datetime import timedelta

    random.seed(42)
    now = datetime.now(timezone.utc)
    events_created = 0

    # Define the household routine
    routines = [
        # Morning: son leaves for college (08:30-09:00)
        {"device_id": "son_room_light", "device_type": "light", "room": "son_room", "action": "ON", "triggered_by": "son", "hour": 7, "minute": 0, "variance": 15},
        {"device_id": "son_room_fan", "device_type": "fan", "room": "son_room", "action": "ON", "triggered_by": "son", "hour": 7, "minute": 5, "variance": 10},
        {"device_id": "son_room_light", "device_type": "light", "room": "son_room", "action": "OFF", "triggered_by": "son", "hour": 8, "minute": 30, "variance": 15},
        {"device_id": "son_room_fan", "device_type": "fan", "room": "son_room", "action": "OFF", "triggered_by": "son", "hour": 8, "minute": 35, "variance": 10},
        {"device_id": "main_door", "device_type": "door", "room": "entrance", "action": "OPEN", "triggered_by": "son", "hour": 8, "minute": 40, "variance": 10},
        {"device_id": "main_door", "device_type": "door", "room": "entrance", "action": "CLOSE", "triggered_by": "son", "hour": 8, "minute": 41, "variance": 5},
        # Son presence leaves
        {"device_id": "son_presence", "device_type": "presence", "room": "house", "action": "LEAVE", "triggered_by": "son", "hour": 8, "minute": 42, "variance": 10},

        # Parents morning (09:00-09:30)
        {"device_id": "living_room_light", "device_type": "light", "room": "living_room", "action": "ON", "triggered_by": "mother", "hour": 6, "minute": 30, "variance": 20},
        {"device_id": "kitchen_light", "device_type": "light", "room": "kitchen", "action": "ON", "triggered_by": "mother", "hour": 6, "minute": 35, "variance": 15},
        {"device_id": "kitchen_light", "device_type": "light", "room": "kitchen", "action": "OFF", "triggered_by": "mother", "hour": 8, "minute": 0, "variance": 20},

        # Father leaves for work
        {"device_id": "father_presence", "device_type": "presence", "room": "house", "action": "LEAVE", "triggered_by": "father", "hour": 9, "minute": 15, "variance": 15},

        # Water motor (runs ~15 min daily)
        {"device_id": "water_motor", "device_type": "motor", "room": "utility", "action": "ON", "triggered_by": "system", "hour": 6, "minute": 0, "variance": 10},
        {"device_id": "water_motor", "device_type": "motor", "room": "utility", "action": "OFF", "triggered_by": "system", "hour": 6, "minute": 15, "variance": 3},

        # Evening: everyone returns
        {"device_id": "son_presence", "device_type": "presence", "room": "house", "action": "ARRIVE", "triggered_by": "son", "hour": 17, "minute": 0, "variance": 30},
        {"device_id": "father_presence", "device_type": "presence", "room": "house", "action": "ARRIVE", "triggered_by": "father", "hour": 18, "minute": 30, "variance": 20},
        {"device_id": "son_room_fan", "device_type": "fan", "room": "son_room", "action": "ON", "triggered_by": "son", "hour": 17, "minute": 10, "variance": 15},
        {"device_id": "son_room_light", "device_type": "light", "room": "son_room", "action": "ON", "triggered_by": "son", "hour": 17, "minute": 10, "variance": 15},
        {"device_id": "living_room_tv", "device_type": "tv", "room": "living_room", "action": "ON", "triggered_by": "father", "hour": 19, "minute": 0, "variance": 20},
        {"device_id": "living_room_light", "device_type": "light", "room": "living_room", "action": "ON", "triggered_by": "system", "hour": 18, "minute": 45, "variance": 15},

        # Night: everything off
        {"device_id": "living_room_tv", "device_type": "tv", "room": "living_room", "action": "OFF", "triggered_by": "father", "hour": 22, "minute": 30, "variance": 20},
        {"device_id": "living_room_light", "device_type": "light", "room": "living_room", "action": "OFF", "triggered_by": "system", "hour": 22, "minute": 45, "variance": 15},
        {"device_id": "son_room_fan", "device_type": "fan", "room": "son_room", "action": "OFF", "triggered_by": "son", "hour": 23, "minute": 0, "variance": 20},
        {"device_id": "son_room_light", "device_type": "light", "room": "son_room", "action": "OFF", "triggered_by": "son", "hour": 23, "minute": 0, "variance": 15},
    ]

    # Generate 30 days of events
    for day_offset in range(30):
        day = now - timedelta(days=30 - day_offset)

        # Skip some events randomly (weekends, sick days) for realism
        skip_son_routine = random.random() < 0.1  # 10% chance son doesn't go

        for routine in routines:
            # Skip son's departure on some days
            if skip_son_routine and routine["triggered_by"] == "son" and routine["hour"] < 12:
                continue

            # Add time variance
            variance_min = random.randint(-routine["variance"], routine["variance"])
            event_time = day.replace(
                hour=routine["hour"],
                minute=max(0, min(59, routine["minute"] + variance_min)),
                second=random.randint(0, 59),
                microsecond=0,
            )

            payload = EventCreate(
                household_id=household_id,
                device_id=routine["device_id"],
                device_type=routine["device_type"],
                room=routine["room"],
                action=routine["action"],
                triggered_by=routine["triggered_by"],
                timestamp=event_time,
            )
            services.store_event(payload)
            events_created += 1

    # Now simulate current state: son left but fan is still on (anomaly for demo)
    current_state_events = [
        EventCreate(household_id=household_id, device_id="son_presence", device_type="presence", room="house", action="LEAVE", triggered_by="son", timestamp=now - timedelta(hours=3)),
        EventCreate(household_id=household_id, device_id="son_room_fan", device_type="fan", room="son_room", action="ON", triggered_by="son", timestamp=now - timedelta(hours=4)),
        EventCreate(household_id=household_id, device_id="father_presence", device_type="presence", room="house", action="ARRIVE", triggered_by="father", timestamp=now - timedelta(hours=1)),
    ]
    for payload in current_state_events:
        event = services.store_event(payload)
        services.apply_event(event)
        events_created += 1

    # Extract patterns from the seeded data
    patterns = services.extract_and_store(household_id)

    return {
        "household_id": household_id,
        "events_created": events_created,
        "patterns_extracted": len(patterns),
        "message": f"Seeded {events_created} events over 30 days and extracted {len(patterns)} patterns. Son's fan is left ON to trigger an anomaly.",
    }
