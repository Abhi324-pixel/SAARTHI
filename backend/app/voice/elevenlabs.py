"""ElevenLabs integration (server side): signed URL for the Agent, Text-to-Speech, Speech-to-Text.

The API key never leaves the server. The browser connects to the Agent with a short-lived signed URL.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ..config import settings

API = "https://api.elevenlabs.io"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
LANG_CODES = {"english": "en", "hindi": "hi", "hinglish": "hi"}
# only these models accept an explicit language_code
LANGUAGE_CODE_MODELS = ("eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_v3")


class VoiceUnavailable(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.elevenlabs_api_key:
        raise VoiceUnavailable("ELEVENLABS_API_KEY is not set")
    return {"xi-api-key": settings.elevenlabs_api_key}


def status() -> dict[str, Any]:
    return {
        "api_key": bool(settings.elevenlabs_api_key), "agent_id": bool(settings.elevenlabs_agent_id),
        "voice_id": bool(settings.elevenlabs_voice_id), "agent_public": settings.elevenlabs_agent_public,
        "tts_model": settings.elevenlabs_tts_model, "stt_model": settings.elevenlabs_stt_model,
        "agent_ready": bool(settings.elevenlabs_agent_id and (settings.elevenlabs_api_key or settings.elevenlabs_agent_public)),
        "tts_ready": bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id),
        "stt_ready": bool(settings.elevenlabs_api_key),
    }


def agent_connection() -> dict[str, Any]:
    """What the browser needs to start a conversation."""
    if not settings.elevenlabs_agent_id:
        raise VoiceUnavailable("ELEVENLABS_AGENT_ID is not set")
    if settings.elevenlabs_agent_public:
        return {"mode": "public", "agent_id": settings.elevenlabs_agent_id}
    r = httpx.get(f"{API}/v1/convai/conversation/get-signed-url", params={"agent_id": settings.elevenlabs_agent_id},
                  headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        raise VoiceUnavailable(f"could not get a signed URL ({r.status_code}): {r.text[:160]}")
    return {"mode": "signed", "signed_url": r.json()["signed_url"], "agent_id": settings.elevenlabs_agent_id}


def text_to_speech(text: str, language: str = "english") -> bytes:
    if not settings.elevenlabs_voice_id:
        raise VoiceUnavailable("ELEVENLABS_VOICE_ID is not set")
    body: dict[str, Any] = {"text": text[:1500], "model_id": settings.elevenlabs_tts_model}
    if settings.elevenlabs_tts_model in LANGUAGE_CODE_MODELS:
        body["language_code"] = LANG_CODES.get(language, "en")
    r = httpx.post(f"{API}/v1/text-to-speech/{settings.elevenlabs_voice_id}", params={"output_format": "mp3_44100_128"},
                   headers={**_headers(), "Content-Type": "application/json"}, json=body, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise VoiceUnavailable(f"text-to-speech failed ({r.status_code}): {r.text[:160]}")
    return r.content


def speech_to_text(audio: bytes, filename: str = "audio.webm", content_type: str = "audio/webm",
                   language: Optional[str] = None) -> dict[str, Any]:
    data: dict[str, Any] = {"model_id": settings.elevenlabs_stt_model, "tag_audio_events": "false", "diarize": "false"}
    if language:
        data["language_code"] = LANG_CODES.get(language, language)
    r = httpx.post(f"{API}/v1/speech-to-text", headers=_headers(), data=data,
                   files={"file": (filename, audio, content_type)}, timeout=httpx.Timeout(60.0, connect=10.0))
    if r.status_code >= 400:
        raise VoiceUnavailable(f"speech-to-text failed ({r.status_code}): {r.text[:160]}")
    j = r.json()
    return {"text": j.get("text", ""), "language_code": j.get("language_code"),
            "duration": j.get("audio_duration_secs"), "language_probability": j.get("language_probability"),
            "words": j.get("words")}
