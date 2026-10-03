"""Notifications and unread counts for learners AND mentors/admins (any signed-in account). Spec: docs/features/C05."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..adapters.base import Principal
from ..db import get_db
from ..deps import current_account
from ..engines import notify
from ..models import Learner, MentorCase

router = APIRouter(prefix="/api")


@router.get("/notifications/summary")
def summary(p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    """The tiny poll that drives the bell and the badges."""
    learner = db.get(Learner, p.learner_id)
    if learner is not None:
        notify.reviews_due_check(db, learner)
    cases = notify.unread_by_case(db, p.learner_id)
    return {"unread": notify.unread_count(db, p.learner_id), "messages_unread": sum(cases.values()), "cases": cases}


@router.get("/notifications")
def listing(limit: int = 30, before: Optional[str] = None, p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    return {"notifications": notify.listing(db, p.learner_id, max(1, min(limit, 100)), before)}


class ReadIn(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=100)
    all: bool = False


@router.post("/notifications/read")
def read(body: ReadIn, p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    return {"marked": notify.mark_read(db, p.learner_id, body.ids, body.all)}      # only the caller's own rows can ever match


@router.post("/cases/{case_id}/read")
def case_read(case_id: str, p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    case = db.get(MentorCase, case_id)
    if case is None or p.learner_id not in (case.learner_id, case.mentor_id):
        raise HTTPException(404, "case not found")
    notify.mark_case_read(db, p.learner_id, case)
    return {"ok": True}
