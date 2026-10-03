"""T07: Typed assistant chat routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import current_learner, get_db
from ..engines import chat
from ..models import Learner, LearningSession

router = APIRouter(prefix="/api")


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None


@router.post("/chat")
def post_chat_message(
    body: ChatIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    clean_msg = body.message.strip()
    if not clean_msg or len(clean_msg) > 1000:
        raise HTTPException(422, "Message must be between 1 and 1000 characters.")

    if body.session_id:
        sess = db.scalars(
            select(LearningSession).where(
                LearningSession.id == body.session_id,
                LearningSession.learner_id == lr.id,
            )
        ).first()
        if not sess:
            raise HTTPException(404, "Chat session not found.")

    return chat.reply_to_message(db, lr, clean_msg, session_id=body.session_id)


@router.get("/chat/suggestions")
def get_chat_suggestions(
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    return {"suggestions": chat.get_chat_suggestions(db, lr)}
