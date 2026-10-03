"""T06 — Progress-over-time routes.

GET /api/progress/history?days=90   → full history payload
GET /api/progress/radar             → per-domain current vs target list
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_learner
from ..engines import progress as progress_engine
from ..models import Learner

router = APIRouter(prefix="/api")

_DAYS_MIN = 7
_DAYS_MAX = 365


@router.get("/progress/history")
def get_history(
    days: int = Query(default=90, ge=_DAYS_MIN, le=_DAYS_MAX),
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    """Return progress-over-time series, markers, now, projection and due_reviews."""
    return progress_engine.history(db, lr, since_days=days)


@router.get("/progress/radar")
def get_radar(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Return per-domain current vs target for the radar chart."""
    return {"domains": progress_engine.radar(db, lr)}
