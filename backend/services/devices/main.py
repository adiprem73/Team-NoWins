"""Device Control Microservice — Maps mood state to smart home environment adjustments."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from pydantic import BaseModel

from services.devices.controller import (
    device_controller,
    MoodState,
    CognitiveLoad,
    EnvironmentState,
    MOOD_PRESETS,
)

app = FastAPI(title="MoodSense — Device Control Service")


class EnvironmentRequest(BaseModel):
    mood: MoodState
    cognitive_load: CognitiveLoad
    user_id: str = "default"
    room_id: str = "living-room"


class DeviceCommandResponse(BaseModel):
    environment: EnvironmentState
    commands_sent: list[dict] = []
    room_id: str


@app.get("/health")
def health():
    return {"service": "device-control", "status": "ok"}


@app.post("/adjust", response_model=DeviceCommandResponse)
async def adjust_environment(request: EnvironmentRequest):
    """Compute and apply environment adjustments based on mood + cognitive load."""
    env = device_controller.compute_environment(
        mood=request.mood,
        cognitive_load=request.cognitive_load,
    )
    commands = _build_device_commands(env, request.room_id)
    return DeviceCommandResponse(
        environment=env,
        commands_sent=commands,
        room_id=request.room_id,
    )


@app.get("/presets")
async def get_presets():
    """Return all available mood presets for reference."""
    return {mood.value: preset for mood, preset in MOOD_PRESETS.items()}


@app.get("/state/{room_id}")
async def get_room_state(room_id: str):
    """Get current environment state for a room (placeholder for IoT query)."""
    return {
        "room_id": room_id,
        "status": "connected",
        "last_adjustment": None,
        "devices": {
            "lights": {"online": True, "type": "smart_bulb"},
            "speaker": {"online": True, "type": "echo"},
            "thermostat": {"online": False, "type": "smart_thermostat"},
        },
    }


def _build_device_commands(env: EnvironmentState, room_id: str) -> list[dict]:
    """Translate environment state into IoT device commands."""
    commands = []
    commands.append({
        "device_type": "light",
        "room_id": room_id,
        "action": "set",
        "params": {
            "color": env.light_color,
            "brightness": env.light_brightness,
            "temperature_k": env.light_temperature_k,
        },
    })
    if env.music_genre:
        commands.append({
            "device_type": "speaker",
            "room_id": room_id,
            "action": "play",
            "params": {
                "genre": env.music_genre,
                "volume": env.music_volume,
            },
        })
    commands.append({
        "device_type": "notification_hub",
        "room_id": room_id,
        "action": "set_mode",
        "params": {
            "mode": env.notification_mode,
        },
    })
    return commands
