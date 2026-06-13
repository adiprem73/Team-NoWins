"""
Smart device controller that maps mood/cognitive state to environment adjustments.

Controls:
- Lights (color, brightness, temperature)
- Music (genre, volume)
- Notification filtering
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─── Local Models ────────────────────────────────────────────────────────────

class MoodState(str, Enum):
    CALM = "calm"
    HAPPY = "happy"
    STRESSED = "stressed"
    ANXIOUS = "anxious"
    FRUSTRATED = "frustrated"
    SAD = "sad"
    ENERGETIC = "energetic"
    TIRED = "tired"
    NEUTRAL = "neutral"


class CognitiveLoad(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    OVERLOADED = "overloaded"


class EnvironmentState(BaseModel):
    mood: MoodState
    cognitive_load: CognitiveLoad
    light_color: str = "#FFFFFF"
    light_brightness: int = Field(ge=0, le=100, default=70)
    light_temperature_k: int = Field(ge=2000, le=6500, default=4000)
    music_genre: Optional[str] = None
    music_volume: int = Field(ge=0, le=100, default=30)
    notification_mode: str = "normal"
    reasoning: str = ""


# ─── Environment Presets ─────────────────────────────────────────────────────

MOOD_PRESETS: dict[MoodState, dict] = {
    MoodState.STRESSED: {
        "light_color": "#4A90D9",
        "light_brightness": 40,
        "light_temperature_k": 2700,
        "music_genre": "ambient",
        "music_volume": 20,
        "notification_mode": "reduced",
        "reasoning": "Dim warm blue light with soft ambient music to reduce stress",
    },
    MoodState.ANXIOUS: {
        "light_color": "#7B68EE",
        "light_brightness": 35,
        "light_temperature_k": 2500,
        "music_genre": "nature_sounds",
        "music_volume": 25,
        "notification_mode": "dnd",
        "reasoning": "Lavender tones with nature sounds to ease anxiety",
    },
    MoodState.FRUSTRATED: {
        "light_color": "#48D1CC",
        "light_brightness": 45,
        "light_temperature_k": 3000,
        "music_genre": "lo-fi",
        "music_volume": 30,
        "notification_mode": "reduced",
        "reasoning": "Cool teal with lo-fi beats to diffuse frustration",
    },
    MoodState.SAD: {
        "light_color": "#FFD700",
        "light_brightness": 55,
        "light_temperature_k": 3500,
        "music_genre": "uplifting",
        "music_volume": 35,
        "notification_mode": "normal",
        "reasoning": "Warm golden light with uplifting music to improve mood",
    },
    MoodState.TIRED: {
        "light_color": "#FF8C00",
        "light_brightness": 30,
        "light_temperature_k": 2200,
        "music_genre": "sleep",
        "music_volume": 15,
        "notification_mode": "dnd",
        "reasoning": "Very warm dim light for rest, sleep-conducive sounds",
    },
    MoodState.HAPPY: {
        "light_color": "#FFFFFF",
        "light_brightness": 75,
        "light_temperature_k": 5000,
        "music_genre": "upbeat",
        "music_volume": 45,
        "notification_mode": "normal",
        "reasoning": "Bright neutral light to maintain positive energy",
    },
    MoodState.ENERGETIC: {
        "light_color": "#00FF7F",
        "light_brightness": 80,
        "light_temperature_k": 5500,
        "music_genre": "electronic",
        "music_volume": 50,
        "notification_mode": "normal",
        "reasoning": "Energetic green with upbeat electronic music",
    },
    MoodState.CALM: {
        "light_color": "#E6E6FA",
        "light_brightness": 50,
        "light_temperature_k": 3500,
        "music_genre": "classical",
        "music_volume": 25,
        "notification_mode": "normal",
        "reasoning": "Balanced light with soft classical to maintain calm",
    },
    MoodState.NEUTRAL: {
        "light_color": "#FFFFFF",
        "light_brightness": 65,
        "light_temperature_k": 4000,
        "music_genre": None,
        "music_volume": 0,
        "notification_mode": "normal",
        "reasoning": "Standard neutral environment",
    },
}

# Cognitive load overrides
COGNITIVE_OVERRIDES: dict[CognitiveLoad, dict] = {
    CognitiveLoad.OVERLOADED: {
        "light_brightness_delta": -20,
        "music_volume_delta": -15,
        "notification_mode": "dnd",
        "reasoning_suffix": " | Cognitive overload detected — reducing stimuli",
    },
    CognitiveLoad.HIGH: {
        "light_brightness_delta": -10,
        "music_volume_delta": -10,
        "notification_mode": "reduced",
        "reasoning_suffix": " | High cognitive load — minimizing distractions",
    },
    CognitiveLoad.MODERATE: {
        "light_brightness_delta": 0,
        "music_volume_delta": 0,
        "notification_mode": None,
        "reasoning_suffix": "",
    },
    CognitiveLoad.LOW: {
        "light_brightness_delta": 5,
        "music_volume_delta": 5,
        "notification_mode": None,
        "reasoning_suffix": "",
    },
}


class DeviceController:
    """Maps detected mood + cognitive load to smart home device commands."""

    def compute_environment(
        self, mood: MoodState, cognitive_load: CognitiveLoad
    ) -> EnvironmentState:
        """Determine optimal environment settings for detected state."""
        preset = MOOD_PRESETS.get(mood, MOOD_PRESETS[MoodState.NEUTRAL])
        override = COGNITIVE_OVERRIDES.get(
            cognitive_load, COGNITIVE_OVERRIDES[CognitiveLoad.MODERATE]
        )

        brightness = max(
            10,
            min(100, preset["light_brightness"] + override["light_brightness_delta"]),
        )
        volume = max(
            0,
            min(100, preset["music_volume"] + override["music_volume_delta"]),
        )
        notification_mode = override["notification_mode"] or preset["notification_mode"]
        reasoning = preset["reasoning"] + override["reasoning_suffix"]

        return EnvironmentState(
            mood=mood,
            cognitive_load=cognitive_load,
            light_color=preset["light_color"],
            light_brightness=brightness,
            light_temperature_k=preset["light_temperature_k"],
            music_genre=preset["music_genre"],
            music_volume=volume,
            notification_mode=notification_mode,
            reasoning=reasoning,
        )


# Singleton
device_controller = DeviceController()
