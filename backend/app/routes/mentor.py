"""Chhatrachhaya mentor layer, consent, safeguarding report, teacher cohort view."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import adapters
from ..config import settings
from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..engines import escalation, hooks, mentor_console, notify, safeguarding
from ..models import Learner, MentorCase, SafeguardingReport

router = APIRouter(prefix="/api")


def _case(db: Session, lr: Learner, case_id: str) -> MentorCase:
    case = db.get(MentorCase, case_id)
    if case is None or case.learner_id != lr.id:
        raise HTTPException(404, "case not found")
    return case


@router.get("/mentors")
def list_mentors(tier: Optional[str] = None, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    d = adapters.mentors()
    return {"mock": d.is_mock, "mentors": [m.public() for m in d.list(db, tier)]}


@router.get("/cases")
def list_cases(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    mentor_console.expire_stale(db)
    rows = db.scalars(select(MentorCase).where(MentorCase.learner_id == lr.id).order_by(MentorCase.created_at.desc()))
    return {"cases": [escalation.case_view(db, k, with_messages=False) for k in rows],
            "suggestions": escalation.check_triggers(db, lr), "mock": adapters.mentors().is_mock}


class CaseIn(BaseModel):
    category: Optional[str] = None
    concept_id: Optional[str] = None
    reason: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=1000)
    trigger: str = "learner_request"
    share_transcript: bool = False


@router.post("/cases")
def create_case(body: CaseIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    category = body.category or escalation.classify_category(body.reason + " " + body.note)
    if category == "career":
        body.concept_id = None
    if body.concept_id and body.concept_id not in get_content().concepts:
        raise HTTPException(404, "unknown concept")
    # the wellbeing path is also triggered by what the learner wrote, whatever category was chosen
    if escalation.classify_category(body.reason + " " + body.note) == "wellbeing":
        category = "wellbeing"
    if category != "wellbeing":          # someone in distress is never turned away because their age is unknown
        safeguarding.require_age(lr)
    if body.share_transcript and adapters.consent().status(db, lr, "transcript_share") != "granted":
        raise HTTPException(403, "Sharing transcripts needs your consent first (Settings > Privacy).")
    try:
        return escalation.open_case(db, lr, category=category, concept_id=body.concept_id, trigger=body.trigger,
                                    reason=body.reason or "Learner asked for a mentor.", learner_note=body.note,
                                    share_transcript=body.share_transcript)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/cases/{case_id}")
def get_case(case_id: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    mentor_console.expire_stale(db)
    return escalation.case_view(db, _case(db, lr, case_id))


class MsgIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


@router.post("/cases/{case_id}/messages")
def send(case_id: str, body: MsgIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    case = _case(db, lr, case_id)
    if case.status in ("awaiting_consent", "escalated", "closed"):
        raise HTTPException(409, f"This case is {case.status.replace('_', ' ')}.")
    out = escalation.send_message(db, lr, case, body.text)
    out["case"] = escalation.case_view(db, case)
    return out


class SimIn(BaseModel):
    rating: float = Field(default=0.7, ge=0, le=1)


@router.post("/cases/{case_id}/simulate-session")
def simulate_session(case_id: str, body: SimIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Demo helper (mock mentors only): pretend the session took place and record the mentor's outcome."""
    case = _case(db, lr, case_id)
    if not adapters.mentors().is_mock:
        raise HTTPException(400, "Sessions are held with real mentors; nothing to simulate.")
    if case.status not in ("accepted", "scheduled", "matched", "held"):
        raise HTTPException(409, "No session to simulate for this case.")
    mentor = adapters.mentors().get(db, case.mentor_id)
    c = get_content()
    cname = c.concepts[case.concept_id].name if case.concept_id in c.concepts else "your goal"
    notes = (f"(Demo) Session held with {mentor.name if mentor else 'the mentor'} on {cname}. Walked through the learner's failing "
             "query line by line and had them predict the result before running it.")
    out = escalation.record_outcome(db, lr, case, notes, body.rating, "Redo the practice tasks, then explain it back.")
    out["after"] = hooks.after_evidence(db, lr, case.concept_id, "your mentor session")
    out["case"] = escalation.case_view(db, case)
    return out


