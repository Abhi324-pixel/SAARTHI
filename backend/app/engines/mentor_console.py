"""The mentor's side of a case (spec docs/features/C02).

State machine (the mentor can move a case forward only along these edges; only the LEARNER's later evidence closes it):

    open --match--> matched --accept--> accepted --held--> held --outcome--> followup --(learner check)--> closed
                      |  decline / 24 h timeout: excluded, re-matched to someone else
    awaiting_consent --(guardian approves)--> matched          wellbeing --> escalated (never any mentor)

Mentors never set mastery: the outcome becomes `mentor` evidence with its own weight (escalation.record_outcome).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import adapters
from ..models import CaseMessage, Learner, Mentor, MentorCase, SafeguardingReport, now
from ..models_ext.C01 import MentorApplication
from ..models_ext.C02 import CaseExclusion
from . import audit, escalation, hooks, mentor_apply, notify

MATCH_TIMEOUT = timedelta(hours=24)
DECLINE_REASONS = ("busy", "outside_expertise", "conflict", "other")
WORKING = ("accepted", "scheduled", "held")
GROUPS = {"new": ("matched",), "active": WORKING, "followup": ("followup",), "closed": ("closed",)}
DEMONSTRATED = {1: 0.1, 2: 0.3, 3: 0.5, 4: 0.7, 5: 0.9}      # "how well did the learner show they understand this concept in the session?"


class ConsoleError(Exception):
    def __init__(self, status: int, message: str, code: Optional[str] = None) -> None:
        super().__init__(message)
        self.status, self.message, self.code = status, message, code


def get_mentor_row(db: Session, account_id: str) -> Optional[Mentor]:
    return db.get(Mentor, account_id)


def mentor_allowed(m: Optional[Mentor]) -> bool:
    """Verified real mentors; demo (seeded) mentors only in a dev setup with the mock sign-in, so they can be driven by hand."""
    from ..config import settings
    if m is None or m.verification_status != "verified":
        return False
    return (not m.is_mock) or (adapters.auth().is_mock and not settings.is_prod)


def pledge_current(db: Session, m: Mentor) -> bool:
    app = db.scalars(select(MentorApplication).where(MentorApplication.user_id == m.id)).first()
    return True if app is None else app.pledge_version == mentor_apply.pledge()["version"]


def require_pledge(db: Session, m: Mentor) -> None:
    if not pledge_current(db, m):
        raise ConsoleError(409, "The code of conduct was updated. Please read and accept the current version first.", "PLEDGE_OUTDATED")


def accept_pledge(db: Session, m: Mentor, version: str) -> None:
    app = db.scalars(select(MentorApplication).where(MentorApplication.user_id == m.id)).first()
    if app is None:
        return
    try:
        mentor_apply.accept_pledge(db, app, version)
    except mentor_apply.ApplyError as e:
        raise ConsoleError(e.status, e.message)


# ---------------------------------------------------------------------------------------------------
# timeouts (lazy: evaluated whenever cases are read, so no scheduler is needed)
# ---------------------------------------------------------------------------------------------------

def expire_stale(db: Session) -> int:
    n = 0
    for case in list(db.scalars(select(MentorCase).where(MentorCase.status == "matched", MentorCase.updated_at < now() - MATCH_TIMEOUT))):
        if not case.mentor_id or adapters.mentors().is_mock:
            continue
        _exclude_and_rematch(db, case, case.mentor_id, "timeout", actor_id="system", actor_role="system")
        n += 1
    return n


def _exclude_and_rematch(db: Session, case: MentorCase, mentor_id: str, reason: str, *, actor_id: str, actor_role: str) -> None:
    db.add(CaseExclusion(case_id=case.id, mentor_id=mentor_id, reason=reason))
    case.mentor_id, case.status, case.scheduled_for, case.match_reasons, case.updated_at = None, "open", None, [], now()
    db.flush()
    learner = db.get(Learner, case.learner_id)
    if learner is not None:
        escalation._match_and_accept(db, learner, case)
    audit.record(db, actor_id=actor_id, actor_role=actor_role, action=f"case_{reason}", subject_type="mentor_case", subject_id=case.id)


# ---------------------------------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------------------------------

def summary(db: Session, m: Mentor) -> dict[str, Any]:
    rows = list(db.scalars(select(MentorCase).where(MentorCase.mentor_id == m.id)))
    counts = {g: sum(1 for r in rows if r.status in sts) for g, sts in GROUPS.items()}
    return {"mentor": {"id": m.id, "name": m.name, "tier": m.tier, "headline": m.headline, "availability": m.availability,
                       "active_case_cap": m.active_case_cap, "is_demo": m.is_mock},
            "load": escalation._active_load(db, m.id), "counts": counts,
            "pledge": {"current": pledge_current(db, m), "version": mentor_apply.pledge()["version"],
                       "promises": [{"id": p["id"], "en": p["en"], "hi": p["hi"]} for p in mentor_apply.pledge()["promises"]]}}


def list_cases(db: Session, m: Mentor, group: Optional[str]) -> list[dict[str, Any]]:
    q = select(MentorCase).where(MentorCase.mentor_id == m.id)
    if group:
        if group not in GROUPS:
            raise ConsoleError(422, "Unknown group.")
        q = q.where(MentorCase.status.in_(GROUPS[group]))
    out = []
    for c in db.scalars(q.order_by(MentorCase.updated_at.desc()).limit(100)):
        v = case_view(db, c, with_messages=False)
        out.append({k: v[k] for k in ("id", "status", "category", "concept_name", "scheduled_for", "created_at")} |
                   {"learner_first_name": (c.report or {}).get("learner", {}).get("first_name"),
                    "age_band": (c.report or {}).get("learner", {}).get("age_band")})
    return out


def case_view(db: Session, case: MentorCase, with_messages: bool = True) -> dict[str, Any]:
    """What a mentor may see of a case: the report, the thread, the outcome. Never the learner's id or e-mail; the
    learner appears as first name + age band (inside report.learner). Transcript excerpts exist only if the learner shared them."""
    v = escalation.case_view(db, case, with_messages=with_messages)
    v.pop("mentor", None)
    v.pop("is_mock", None)
    return v


def _mine(db: Session, m: Mentor, case_id: str) -> MentorCase:
    case = db.get(MentorCase, case_id)
    if case is None or case.mentor_id != m.id:
        raise ConsoleError(404, "case not found")
    return case


def get_case(db: Session, m: Mentor, case_id: str) -> dict[str, Any]:
    return case_view(db, _mine(db, m, case_id))


# ---------------------------------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------------------------------

def accept(db: Session, m: Mentor, case_id: str, slot: str) -> dict[str, Any]:
    case = _mine(db, m, case_id)
    if case.status != "matched":
        raise ConsoleError(409, "Only a new case can be accepted.")
    slot = (slot or "").strip()
    if not slot or len(slot) > 80:
        raise ConsoleError(422, "Choose a first session slot (or write one).")
    if escalation._active_load(db, m.id) - 1 >= m.active_case_cap:       # this case already counts as one
        raise ConsoleError(409, "You are at your case limit.")
    case.status, case.scheduled_for, case.updated_at = "accepted", slot, now()
    db.add(CaseMessage(case_id=case.id, sender="system", text=f"{m.name} accepted the case. First session: {slot}.", is_mock=False))
    db.flush()
    audit.record(db, actor_id=m.id, actor_role="mentor", action="case_accepted", subject_type="mentor_case", subject_id=case.id)
    notify.notify(db, case.learner_id, "case_accepted", {"mentor": notify.first_name(m.name, "Your mentor")}, f"/mentors/{case.id}",
                  dedupe_key=f"case:{case.id}:accepted")
    return case_view(db, case)


def decline(db: Session, m: Mentor, case_id: str, reason: str) -> dict[str, Any]:
    case = _mine(db, m, case_id)
    if case.status != "matched":
        raise ConsoleError(409, "Only a new case can be declined.")
    if reason not in DECLINE_REASONS:
        raise ConsoleError(422, "Choose a reason.")
    _exclude_and_rematch(db, case, m.id, reason, actor_id=m.id, actor_role="mentor")
    return {"declined": True}


def send_message(db: Session, m: Mentor, case_id: str, text: str) -> dict[str, Any]:
    case = _mine(db, m, case_id)
    if case.status not in WORKING:
        raise ConsoleError(409, "You can message the learner once you have accepted the case, until the session outcome is recorded.")
    ok, why = escalation.screen_message(text)
    if not ok:
        db.add(CaseMessage(case_id=case.id, sender="mentor", text=text[:300], screened=False, blocked_reason=why, is_mock=False))
        db.flush()
        audit.record(db, actor_id=m.id, actor_role="mentor", action="message_blocked", subject_type="mentor_case", subject_id=case.id)
        return {"sent": False, "blocked": True, "reason": why}
    db.add(CaseMessage(case_id=case.id, sender="mentor", text=text.strip(), is_mock=False))
    case.updated_at = now()
    db.flush()
    notify.notify(db, case.learner_id, "case_message", {"name": notify.first_name(m.name, "Your mentor")}, f"/mentors/{case.id}",
                  dedupe_key=f"case:{case.id}:msg")
    return {"sent": True, "case": case_view(db, case)}


def mark_held(db: Session, m: Mentor, case_id: str) -> dict[str, Any]:
    case = _mine(db, m, case_id)
    if case.status not in ("accepted", "scheduled"):
        raise ConsoleError(409, "Accept the case first.")
    case.status, case.updated_at = "held", now()
    db.add(CaseMessage(case_id=case.id, sender="system", text="The session was held.", is_mock=False))
    db.flush()
    audit.record(db, actor_id=m.id, actor_role="mentor", action="case_held", subject_type="mentor_case", subject_id=case.id)
    return case_view(db, case)


def record_outcome(db: Session, m: Mentor, case_id: str, notes: str, next_step: str, demonstrated: int) -> dict[str, Any]:
    case = _mine(db, m, case_id)
    if case.status not in WORKING:
        raise ConsoleError(409, "The outcome can be recorded after you accepted the case, once.")
    if demonstrated not in DEMONSTRATED:
        raise ConsoleError(422, "Choose how well the learner showed they understand it (1 to 5).")
    if len((notes or "").strip()) < 10:
        raise ConsoleError(422, "Please write a few words about what you covered.")
    learner = db.get(Learner, case.learner_id)
    if learner is None:
        raise ConsoleError(404, "case not found")
    escalation.record_outcome(db, learner, case, notes.strip()[:1500], DEMONSTRATED[demonstrated], (next_step or "").strip()[:300])
    hooks.after_evidence(db, learner, case.concept_id, "your mentor session")       # the learner's roadmap updates; not returned to the mentor
    audit.record(db, actor_id=m.id, actor_role="mentor", action="case_outcome", subject_type="mentor_case", subject_id=case.id,
                 detail={"demonstrated": demonstrated})
    notify.notify(db, case.learner_id, "case_outcome", {"mentor": notify.first_name(m.name, "Your mentor")}, f"/mentors/{case.id}",
                  dedupe_key=f"case:{case.id}:outcome")
    return case_view(db, case)


def flag_concern(db: Session, m: Mentor, case_id: str, detail: str) -> dict[str, Any]:
    case = _mine(db, m, case_id)
    if len((detail or "").strip()) < 10:
        raise ConsoleError(422, "Please describe what worries you.")
    rep = SafeguardingReport(reporter_id=m.id, case_id=case.id, category="mentor_concern", detail=detail.strip()[:1000])
    db.add(rep)
    db.flush()
    audit.record(db, actor_id=m.id, actor_role="mentor", action="concern_flagged", subject_type="safeguarding_report", subject_id=rep.id)
    notify.notify_admins(db, "safeguarding_report", {}, "/admin", dedupe_key=f"report:{rep.id}")
    return {"report_id": rep.id, "message": "Thank you. A safeguarding lead will review this. If a learner is in immediate danger, contact local emergency services."}


# ---------------------------------------------------------------------------------------------------
# safeguarding lead
# ---------------------------------------------------------------------------------------------------

def list_reports(db: Session, status: Optional[str]) -> list[dict[str, Any]]:
    q = select(SafeguardingReport)
    if status:
        q = q.where(SafeguardingReport.status == status)
    return [{"id": r.id, "category": r.category, "detail": r.detail, "case_id": r.case_id, "reporter_id": r.reporter_id,
             "status": r.status, "created_at": r.created_at.isoformat(timespec="minutes")}
            for r in db.scalars(q.order_by(SafeguardingReport.created_at.desc()).limit(200))]


def resolve_report(db: Session, admin_id: str, report_id: str, note: str) -> dict[str, Any]:
    r = db.get(SafeguardingReport, report_id)
    if r is None:
        raise ConsoleError(404, "Report not found.")
    if len((note or "").strip()) < 5:
        raise ConsoleError(422, "A note is required to close a report.")
    r.status = "resolved"
    db.flush()
    audit.record(db, actor_id=admin_id, actor_role="admin", action="report_resolved", subject_type="safeguarding_report", subject_id=r.id,
                 detail={"note": note.strip()[:500]})
    return {"id": r.id, "status": r.status}
