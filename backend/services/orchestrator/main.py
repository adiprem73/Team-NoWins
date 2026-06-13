"""Orchestrator Microservice — The brain that connects all services via HTTP."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import httpx

from config import settings
from services.orchestrator.action_engine import action_engine

logger = logging.getLogger(__name__)
app = FastAPI(title="MoodSense — Orchestrator Service")


class OrchestratorRequest(BaseModel):
    user_id: str = "default"
    room_id: str = "living-room"
    household_id: str = "H001"
    speech_text: Optional[str] = None
    audio_base64: Optional[str] = None
    audio_format: str = "wav"
    behavior_signals: list[dict] = []
    time_of_day: Optional[str] = None  # Passed from frontend (local timezone)


class OrchestratorResponse(BaseModel):
    mood_assessment: str
    mood: str
    cognitive_load: str
    confidence: float
    actions: dict
    alexa_response: str
    reasoning: str
    commands: list[dict]
    voice_analyzed: bool
    behavior_analyzed: bool
    patterns_used: bool
    llm_powered: bool


@app.get("/health")
def health():
    return {"service": "orchestrator", "status": "ok"}


@app.post("/process", response_model=OrchestratorResponse)
async def process_interaction(request: OrchestratorRequest):
    """
    The unified pipeline. Calls each microservice over HTTP and feeds
    all context to the Action Engine LLM.
    """
    voice_analyzed = False
    behavior_analyzed = False
    patterns_used = False

    mood_result = None
    behavior_result = None
    pattern_context = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Step 1: Analyze mood via Mood Service
        if request.audio_base64:
            try:
                resp = await client.post(
                    f"{settings.mood_service_url}/analyze/audio",
                    json={
                        "audio_base64": request.audio_base64,
                        "audio_format": request.audio_format,
                    },
                )
                if resp.status_code == 200:
                    mood_result = resp.json()
                    voice_analyzed = True
            except Exception as e:
                logger.error(f"Mood service error: {e}")
        elif request.speech_text:
            try:
                resp = await client.post(
                    f"{settings.mood_service_url}/analyze/text",
                    json={"text": request.speech_text},
                )
                if resp.status_code == 200:
                    mood_result = resp.json()
                    voice_analyzed = True
            except Exception as e:
                logger.error(f"Mood service error: {e}")

        # Step 2: Analyze behavior via Behavior Service
        if request.behavior_signals:
            try:
                resp = await client.post(
                    f"{settings.behavior_service_url}/analyze",
                    json={
                        "user_id": request.user_id,
                        "device_id": "alexa-main",
                        "signals": request.behavior_signals,
                    },
                )
                if resp.status_code == 200:
                    behavior_result = resp.json()
                    behavior_analyzed = True
            except Exception as e:
                logger.error(f"Behavior service error: {e}")

        # Step 3: Get pattern context from Pattern Service
        try:
            resp = await client.get(
                f"{settings.patterns_service_url}/context/{request.household_id}"
            )
            if resp.status_code == 200:
                pattern_context = resp.json()
                patterns_used = True
        except Exception as e:
            logger.error(f"Pattern service error: {e}")

    # Step 4: Send ALL context to Action Engine (LLM)
    from services.mood.models import MoodState
    from services.behavior.models import BehaviorAnalysisResult, CognitiveLoad as BehaviorCogLoad

    detected_mood = MoodState(mood_result["mood"]) if mood_result else None
    mood_confidence = mood_result.get("confidence", 0.0) if mood_result else 0.0
    speech_features = mood_result.get("speech_features") if mood_result else None

    beh_result = None
    if behavior_result:
        beh_result = BehaviorAnalysisResult(**behavior_result)

    # Time of day — prefer client-provided (local timezone)
    if request.time_of_day:
        time_of_day = request.time_of_day
    else:
        hour = datetime.now().hour
        time_of_day = (
            "morning" if hour < 12
            else "afternoon" if hour < 17
            else "evening" if hour < 21
            else "night"
        )

    action_result = await action_engine.decide_actions(
        mood=detected_mood,
        mood_confidence=mood_confidence,
        speech_text=request.speech_text,
        speech_features=speech_features,
        behavior_result=beh_result,
        pattern_context=pattern_context,
        room_id=request.room_id,
        time_of_day=time_of_day,
    )

    actions = action_result.get("actions", {})

    # Use the LLM's assessed mood and cognitive load (it sees the full picture)
    final_mood = action_result.get("detected_mood", detected_mood.value if detected_mood else "neutral")
    final_load = action_result.get("cognitive_load",
        behavior_result.get("cognitive_load", "moderate") if behavior_result
        else mood_result.get("cognitive_load", "moderate") if mood_result
        else "moderate"
    )

    return OrchestratorResponse(
        mood_assessment=action_result.get("mood_assessment", ""),
        mood=final_mood,
        cognitive_load=final_load,
        confidence=action_result.get("confidence", mood_confidence),
        actions=actions,
        alexa_response=action_result.get("alexa_response", ""),
        reasoning=action_result.get("reasoning", ""),
        commands=_build_commands(actions, request.room_id),
        voice_analyzed=voice_analyzed,
        behavior_analyzed=behavior_analyzed,
        patterns_used=patterns_used,
        llm_powered="fallback" not in action_result.get("reasoning", "").lower(),
    )


# ─── WebSocket for real-time processing ─────────────────────────────────────

@app.websocket("/live")
async def live_processing(websocket: WebSocket):
    """Real-time WebSocket that continuously processes signals."""
    await websocket.accept()
    last_mood = None
    last_mood_confidence = 0.0
    last_speech_features = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "voice_text":
                text = data["payload"]["text"]
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post(
                            f"{settings.mood_service_url}/analyze/text",
                            json={"text": text},
                        )
                        if resp.status_code == 200:
                            mood_result = resp.json()
                            from services.mood.models import MoodState
                            last_mood = MoodState(mood_result.get("mood", "neutral"))
                            last_mood_confidence = mood_result.get("confidence", 0.5)
                            last_speech_features = mood_result.get("speech_features")

                            action_result = await action_engine.decide_actions(
                                mood=last_mood,
                                mood_confidence=last_mood_confidence,
                                speech_text=text,
                                speech_features=last_speech_features,
                            )

                            await websocket.send_json({
                                "type": "action_update",
                                "source": "voice",
                                "mood": last_mood.value,
                                "cognitive_load": mood_result.get("cognitive_load", "moderate"),
                                "confidence": last_mood_confidence,
                                "actions": action_result.get("actions", {}),
                                "alexa_response": action_result.get("alexa_response", ""),
                                "reasoning": action_result.get("reasoning", ""),
                                "llm_powered": True,
                            })
                except Exception as e:
                    logger.error(f"WS voice processing failed: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})

            elif msg_type == "behavior_batch":
                signals = data["payload"]["signals"]
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post(
                            f"{settings.behavior_service_url}/analyze",
                            json={
                                "user_id": "default",
                                "device_id": "alexa-main",
                                "signals": signals,
                            },
                        )
                        if resp.status_code == 200:
                            behavior_result = resp.json()
                            cog_load = behavior_result.get("cognitive_load", "moderate")

                            if cog_load in ("high", "overloaded"):
                                from services.behavior.models import BehaviorAnalysisResult
                                beh = BehaviorAnalysisResult(**behavior_result)
                                action_result = await action_engine.decide_actions(
                                    mood=last_mood,
                                    mood_confidence=last_mood_confidence,
                                    behavior_result=beh,
                                )
                                await websocket.send_json({
                                    "type": "action_update",
                                    "source": "behavior",
                                    "mood": last_mood.value if last_mood else "neutral",
                                    "cognitive_load": cog_load,
                                    "agitation_level": behavior_result.get("agitation_level", 0),
                                    "patterns": behavior_result.get("patterns_detected", []),
                                    "actions": action_result.get("actions", {}),
                                    "alexa_response": action_result.get("alexa_response", ""),
                                    "reasoning": action_result.get("reasoning", ""),
                                    "llm_powered": True,
                                })
                            else:
                                await websocket.send_json({
                                    "type": "behavior_update",
                                    "cognitive_load": cog_load,
                                    "agitation_level": behavior_result.get("agitation_level", 0),
                                    "patterns": behavior_result.get("patterns_detected", []),
                                    "llm_powered": False,
                                })
                except Exception as e:
                    logger.error(f"WS behavior processing failed: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_commands(actions: dict, room_id: str) -> list[dict]:
    """Convert LLM action decisions into IoT device commands."""
    commands = []
    if any(k.startswith("light") for k in actions):
        commands.append({
            "device": "light",
            "room": room_id,
            "action": "set",
            "color": actions.get("light_color", "#FFFFFF"),
            "brightness": actions.get("light_brightness", 65),
            "temperature_k": actions.get("light_temperature_k", 4000),
        })
    if actions.get("music_genre"):
        commands.append({
            "device": "speaker",
            "room": room_id,
            "action": "play",
            "genre": actions["music_genre"],
            "volume": actions.get("music_volume", 30),
        })
    if "notification_mode" in actions:
        commands.append({
            "device": "notification_hub",
            "room": room_id,
            "action": "set_mode",
            "mode": actions["notification_mode"],
        })
    return commands