@router.post("/cases/{case_id}/followup")
def followup(case_id: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    case = _case(db, lr, case_id)
    out = escalation.followup_check(db, lr, case)
    out["case"] = escalation.case_view(db, case)
    return out


# ---- consent --------------------------------------------------------------------------------------------------------------
@router.get("/consent")
def consent_status(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    p = adapters.consent()
    out = {"mock": p.is_mock, "is_minor": safeguarding.is_minor(lr),
           "scopes": {s: p.status(db, lr, s) for s in ("mentor_sessions", "transcript_share")}}
    if not p.is_mock and safeguarding.is_minor(lr):
        from ..engines import guardian
        out["request"] = guardian.current_request(db, lr, "mentor_sessions")     # masked address, status, when it can be re-sent
        out["dev_outbox"] = (not settings.is_prod) and adapters.mailer().is_mock  # the UI may offer the dev-only outbox viewer
    return out


class ConsentIn(BaseModel):
    scope: str = "mentor_sessions"


class ConsentRequestIn(BaseModel):
    scope: str = "mentor_sessions"
    guardian_email: Optional[str] = Field(default=None, max_length=200)
    lang: str = "english"


@router.post("/consent/request")
def consent_request(body: ConsentRequestIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """A minor asks for guardian approval. In real mode the guardian's e-mail gets a signed link; the response never contains it."""
    from ..engines import guardian
    safeguarding.require_age(lr)
    try:
        return adapters.consent().request(db, lr, body.scope, guardian_email=body.guardian_email, lang=body.lang)
    except guardian.GuardianError as e:
        raise HTTPException(e.status, e.message)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/consent/grant-demo")
def consent_grant_demo(body: ConsentIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Mock guardian approval. Exists only while CONSENT=mock; the real flow uses a signed guardian link."""
    safeguarding.require_age(lr)
    p = adapters.consent()
    if not p.is_mock:
        raise HTTPException(400, "Guardian approval is done through the signed link sent to the guardian.")
    out = p.grant(db, lr, body.scope, "guardian")
    out["resumed"] = escalation.resume_after_consent(db, lr) if body.scope == "mentor_sessions" else []
    return out


@router.post("/consent/self-grant")
def self_grant(body: ConsentIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Adults can grant optional scopes (e.g. sharing transcript excerpts) themselves."""
    safeguarding.require_age(lr)
    if safeguarding.is_minor(lr):
        raise HTTPException(403, "A guardian must approve this.")
    return adapters.consent().grant(db, lr, body.scope, "learner")


@router.post("/consent/revoke")
def consent_revoke(body: ConsentIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return adapters.consent().revoke(db, lr, body.scope)


# ---- safeguarding report ------------------------------------------------------------------------------------------------------
class ReportIn(BaseModel):
    case_id: Optional[str] = None
    category: str = "concern"
    detail: str = Field(default="", max_length=1000)


@router.post("/reports")
def report(body: ReportIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    r = SafeguardingReport(reporter_id=lr.id, case_id=body.case_id, category=body.category, detail=body.detail)
    db.add(r)
    db.flush()
    notify.notify_admins(db, "safeguarding_report", {}, "/admin", dedupe_key=f"report:{r.id}")
    return {"report_id": r.id, "status": "open", "message": "Thank you. A safeguarding lead reviews every report, target within 24 hours.",
            "helpline": escalation.HELPLINE}


# ---- teacher / institution view (lite) ----------------------------------------------------------------------------------------------
@router.get("/cohort")
def cohort(cohort_id: Optional[str] = None, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    prov = adapters.cohort()
    cid = cohort_id or ("mock_cohort_bca_2" if prov.is_mock else "saarthi-learners")
    return prov.summary(db, cid)
