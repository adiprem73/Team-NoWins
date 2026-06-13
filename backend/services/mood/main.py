"""Mood Analysis Microservice — Speech-based emotion detection using Voxtral on Bedrock."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import logging
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from services.mood.bedrock_client import bedrock_analyzer
from services.mood.models import MoodAnalysisResult, MoodState, CognitiveLoad

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MoodSense — Mood Analysis Service")


class TextMoodRequest(BaseModel):
    text: str
    user_id: str = "default"


class AudioMoodRequest(BaseModel):
    audio_base64: str
    audio_format: str = "wav"
    user_id: str = "default"


@app.get("/health")
def health():
    return {"service": "mood-analysis", "status": "ok"}


@app.post("/analyze/audio", response_model=MoodAnalysisResult)
async def analyze_audio_mood(request: AudioMoodRequest):
    try:
        logger.info(f"Analyzing audio: format={request.audio_format}, size={len(request.audio_base64)} chars")
        result = await bedrock_analyzer.analyze_speech_mood(
            audio_base64=request.audio_base64,
            audio_format=request.audio_format,
        )
        return MoodAnalysisResult(
            mood=MoodState(result.get("mood", "neutral")),
            confidence=result.get("confidence", 0.5),
            cognitive_load=CognitiveLoad(result.get("cognitive_load", "moderate")),
            speech_features=result.get("speech_features", {}),
            reasoning=result.get("reasoning", ""),
        )
    except Exception as e:
        logger.error(f"Audio analysis failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/analyze/text", response_model=MoodAnalysisResult)
async def analyze_text_mood(request: TextMoodRequest):
    try:
        result = await bedrock_analyzer.analyze_text_mood(request.text)
        return MoodAnalysisResult(
            mood=MoodState(result.get("mood", "neutral")),
            confidence=result.get("confidence", 0.5),
            cognitive_load=CognitiveLoad(result.get("cognitive_load", "moderate")),
            speech_features=result.get("speech_features", {}),
            reasoning=result.get("reasoning", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/upload")
async def analyze_uploaded_audio(file: UploadFile = File(...)):
    content = await file.read()
    audio_base64 = base64.b64encode(content).decode("utf-8")
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "wav"
    format_map = {"mp3": "mpeg", "ogg": "ogg", "wav": "wav"}
    audio_format = format_map.get(ext, "wav")
    try:
        result = await bedrock_analyzer.analyze_speech_mood(
            audio_base64=audio_base64, audio_format=audio_format
        )
        return MoodAnalysisResult(
            mood=MoodState(result.get("mood", "neutral")),
            confidence=result.get("confidence", 0.5),
            cognitive_load=CognitiveLoad(result.get("cognitive_load", "moderate")),
            speech_features=result.get("speech_features", {}),
            reasoning=result.get("reasoning", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
