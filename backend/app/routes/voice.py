"""Voice endpoints: ElevenLabs agent connection, TTS, STT, and the agent's tool dispatcher."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import agent_tools
from ..db import get_db
from ..deps import current_learner
from ..engines import speech as speech_engine
from ..models import Learner, LearningSession, TranscriptTurn
from ..voice import elevenlabs

router = APIRouter(prefix="/api/voice")


@router.get("/status")
def status(lr: Learner = Depends(current_learner)):
    return elevenlabs.status()


class ConnectIn(BaseModel):
    mode: str = "explain_back"
    concept_id: Optional[str] = None
    use_resume: bool = False      # interview mode only: base the questions on the learner's own resume summary


@router.post("/connect")
def connect(body: ConnectIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Everything the browser needs to start a conversation: connection details, dynamic variables, voice session id."""
    try:
        conn = elevenlabs.agent_connection()
    except elevenlabs.VoiceUnavailable as e:
        raise HTTPException(503, str(e))
    sess = agent_tools.start_voice_session(db, lr, body.mode, body.concept_id, body.use_resume)
    dv = agent_tools.dynamic_variables(db, lr, body.mode, body.concept_id, body.use_resume)
    sess.state = {**sess.state, "concept_id": dv["current_concept"]}
    return {**conn, "voice_session_id": sess.id, "dynamic_variables": dv}


class ToolIn(BaseModel):
    voice_session_id: Optional[str] = None
    args: dict[str, Any] = Field(default_factory=dict)


@router.post("/tools/{tool}")
def tool(tool: str, body: ToolIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return agent_tools.dispatch(db, lr, tool, body.args, body.voice_session_id)


class TurnIn(BaseModel):
    voice_session_id: str
    role: str
    text: str = Field(max_length=2000)


@router.post("/transcript")
def transcript(body: TurnIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    sess = db.get(LearningSession, body.voice_session_id)
    if sess is None or sess.learner_id != lr.id:
        raise HTTPException(404, "session not found")
    db.add(TranscriptTurn(session_id=sess.id, role=body.role if body.role in ("learner", "mentor_ai") else "system", text=body.text))
    return {"ok": True}


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    language: Optional[str] = None


@router.post("/tts")
def tts(body: TtsIn, lr: Learner = Depends(current_learner)):
    try:
        audio = elevenlabs.text_to_speech(body.text, body.language or lr.language_pref)
    except elevenlabs.VoiceUnavailable as e:
        raise HTTPException(503, str(e))
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/stt")
async def stt(file: UploadFile = File(...), language: Optional[str] = Form(default=None), lr: Learner = Depends(current_learner)):
    data = await file.read()
    if not data or len(data) > 15 * 1024 * 1024:
        raise HTTPException(400, "Audio is empty or too large.")
    try:
        res = elevenlabs.speech_to_text(data, file.filename or "audio.webm", file.content_type or "audio/webm", language or None)
        lang = language or res.get("language_code") or lr.language_pref
        metrics = speech_engine.analyze(res.get("words"), language=lang)
        return {
            "text": res.get("text", ""),
            "language_code": res.get("language_code"),
            "duration": res.get("duration"),
            "language_probability": res.get("language_probability"),
            "words": res.get("words"),
            "speech": metrics,
        }
    except elevenlabs.VoiceUnavailable as e:
        raise HTTPException(503, str(e))
