"""Behavior Analysis Microservice."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from pydantic import BaseModel
from services.behavior.engine import behavior_engine
from services.behavior.models import BehaviorSignal, BehaviorAnalysisResult

app = FastAPI(title="MoodSense — Behavior Analysis Service")


class BehaviorBatchRequest(BaseModel):
    user_id: str = "default"
    device_id: str = "alexa-main"
    signals: list[BehaviorSignal]


@app.get("/health")
def health():
    return {"service": "behavior-analysis", "status": "ok"}


@app.post("/analyze", response_model=BehaviorAnalysisResult)
async def analyze_behavior(request: BehaviorBatchRequest):
    return behavior_engine.analyze(request.signals)


@app.post("/signal", response_model=BehaviorAnalysisResult)
async def report_single_signal(signal: BehaviorSignal):
    return behavior_engine.analyze([signal])
