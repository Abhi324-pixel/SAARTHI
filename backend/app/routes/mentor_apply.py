"""Mentor sign-up (applicant side) and the safeguarding lead's review (admin side). Real mentors only: 404 while mentors are mock.
Spec: docs/features/C01."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..adapters.base import Principal
from ..config import settings
from ..db import get_db
from ..deps import current_account, current_admin
from ..engines import mentor_apply as ma

router = APIRouter(prefix="/api")


def _real_mentors_only() -> None:
    if settings.mentors_mode != "db":
        raise HTTPException(404, "Mentor sign-up is only available with real mentors (SAARTHI_MENTORS=db).")


def _err(e: ma.ApplyError):
    raise HTTPException(e.status, e.message)


# ---- applicant ------------------------------------------------------------------------------------------------
@router.get("/mentor/apply")
def my_application(p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    _real_mentors_only()
    pl = ma.pledge()
    return {"application": ma.view(ma.get(db, p.learner_id)),
            "pledge": {"version": pl["version"], "promises": [{"id": x["id"], "en": x["en"], "hi": x["hi"]} for x in pl["promises"]]},
            "options": {"tiers": list(ma.TIERS), "languages": list(ma.LANGUAGES), "expertise": sorted(ma.allowed_expertise()),
                        "slot_format": "Mon 18:00 (India time)"}}


class ProfileIn(BaseModel):
    tier_requested: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=120)
    headline: Optional[str] = Field(default=None, max_length=240)
    bio: Optional[str] = Field(default=None, max_length=2000)
    years_experience: Optional[int] = None
    organisation: Optional[str] = Field(default=None, max_length=300)
    expertise: Optional[list[str]] = Field(default=None, max_length=30)
    languages: Optional[list[str]] = Field(default=None, max_length=10)
    availability: Optional[list[str]] = Field(default=None, max_length=30)


@router.put("/mentor/apply")
def save_profile(body: ProfileIn, p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    _real_mentors_only()
    try:
        return ma.view(ma.save_draft(db, p, body.model_dump(exclude_none=True)))
    except ma.ApplyError as e:
        _err(e)


def _mine(db: Session, p: Principal):
    app = ma.get(db, p.learner_id)
    if app is None:
        raise HTTPException(409, "Save your profile first.")
    return app


@router.get("/mentor/apply/screen")
def screen_get(p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    _real_mentors_only()
    return ma.screen_questions(_mine(db, p))


class ScreenIn(BaseModel):
    answers: dict[str, int] = Field(default_factory=dict)
    open: dict[str, str] = Field(default_factory=dict)


@router.post("/mentor/apply/screen")
def screen_post(body: ScreenIn, p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    _real_mentors_only()
    try:
        return ma.submit_screen(db, _mine(db, p), body.answers, body.open)
    except ma.ApplyError as e:
        _err(e)


class PledgeIn(BaseModel):
    version: str = Field(max_length=40)


@router.post("/mentor/apply/pledge")
def pledge_accept(body: PledgeIn, p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    _real_mentors_only()
    try:
        ma.accept_pledge(db, _mine(db, p), body.version)
        return {"ok": True}
    except ma.ApplyError as e:
        _err(e)


@router.post("/mentor/apply/submit")
def submit(p: Principal = Depends(current_account), db: Session = Depends(get_db)):
    _real_mentors_only()
    try:
        return ma.view(ma.submit(db, _mine(db, p)))
    except ma.ApplyError as e:
        _err(e)


# ---- admin (safeguarding lead) ----------------------------------------------------------------------------------
@router.get("/admin/mentor-applications")
def admin_list(status: Optional[str] = None, a: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    _real_mentors_only()
    return {"applications": ma.list_applications(db, status)}


class CheckIn(BaseModel):
    kind: str = Field(max_length=24)
    note: str = Field(default="", max_length=300)


class DecisionIn(BaseModel):
    decision: str = Field(max_length=12)
    note: str = Field(default="", max_length=1000)
    checks: list[CheckIn] = Field(default_factory=list, max_length=8)


@router.post("/admin/mentor-applications/{app_id}/decision")
def admin_decide(app_id: str, body: DecisionIn, a: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    _real_mentors_only()
    try:
        return ma.decide(db, a.learner_id, app_id, body.decision, body.note, [c.model_dump() for c in body.checks])
    except ma.ApplyError as e:
        _err(e)


@router.get("/admin/mentors")
def admin_mentors(a: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    _real_mentors_only()
    return {"mentors": ma.list_mentors(db), "minor_policy": {"required_checks": list(ma.MINOR_REQUIRED_CHECKS)}}


class SuspendIn(BaseModel):
    note: str = Field(max_length=1000)


@router.post("/admin/mentors/{mentor_id}/suspend")
def admin_suspend(mentor_id: str, body: SuspendIn, a: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    _real_mentors_only()
    try:
        return ma.suspend(db, a.learner_id, mentor_id, body.note)
    except ma.ApplyError as e:
        _err(e)
