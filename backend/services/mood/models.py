"""Data models for mood analysis service."""
from enum import Enum
from pydantic import BaseModel, Field


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


class MoodAnalysisResult(BaseModel):
    mood: MoodState
    confidence: float = Field(ge=0.0, le=1.0)
    cognitive_load: CognitiveLoad
    speech_features: dict = Field(default_factory=dict)
    reasoning: str = ""
