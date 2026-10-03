"""C03: Learner prep notes and session summary routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import current_learner, get_db
from ..engines import casenotes, escalation
from ..models import Learner, MentorCase

router = APIRouter(prefix="/api")


def _get_case(db: Session, learner: Learner, case_id: str) -> MentorCase:
    case = db.scalars(select(MentorCase).where(MentorCase.id == case_id)).first()
    if not case or case.learner_id != learner.id:
        raise HTTPException(404, "Mentor case not found.")
    return case


@router.get("/cases/{case_id}/prep")
def get_case_prep(
    case_id: str,
    lang: Optional[str] = Query(None),
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    case = _get_case(db, lr, case_id)
    if case.status not in ("accepted", "scheduled", "matched"):
        raise HTTPException(
            409,
            f"Prep notes are only available for matched or scheduled sessions (current status: {case.status}).",
        )
    return casenotes.learner_prep(db, lr, case, lang=lang)


class ShareIn(BaseModel):
    question_indexes: list[int] = Field(default_factory=list)


@router.post("/cases/{case_id}/prep/share")
def share_prep_questions(
    case_id: str,
    body: ShareIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    case = _get_case(db, lr, case_id)
    if case.status not in ("accepted", "scheduled", "matched"):
        raise HTTPException(
            409, f"Cannot share questions for a case with status: {case.status}."
        )
    prep = casenotes.learner_prep(db, lr, case)
    all_qs = prep.get("questions", [])
    selected = [all_qs[i]["text"] for i in body.question_indexes if 0 <= i < len(all_qs)]
    if not selected:
        raise HTTPException(400, "No valid questions selected.")
    msg_text = "Questions I'd like to discuss in our session:\n" + "\n".join(f"- {q}" for q in selected)
    res = escalation.send_message(db, lr, case, msg_text)
    return res


@router.get("/cases/{case_id}/summary")
def get_case_summary(
    case_id: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    case = _get_case(db, lr, case_id)
    if case.status not in ("followup", "closed"):
        raise HTTPException(
            409,
            f"Session summary is only available after session completion (current status: {case.status}).",
        )
    return casenotes.session_summary(db, lr, case)
