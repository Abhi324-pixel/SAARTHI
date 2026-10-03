"""Mentor console (the mentor's side of a case) and the safeguarding lead's report queue. Spec: docs/features/C02.
Real mentors only (404 while mentors are mock)."""

from __future__ import annotations

import time
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import adapters
from ..adapters.base import Principal
from ..config import settings
from ..db import get_db
from ..deps import current_account, current_admin
from ..engines import mentor_apply, mentor_console as mc
from ..demo_accounts import DEMO_MENTOR_IDS, LEARNERS, ensure_mentor_learner
from ..models import Learner, Mentor

router = APIRouter(prefix="/api")


def _db_mode() -> None:
    if settings.mentors_mode != "db":
        raise HTTPException(404, "The mentor console is only available with real mentors (SAARTHI_MENTORS=db).")


def current_mentor(p: Principal = Depends(current_account), db: Session = Depends(get_db)) -> Mentor:
    _db_mode()
    m = mc.get_mentor_row(db, p.learner_id)
    if not mc.mentor_allowed(m):
        raise HTTPException(403, "This account is not a verified mentor.")
    return m


def _run(fn, *args):
    try:
        return fn(*args)
    except mc.ConsoleError as e:
        raise HTTPException(e.status, {"code": e.code, "message": e.message} if e.code else e.message)


def _active(db: Session, m: Mentor) -> Mentor:
    _run(mc.require_pledge, db, m)
    return m


# ---- mentor ------------------------------------------------------------------------------------------------
@router.get("/mentor-console/me")
def me(m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    mc.expire_stale(db)
    return mc.summary(db, m)


class PledgeIn(BaseModel):
    version: str = Field(max_length=40)


@router.post("/mentor-console/me/pledge")
def pledge(body: PledgeIn, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    _run(mc.accept_pledge, db, m, body.version)
    return {"ok": True}


class AvailabilityIn(BaseModel):
    availability: list[str] = Field(max_length=30)


@router.put("/mentor-console/me/availability")
def availability(body: AvailabilityIn, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    try:
        m.availability = mentor_apply.clean_profile({"availability": body.availability})["availability"]
    except mentor_apply.ApplyError as e:
        raise HTTPException(e.status, e.message)
    db.flush()
    return {"availability": m.availability}


@router.get("/mentor-console/cases")
def cases(group: Optional[str] = None, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    mc.expire_stale(db)
    return {"cases": _run(mc.list_cases, db, m, group)}


@router.get("/mentor-console/cases/{case_id}")
def case(case_id: str, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    mc.expire_stale(db)
    return _run(mc.get_case, db, m, case_id)


class AcceptIn(BaseModel):
    slot: str = Field(max_length=80)


@router.post("/mentor-console/cases/{case_id}/accept")
def accept(case_id: str, body: AcceptIn, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    return _run(mc.accept, db, _active(db, m), case_id, body.slot)


class DeclineIn(BaseModel):
    reason: str = Field(max_length=24)


@router.post("/mentor-console/cases/{case_id}/decline")
def decline(case_id: str, body: DeclineIn, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    return _run(mc.decline, db, _active(db, m), case_id, body.reason)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


@router.post("/mentor-console/cases/{case_id}/messages")
def message(case_id: str, body: MessageIn, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    return _run(mc.send_message, db, _active(db, m), case_id, body.text)


@router.post("/mentor-console/cases/{case_id}/held")
def held(case_id: str, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    return _run(mc.mark_held, db, _active(db, m), case_id)


class OutcomeIn(BaseModel):
    notes: str = Field(max_length=1500)
    next_step: str = Field(default="", max_length=300)
    demonstrated: int = Field(ge=1, le=5)


@router.post("/mentor-console/cases/{case_id}/outcome")
def outcome(case_id: str, body: OutcomeIn, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    return _run(mc.record_outcome, db, _active(db, m), case_id, body.notes, body.next_step, body.demonstrated)


class FlagIn(BaseModel):
    detail: str = Field(max_length=1000)


@router.post("/mentor-console/cases/{case_id}/flag")
def flag(case_id: str, body: FlagIn, m: Mentor = Depends(current_mentor), db: Session = Depends(get_db)):
    return _run(mc.flag_concern, db, m, case_id, body.detail)


# ---- safeguarding lead --------------------------------------------------------------------------------------
@router.get("/admin/reports")
def reports(status: Optional[str] = "open", a: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    _db_mode()
    return {"reports": mc.list_reports(db, status or None)}


class ResolveIn(BaseModel):
    note: str = Field(max_length=500)


@router.post("/admin/reports/{report_id}/resolve")
def resolve(report_id: str, body: ResolveIn, a: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    _db_mode()
    return _run(mc.resolve_report, db, a.learner_id, report_id, body.note)


# ---- dev only ------------------------------------------------------------------------------------------------
class DevMentorIn(BaseModel):
    mentor_id: str = Field(max_length=64)


@router.post("/dev/mentor-login")
def dev_mentor_login(body: DevMentorIn, db: Session = Depends(get_db)):
    """Dev/demo helper (mock sign-in + real mentors table, never in prod): a token for a seeded demo mentor so the console can be driven by hand."""
    _db_mode()
    if settings.is_prod or not adapters.auth().is_mock:
        raise HTTPException(404, "Not found")
    m = db.get(Mentor, body.mentor_id)
    if not mc.mentor_allowed(m):
        raise HTTPException(404, "Mentor not found")
    tok = jwt.encode({"sub": m.id, "name": m.name, "iat": int(time.time()), "mock": True}, settings.secret, algorithm="HS256")
    return {"token": tok, "mentor_id": m.id, "name": m.name}


def _demo_menu_allowed() -> bool:
    return not settings.is_prod and adapters.auth().is_mock


def _demo_accounts(db: Session) -> list[dict]:
    out = []
    for spec in LEARNERS:
        if db.get(Learner, spec["id"]) is not None:
            out.append({"id": spec["id"], "name": spec["name"], "role": "learner", "note": spec["note"]})
    if settings.mentors_mode == "db":
        for mid in DEMO_MENTOR_IDS:
            m = db.get(Mentor, mid)
            if mc.mentor_allowed(m):
                out.append({"id": m.id, "name": m.name, "role": "mentor", "note": "mentor console"})
    return out


@router.get("/dev/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Dev only (mock sign-in, never in prod): the fake accounts seeded by scripts/seed_demo.py, for the login page's Demo accounts menu."""
    if not _demo_menu_allowed():
        raise HTTPException(404, "Not found")
    return {"accounts": _demo_accounts(db)}


@router.post("/dev/demo-login")
def demo_login(body: DevMentorIn, db: Session = Depends(get_db)):
    """Dev only: a token for one of the listed demo accounts (fixed ids only, so this cannot sign in as anybody else)."""
    if not _demo_menu_allowed():
        raise HTTPException(404, "Not found")
    acc = next((a for a in _demo_accounts(db) if a["id"] == body.mentor_id), None)
    if acc is None:
        raise HTTPException(404, "Not found")
    if acc["role"] == "mentor":
        ensure_mentor_learner(db, db.get(Mentor, acc["id"]))
    tok = jwt.encode({"sub": acc["id"], "name": acc["name"], "iat": int(time.time()), "mock": True}, settings.secret, algorithm="HS256")
    return {"token": tok, "learner_id": acc["id"], "name": acc["name"], "role": acc["role"]}
