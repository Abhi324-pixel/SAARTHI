"""Mentor applications: profile, subject screen, code-of-conduct pledge, human review (spec docs/features/C01).

Nothing here verifies a person automatically. The screen is an INPUT to a human decision; "verified" only ever comes from an
admin approving an application and recording which checks they really did (`mentor_checks`).
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..adapters.base import Principal
from ..config import CONTENT_DIR
from ..content import get_content
from ..models import Mentor, MentorCase, now
from ..models_ext.C01 import MentorApplication, MentorCheck
from . import audit, notify

TIERS = ("skill_mentor", "margdarshak")
LANGUAGES = ("english", "hindi", "hinglish")
EXTRA_TAGS = ("sql", "career", "interview", "motivation")      # tags the matcher already understands (escalation._tags_for)
CHECK_KINDS = ("identity", "reference", "interview", "police_verification")
MINOR_REQUIRED_CHECKS = ("identity", "reference", "police_verification")   # policy: all three before a mentor may take under-18 learners
SLOT = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([01]\d|2[0-3]):[0-5]\d$")
EDITABLE = ("draft", "needs_info")
SCREEN_MCQ = 5

OPEN_QUESTIONS = {
    "skill_mentor": [
        ("stuck_join", "A learner says: \"my LEFT JOIN drops customers who have no orders\". How would you help them find the cause without simply giving the answer?"),
    ],
    "margdarshak": [
        ("job_or_study", "A final-year student in a small town asks whether to take the first job offer or prepare for a master's. How do you advise them?"),
        ("interview_fear", "A first-generation graduate freezes in interviews. What would you suggest?"),
        ("hopeless", "A learner tells you they feel hopeless about their future. What do you do, and what do you not do?"),
    ],
}


class ApplyError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


@lru_cache(maxsize=1)
def pledge() -> dict[str, Any]:
    return json.loads((CONTENT_DIR / "mentor_pledge.json").read_text(encoding="utf-8"))


def allowed_expertise() -> set[str]:
    return set(get_content().concepts) | set(EXTRA_TAGS)


def get(db: Session, user_id: str) -> Optional[MentorApplication]:
    return db.scalars(select(MentorApplication).where(MentorApplication.user_id == user_id)).first()


def view(app: Optional[MentorApplication], *, admin: bool = False) -> Optional[dict[str, Any]]:
    if app is None:
        return None
    out = {"id": app.id, "status": app.status, "tier_requested": app.tier_requested, "name": app.name, "headline": app.headline,
           "bio": app.bio, "years_experience": app.years_experience, "organisation": app.organisation, "expertise": app.expertise,
           "languages": app.languages, "availability": app.availability, "screen_done": bool(app.screen_result.get("done")),
           "pledge_version": app.pledge_version, "pledge_current": app.pledge_version == pledge()["version"],
           "reviewer_note": app.reviewer_note if app.status in ("needs_info", "rejected", "approved") else "",
           "created_at": app.created_at.isoformat(timespec="minutes"), "updated_at": app.updated_at.isoformat(timespec="minutes")}
    if admin:
        out.update({"user_id": app.user_id, "email": app.email, "screen_result": app.screen_result,
                    "pledge_accepted_at": app.pledge_accepted_at.isoformat(timespec="minutes") if app.pledge_accepted_at else None})
    return out


def clean_profile(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise the profile fields that were provided (all optional in a draft)."""
    out: dict[str, Any] = {}
    if "tier_requested" in data:
        if data["tier_requested"] not in TIERS:
            raise ApplyError(422, "Choose Skill Mentor or Margdarshak.")
        out["tier_requested"] = data["tier_requested"]
    for key, limit in (("name", 120), ("headline", 120), ("organisation", 160)):
        if key in data:
            out[key] = re.sub(r"\s+", " ", str(data[key] or "")).strip()[:limit]
    if "bio" in data:
        out["bio"] = str(data["bio"] or "").strip()[:600]
    if "years_experience" in data:
        try:
            y = int(data["years_experience"])
        except (TypeError, ValueError):
            raise ApplyError(422, "Years of experience must be a number.")
        if not 0 <= y <= 60:
            raise ApplyError(422, "Years of experience must be between 0 and 60.")
        out["years_experience"] = y
    if "expertise" in data:
        tags = list(dict.fromkeys(str(t) for t in (data["expertise"] or [])))
        if len(tags) > 10 or any(t not in allowed_expertise() for t in tags):
            raise ApplyError(422, "Pick up to 10 topics from the list.")
        out["expertise"] = tags
    if "languages" in data:
        langs = list(dict.fromkeys(str(t) for t in (data["languages"] or [])))
        if not langs or any(t not in LANGUAGES for t in langs):
            raise ApplyError(422, "Choose at least one of English, Hindi, Hinglish.")
        out["languages"] = langs
    if "availability" in data:
        slots = list(dict.fromkeys(str(t) for t in (data["availability"] or [])))
        if len(slots) > 14 or any(not SLOT.match(t) for t in slots):
            raise ApplyError(422, "Availability slots look like 'Mon 18:00' (India time), at most 14.")
        out["availability"] = slots
    return out


