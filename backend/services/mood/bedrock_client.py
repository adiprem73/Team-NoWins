"""
Mood Analysis Client — All via Groq (free tier):
  1. Whisper Large V3 Turbo: Audio → Text
  2. LLaMA 3.3 70B: Text → Mood analysis

Groq free tier: 30 RPM, 14,400 requests/day for LLaMA 3.3 70B.
"""
import json
import logging
import base64
import tempfile
import os

import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import settings

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


class GroqMoodAnalyzer:
    """
    All-in-one Groq client:
    1. Whisper (speech-to-text)
    2. LLaMA 3.3 70B (mood analysis from text)
    """

    def __init__(self):
        self.api_key = settings.groq_api_key
        self.llm_model = settings.groq_llm_model
        logger.info(
            f"Mood analyzer initialized: model={self.llm_model}, "
            f"api_key={'configured' if self.api_key else 'NOT SET'}"
        )

    # ─── Step 1: Speech-to-Text via Groq Whisper ────────────────────────────

    async def transcribe_audio(self, audio_base64: str, audio_format: str = "webm") -> str:
        """Transcribe audio using Groq Whisper."""
        if not self.api_key:
            raise Exception("GROQ_API_KEY not configured.")

        audio_bytes = base64.b64decode(audio_base64)
        suffix = f".{audio_format}"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(tmp_path, "rb") as audio_file:
                    response = await client.post(
                        GROQ_WHISPER_URL,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": (f"audio{suffix}", audio_file, f"audio/{audio_format}")},
                        data={"model": "whisper-large-v3-turbo", "response_format": "json"},
                    )

                if response.status_code != 200:
                    logger.error(f"Groq Whisper error: {response.status_code} - {response.text}")
                    raise Exception(f"Whisper failed: {response.text}")

                transcript = response.json().get("text", "")
                logger.info(f"Transcription: '{transcript[:80]}'")
                return transcript
        finally:
            os.unlink(tmp_path)

    # ─── Step 2: Mood Analysis via Groq LLM ─────────────────────────────────

    async def analyze_text_mood(self, text: str) -> dict:
        """Analyze mood from text using LLaMA on Groq."""
        if not self.api_key:
            raise Exception("GROQ_API_KEY not configured.")

        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": MOOD_ANALYSIS_PROMPT},
                {"role": "user", "content": f'User speech: "{text}"'},
            ],
            "temperature": 0.3,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"Groq LLM error: {response.status_code} - {response.text}")
                raise Exception(f"Groq LLM failed: {response.text}")

            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"Mood analysis complete")
            return json.loads(content)

    # ─── Combined: Audio → Transcript → Mood ────────────────────────────────

    async def analyze_speech_mood(self, audio_base64: str, audio_format: str = "webm") -> dict:
        """Full pipeline: Audio → Whisper → LLaMA → Mood."""
        transcript = await self.transcribe_audio(audio_base64, audio_format)

        if not transcript.strip():
            return {
                "mood": "neutral",
                "confidence": 0.3,
                "cognitive_load": "moderate",
                "speech_features": {"transcript": ""},
                "reasoning": "No speech detected in audio",
            }

        result = await self.analyze_text_mood(transcript)
        if "speech_features" not in result:
            result["speech_features"] = {}
        result["speech_features"]["transcript"] = transcript
        return result


# ─── Prompt ──────────────────────────────────────────────────────────────────

MOOD_ANALYSIS_PROMPT = """You are a mood and cognitive load analyzer for a smart home AI assistant.

Analyze the user's speech for emotional state and cognitive load. Consider word choice, sentence structure, expressed emotions, and urgency.

Respond with JSON only:
{
  "mood": "one of: calm, happy, stressed, anxious, frustrated, sad, energetic, tired, neutral",
  "confidence": 0.0-1.0,
  "cognitive_load": "one of: low, moderate, high, overloaded",
  "speech_features": {
    "sentiment": "positive/negative/neutral",
    "complexity": "simple/moderate/complex",
    "urgency": "low/medium/high"
  },
  "reasoning": "Brief explanation"
}"""


# Singleton (kept as bedrock_analyzer for compatibility)
bedrock_analyzer = GroqMoodAnalyzer()
