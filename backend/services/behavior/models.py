"""Data models for behavior tracking service."""
from enum import Enum
from pydantic import BaseModel, Field


class CognitiveLoad(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    OVERLOADED = "overloaded"


class BehaviorSignal(BaseModel):
    signal_type: str
    intensity: float = Field(ge=0.0, le=1.0)
    frequency: float = Field(ge=0.0)
    duration_ms: int = Field(ge=0)
    timestamp: float


class BehaviorAnalysisResult(BaseModel):
    cognitive_load: CognitiveLoad
    agitation_level: float = Field(ge=0.0, le=1.0)
    patterns_detected: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
