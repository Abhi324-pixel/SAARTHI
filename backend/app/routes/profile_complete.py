"""Finish a profile that was created without an age (Google / OAuth sign-up). Spec: docs/features/C07."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_learner
from ..engines import audit, safeguarding
from ..models import Learner
from .core import _me

router = APIRouter(prefix="/api")


class CompleteIn(BaseModel):
    age: int = Field(ge=safeguarding.MIN_AGE, le=safeguarding.MAX_AGE)
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    language: Optional[str] = None


@router.post("/me/complete-profile")
def complete_profile(body: CompleteIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Record the learner's age once. It cannot be changed afterwards through the app (a minor must not be able to flip to
    'adult' to skip guardian approval); a correction is a support action."""
    if safeguarding.age_confirmed(lr):
        if body.age != lr.age:
            raise HTTPException(409, "Your age is already recorded and can't be changed here. Ask support if it is wrong.")
    else:
        lr.age = body.age
        lr.settings = {**(lr.settings or {}), "age_confirmed": True}
        audit.record(db, actor_id=lr.id, actor_role="learner", action="age_confirmed", subject_type="learner", subject_id=lr.id,
                     detail={"minor": body.age < 18})
    if body.name and body.name.strip():
        lr.name = body.name.strip()[:80]
    if body.language in ("english", "hindi", "hinglish"):
        lr.language_pref = body.language
    db.flush()
    return _me(db, lr)
