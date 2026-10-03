"""T03 — Difficulty & Preference Feedback Routes.

POST /api/feedback              → apply feedback with rate-limiting
GET  /api/feedback/adaptations  → inspect adapted practice factors & strategy preferences
POST /api/feedback/reset        → reset all feedback adaptations back to defaults
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..engines import feedback as feedback_engine, mastery, planner
from ..models import EvidenceEvent, Learner

router = APIRouter(prefix="/api/feedback")

_HOURLY_RATE_LIMIT = 6


class FeedbackIn(BaseModel):
    concept_id: str
    signal: str  # too_easy | too_hard | helpful | not_helpful
    context: str = "explanation"  # explanation | task | quiz
    item_id: Optional[str] = None


@router.post("")
def post_feedback(
    body: FeedbackIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    content = get_content()
    if body.concept_id not in content.concepts:
        raise HTTPException(404, f"Unknown concept {body.concept_id}")

    if body.signal not in feedback_engine.SIGNALS:
        raise HTTPException(400, f"Invalid signal {body.signal}. Allowed: {sorted(feedback_engine.SIGNALS)}")

    # Rate limiting: count feedback events on this concept in the last 1 hour
    now = mastery.learner_now(lr)
    one_hour_ago = now - timedelta(hours=1)

    count = db.scalar(
        select(func.count(EvidenceEvent.id)).where(
            EvidenceEvent.learner_id == lr.id,
            EvidenceEvent.concept_id == body.concept_id,
            EvidenceEvent.source_type == "feedback",
            EvidenceEvent.created_at >= one_hour_ago,
        )
    ) or 0

    if count >= _HOURLY_RATE_LIMIT:
        raise HTTPException(
            429,
            "You've sent feedback several times recently for this concept. Try working through the current material first!",
        )

    return feedback_engine.apply(
        db,
        lr,
        concept_id=body.concept_id,
        signal=body.signal,
        context=body.context,
        item_id=body.item_id,
    )


@router.get("/adaptations")
def get_adaptations(lr: Learner = Depends(current_learner)):
    settings = lr.settings or {}
    return {
        "practice_factors": settings.get("practice_factor", {}),
        "default_factor": planner.PRACTICE_FACTOR,
        "helpful_strategies": settings.get("helpful_strategies", {}),
    }


@router.post("/reset")
def reset_adaptations(
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    return feedback_engine.reset_adaptations(db, lr)