def save_draft(db: Session, principal: Principal, data: dict[str, Any]) -> MentorApplication:
    app = get(db, principal.learner_id)
    fields = clean_profile(data)
    if app is None:
        app = MentorApplication(user_id=principal.learner_id, email=principal.email, name=principal.name or "")
        db.add(app)
    elif app.status not in EDITABLE:
        raise ApplyError(409, "This application can't be edited now." if app.status != "submitted" else "Your application is with a reviewer; you can edit it again if they ask for more information.")
    for k, v in fields.items():
        setattr(app, k, v)
    app.updated_at = now()
    db.flush()
    return app


def _screen_items(app: MentorApplication) -> list[dict[str, Any]]:
    """The MCQs for this application: drawn from the tags they claim (or SQL basics), deterministic per application."""
    c = get_content()
    concepts = [t for t in app.expertise if t in c.concepts]
    if not concepts:
        concepts = [cid for cid in c.concepts if cid.startswith("sql_")]
    pool = [i for cid in concepts for i in c.items_by_concept.get(cid, [])]
    pool.sort(key=lambda i: hashlib.sha1(f"{app.id}:{i['id']}".encode()).hexdigest())
    return pool[:SCREEN_MCQ]


def screen_questions(app: MentorApplication) -> dict[str, Any]:
    c = get_content()
    items = _screen_items(app) if app.tier_requested == "skill_mentor" else []
    return {"mcq": [c.public_item(i, app.id) for i in items],
            "open": [{"key": k, "prompt": p} for k, p in OPEN_QUESTIONS[app.tier_requested]]}


def submit_screen(db: Session, app: MentorApplication, answers: dict[str, int], open_answers: dict[str, str]) -> dict[str, Any]:
    if app.status not in EDITABLE:
        raise ApplyError(409, "This application can't be edited now.")
    c = get_content()
    graded = []
    for item in (_screen_items(app) if app.tier_requested == "skill_mentor" else []):
        idx = answers.get(item["id"])
        opts = c.shuffled_options(item, app.id)
        graded.append({"id": item["id"], "concept_id": item["concept_id"],
                       "correct": isinstance(idx, int) and 0 <= idx < len(opts) and bool(opts[idx].get("correct"))})
        if idx is None:
            raise ApplyError(422, "Please answer every multiple-choice question.")
    wanted = {k for k, _ in OPEN_QUESTIONS[app.tier_requested]}
    texts = {k: str(open_answers.get(k, "")).strip()[:1500] for k in wanted}
    if any(len(t) < 20 for t in texts.values()):
        raise ApplyError(422, "Please answer each open question in a few sentences.")
    app.screen_result = {"done": True, "at": now().isoformat(timespec="minutes"),
                         "mcq": {"asked": len(graded), "correct": sum(1 for g in graded if g["correct"]), "items": graded},
                         "open": texts}
    app.updated_at = now()
    db.flush()
    return {"mcq_correct": app.screen_result["mcq"]["correct"], "mcq_asked": len(graded)}   # not a pass/fail: a human reads it


def accept_pledge(db: Session, app: MentorApplication, version: str) -> None:
    if version != pledge()["version"]:
        raise ApplyError(409, "The code of conduct was updated; please read the current version.")
    app.pledge_version, app.pledge_accepted_at, app.updated_at = version, now(), now()
    db.flush()


def submit(db: Session, app: MentorApplication) -> MentorApplication:
    if app.status not in EDITABLE:
        raise ApplyError(409, "This application was already submitted.")
    problems = []
    if not app.name.strip():
        problems.append("name")
    if len(app.headline) < 10:
        problems.append("headline (at least 10 characters)")
    if len(app.bio) < 40:
        problems.append("short bio (at least 40 characters)")
    if not app.expertise:
        problems.append("at least one topic")
    if not app.languages:
        problems.append("languages")
    if not app.availability:
        problems.append("at least one availability slot")
    if not app.screen_result.get("done"):
        problems.append("the short screen")
    if app.pledge_version != pledge()["version"] or not app.pledge_accepted_at:
        problems.append("accepting the code of conduct")
    if problems:
        raise ApplyError(422, "Still missing: " + ", ".join(problems) + ".")
    app.status, app.updated_at = "submitted", now()
    db.flush()
    audit.record(db, actor_id=app.user_id, actor_role="applicant", action="mentor_application_submitted",
                 subject_type="mentor_application", subject_id=app.id)
    notify.notify_admins(db, "mentor_application", {}, "/admin", dedupe_key=f"app:{app.id}")
    return app


