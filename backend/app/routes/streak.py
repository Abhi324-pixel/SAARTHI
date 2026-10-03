"""T04 — Streak and daily goal routes.

GET  /api/streak            → streak summary + show flag
PATCH /api/streak/settings  → update daily_goal and/or show preference
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_learner
from ..engines import streak as streak_engine
from ..models import Learner

router = APIRouter(prefix="/api")


@router.get("/streak")
def get_streak(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Return the learner's current streak summary plus the show flag."""
    summary = streak_engine.for_learner(db, lr)
    settings = lr.settings or {}
    show = bool(settings.get("streak_show", True))
    return {**summary, "show": show}


class StreakSettingsIn(BaseModel):
    daily_goal: Optional[int] = Field(default=None, ge=streak_engine.DAILY_GOAL_MIN, le=streak_engine.DAILY_GOAL_MAX)
    show: Optional[bool] = None


@router.patch("/streak/settings")
def update_streak_settings(
    body: StreakSettingsIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    """Update daily_goal (1–10) and/or show toggle for this learner."""
    settings = dict(lr.settings or {})
    if body.daily_goal is not None:
        settings["daily_goal"] = body.daily_goal
    if body.show is not None:
        settings["streak_show"] = body.show
    lr.settings = settings
    db.flush()
    # Return the fresh summary so the frontend can update in one round-trip
    summary = streak_engine.for_learner(db, lr)
    return {**summary, "show": bool(settings.get("streak_show", True))}
