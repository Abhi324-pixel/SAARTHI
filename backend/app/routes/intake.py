"""T01 — Free-text goal and conversational intake routes.

POST /api/intake/turn     → Process a conversational intake message, extract structured constraints
POST /api/intake/confirm  → Apply the confirmed intake draft to learner profile and build roadmap
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_learner
from ..engines import intake
from ..llm.gateway import LLMUnavailable
from ..models import Learner, LearningSession, TranscriptTurn

router = APIRouter(prefix="/api/intake")


class IntakeTurnIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class IntakeConfirmIn(BaseModel):
    goal_text: Optional[str] = None
    role_id: Optional[str] = None
    weekly_hours: Optional[float] = None
    horizon_weeks: Optional[int] = None
    language: Optional[str] = None
    known_skills: Optional[list[dict[str, Any]]] = None


@router.post("/turn")
def intake_turn(
    body: IntakeTurnIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    try:
        session = db.scalar(
            select(LearningSession).where(
                LearningSession.learner_id == lr.id,
                LearningSession.mode == "intake",
                LearningSession.status == "active",
            ).order_by(LearningSession.created_at.desc())
        )
        if not session:
            session = LearningSession(learner_id=lr.id, mode="intake", channel="text", status="active")
            db.add(session)
            db.flush()

        turns = list(db.scalars(
            select(TranscriptTurn).where(
                TranscriptTurn.session_id == session.id
            ).order_by(TranscriptTurn.created_at.asc())
        ))
        history = [{"role": t.role, "text": t.text} for t in turns]

        res = intake.extract(db, lr, body.message.strip(), history=history)

        # Store turn in transcript
        db.add(TranscriptTurn(session_id=session.id, role="learner", text=body.message.strip()))
        ai_reply = res.get("follow_up") or "Understood your goal."
        db.add(TranscriptTurn(session_id=session.id, role="mentor_ai", text=ai_reply, meta=res["understood"]))

        # Store draft in learner settings
        settings = dict(lr.settings or {})
        settings["intake_draft"] = res["understood"]
        lr.settings = settings
        db.flush()

        return res
    except LLMUnavailable:
        return {
            "unavailable": True,
            "message": "I couldn't read that just now — please use the form",
            "understood": {},
            "follow_up": None,
            "ready": False,
            "unavailable_role": None,
        }


@router.post("/confirm")
def intake_confirm(
    body: Optional[IntakeConfirmIn] = None,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    settings = dict(lr.settings or {})
    draft = dict(settings.get("intake_draft") or {})

    # Apply overrides from body if provided
    if body:
        if body.goal_text is not None:
            draft["goal_text"] = body.goal_text
        if body.role_id is not None:
            draft["role_id"] = body.role_id
        if body.weekly_hours is not None:
            draft["weekly_hours"] = body.weekly_hours
        if body.horizon_weeks is not None:
            draft["horizon_weeks"] = body.horizon_weeks
        if body.language is not None:
            draft["language"] = body.language
        if body.known_skills is not None:
            draft["known_skills"] = body.known_skills

    if not draft and not body:
        raise HTTPException(400, "No pending intake draft to confirm. Please submit an intake message first.")

    res = intake.apply(db, lr, draft)

    # Close any active intake sessions
    sessions = list(db.scalars(
        select(LearningSession).where(
            LearningSession.learner_id == lr.id,
            LearningSession.mode == "intake",
            LearningSession.status == "active",
        )
    ))
    for s in sessions:
        s.status = "completed"
    db.flush()

    return res