# ---------------------------------------------------------------------------------------------------
# admin (safeguarding lead)
# ---------------------------------------------------------------------------------------------------

def list_applications(db: Session, status: Optional[str] = None) -> list[dict[str, Any]]:
    q = select(MentorApplication)
    if status:
        q = q.where(MentorApplication.status == status)
    rows = db.scalars(q.order_by(MentorApplication.updated_at.desc()).limit(200))
    return [view(a, admin=True) for a in rows]


def decide(db: Session, admin_id: str, app_id: str, decision: str, note: str, checks: list[dict[str, str]]) -> dict[str, Any]:
    app = db.get(MentorApplication, app_id)
    if app is None:
        raise ApplyError(404, "Application not found.")
    if decision not in ("approve", "needs_info", "reject"):
        raise ApplyError(422, "Decision must be approve, needs_info or reject.")
    if not (note or "").strip():
        raise ApplyError(422, "A note is required with every decision.")
    if app.status not in ("submitted", "needs_info", "approved", "rejected"):
        raise ApplyError(409, "This application has not been submitted yet.")
    if decision == "approve":
        if app.status == "rejected":
            raise ApplyError(409, "A rejected application can't be approved; ask the applicant to apply again via 'needs info'.")
        for ch in checks:
            if ch.get("kind") not in CHECK_KINDS:
                raise ApplyError(422, f"Unknown check kind {ch.get('kind')!r}.")
        m = db.get(Mentor, app.user_id)
        if m is None:
            m = Mentor(id=app.user_id, is_mock=False)
            db.add(m)
        m.name, m.tier, m.headline, m.bio = app.name, app.tier_requested, app.headline, app.bio
        m.expertise, m.languages, m.availability = list(app.expertise), list(app.languages), list(app.availability)
        m.verification_status, m.is_mock = "verified", False
        for ch in checks:
            db.add(MentorCheck(mentor_id=app.user_id, kind=ch["kind"], done_by=admin_id, note=str(ch.get("note", ""))[:300]))
        app.status = "approved"
    else:
        app.status = "needs_info" if decision == "needs_info" else "rejected"
    app.reviewer_id, app.reviewer_note, app.updated_at = admin_id, note.strip()[:1000], now()
    db.flush()
    audit.record(db, actor_id=admin_id, actor_role="admin", action=f"mentor_application_{decision}", subject_type="mentor_application",
                 subject_id=app.id, detail={"checks": [c["kind"] for c in checks] if decision == "approve" else []})
    return view(app, admin=True)


def list_mentors(db: Session) -> list[dict[str, Any]]:
    out = []
    for m in db.scalars(select(Mentor).where(Mentor.is_mock.is_(False)).order_by(Mentor.name)):
        kinds = sorted({c.kind for c in db.scalars(select(MentorCheck).where(MentorCheck.mentor_id == m.id))})
        out.append({"id": m.id, "name": m.name, "tier": m.tier, "status": m.verification_status, "checks": kinds,
                    "can_take_minors": all(k in kinds for k in MINOR_REQUIRED_CHECKS)})
    return out


def has_minor_checks(db: Session, mentor_id: str) -> bool:
    kinds = {c.kind for c in db.scalars(select(MentorCheck).where(MentorCheck.mentor_id == mentor_id))}
    return all(k in kinds for k in MINOR_REQUIRED_CHECKS)


def suspend(db: Session, admin_id: str, mentor_id: str, note: str) -> dict[str, Any]:
    from . import escalation          # local import: escalation imports this module for the minors policy
    m = db.get(Mentor, mentor_id)
    if m is None or m.is_mock:
        raise ApplyError(404, "Mentor not found.")
    if not (note or "").strip():
        raise ApplyError(422, "A note is required.")
    m.verification_status = "suspended"
    moved = 0
    for case in db.scalars(select(MentorCase).where(MentorCase.mentor_id == mentor_id,
                                                    MentorCase.status.in_(("matched", "accepted", "scheduled")))):
        learner = db.get(escalation.Learner, case.learner_id)
        case.mentor_id, case.status, case.scheduled_for, case.updated_at = None, "open", None, now()
        db.flush()
        if learner is not None:
            escalation._match_and_accept(db, learner, case)          # re-match to someone else (or stay queued)
        moved += 1
    db.flush()
    audit.record(db, actor_id=admin_id, actor_role="admin", action="mentor_suspended", subject_type="mentor", subject_id=mentor_id,
                 detail={"cases_rematched": moved})
    return {"id": mentor_id, "status": "suspended", "cases_rematched": moved}
