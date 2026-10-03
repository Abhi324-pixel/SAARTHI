"""Interview extension routes (T08: HR & behavioural rounds, interview packs, history).

Endpoints:
  GET /api/interview/packs
  GET /api/interview/history
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..models import Learner, LearningSession

router = APIRouter(prefix="/api/interview", tags=["interview-ext"])


@router.get("/packs")
def list_interview_packs():
    """List available interview packs (services fresher, product junior, internship, etc.)."""
    c = get_content()
    return {"packs": c.get_packs()}


@router.get("/history")
def get_interview_history(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """List finished interview sessions for the current learner without invented percentiles."""
    sessions = list(
        db.scalars(
            select(LearningSession)
            .where(LearningSession.learner_id == lr.id, LearningSession.mode == "interview")
            .order_by(LearningSession.created_at.desc())
        )
    )
    history: list[dict[str, Any]] = []
    for s in sessions:
        st = s.state or {}
        res = st.get("results", {})
        n_cov = sum(len(r.get("covered", [])) for r in res.values())
        n_tot = sum(len(r.get("covered", [])) + len(r.get("missed", [])) for r in res.values())
        history.append({
            "session_id": s.id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "status": s.status,
            "round": st.get("round", "technical"),
            "pack_id": st.get("pack_id"),
            "role_title": st.get("role_title", "Backend Developer"),
            "total_topics": len(st.get("queue", [])),
            "completed_topics": len(res),
            "checklist_items_covered": n_cov,
            "checklist_items_total": n_tot,
            "strengths": [r.get("name", cid) for cid, r in res.items() if r.get("score", 0) >= 0.75],
            "needs_work": [r.get("name", cid) for cid, r in res.items() if r.get("score", 0) < 0.5],
        })
    return {"history": history}
