"""Opt-in membership of the anonymous class view (the teacher / institution page). Nothing is shared unless the learner joins here."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import privacy
from ..adapters.impl import MIN_CLASS_SIZE, OPEN_COHORT_ID
from ..db import get_db
from ..deps import current_learner
from ..models import CohortMember, Learner

router = APIRouter(prefix="/api/cohort/membership", tags=["class-view"])


def _is_member(db: Session, lr: Learner) -> bool:
    return db.get(CohortMember, (OPEN_COHORT_ID, lr.id)) is not None


@router.get("")
def status(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    n = len(list(db.scalars(select(CohortMember).where(CohortMember.cohort_id == OPEN_COHORT_ID))))
    return {"member": _is_member(db, lr), "joined": n, "min_learners": MIN_CLASS_SIZE}


@router.post("")
def join(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    if not _is_member(db, lr):
        db.add(CohortMember(cohort_id=OPEN_COHORT_ID, learner_id=lr.id, display_name="", is_mock=False))
        db.flush()
    return status(lr, db)


@router.delete("")
def leave(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    db.execute(delete(CohortMember).where(CohortMember.cohort_id == OPEN_COHORT_ID, CohortMember.learner_id == lr.id))
    db.flush()
    return status(lr, db)


def _export(db: Session, learner: Learner) -> dict[str, Any]:
    return {"in_class_view": _is_member(db, learner)}


def _delete(db: Session, learner: Learner) -> None:
    db.execute(delete(CohortMember).where(CohortMember.learner_id == learner.id))


privacy.register_export("class_view_membership", _export)
privacy.register_delete(_delete)
