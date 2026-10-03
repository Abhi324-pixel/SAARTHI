"""Chhatrachhaya mentor layer: triggers, routing, matching, case report, lifecycle, screening.

Routing is rule-based and explainable:
  technical  -> Skill Mentor      (persistent concept failure, unresolved misconception, learner asks about code)
  career     -> Margdarshak       (career choice, interview behaviour, motivation, study habits)
  wellbeing  -> Safeguarding lead (never an ordinary mentor ticket)
Mentors are MOCK today (adapter), but every rule below is the real rule.
"""

from __future__ import annotations

from datetime import timedelta
import re
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import adapters
from ..adapters.base import MentorRecord
from ..content import get_content
from ..models_ext.C02 import CaseExclusion
from ..models import (CaseMessage, Learner, MentorCase, SafeguardingReport, StrategyOutcome, EvidenceEvent,
                      LearningSession, TranscriptTurn, now)
from . import mastery, misconception, notify, safeguarding

HELPLINE = {"name": "Tele-MANAS (India, free, 24x7)", "number": "14416"}
ACTIVE_STATUSES = ("open", "matched", "accepted", "scheduled", "held", "followup", "awaiting_consent")

PERSISTENT_ATTEMPTS = 3
PERSISTENT_STRATEGIES = 2
MISCONCEPTION_CYCLES = 2

_CAREER_WORDS = ("career", "job", "interview", "resume", "cv", "salary", "which field", "future", "college", "degree", "motivation", "demotivated")
_WELLBEING_WORDS = ("suicide", "kill myself", "end my life", "self harm", "self-harm", "hurt myself", "abuse", "abused", "hopeless", "can't go on", "cant go on", "want to die")
_CONTACT = re.compile(r"(\+?\d[\d\s\-]{8,}\d)|([\w.\-]+@[\w\-]+\.\w+)|(https?://\S+)|\b(whatsapp|telegram|instagram|snapchat|call me|my number)\b", re.I)


def classify_category(text: str) -> str:
    t = text.lower()
    if any(w in t for w in _WELLBEING_WORDS):
        return "wellbeing"
    if any(w in t for w in _CAREER_WORDS):
        return "career"
    return "technical"


def screen_message(text: str) -> tuple[bool, Optional[str]]:
    """Mentor-case messages must not carry personal contact details (platform safety rule)."""
    if _CONTACT.search(text):
        return False, "Personal contact details can't be shared here. Keep the conversation inside SAARTHI."
    if len(text.strip()) == 0:
        return False, "Message is empty."
    return True, None


# ---------------------------------------------------------------------------------------------------
# triggers
# ---------------------------------------------------------------------------------------------------

def check_triggers(db: Session, learner: Learner) -> list[dict[str, Any]]:
    c = get_content()
    views = mastery.concept_views(db, learner)
    out: list[dict[str, Any]] = []
    open_concepts = {mc.concept_id for mc in db.scalars(select(MentorCase).where(
        MentorCase.learner_id == learner.id, MentorCase.status.in_(ACTIVE_STATUSES)))}
    for cid, v in views.items():
        if cid in open_concepts:
            continue
        strategies = {r for r in db.scalars(select(StrategyOutcome.strategy).where(
            StrategyOutcome.learner_id == learner.id, StrategyOutcome.concept_id == cid))}
        if v["n_evidence"] >= PERSISTENT_ATTEMPTS and v["level"] in ("unknown", "not_assessed") or \
                (v["n_evidence"] >= PERSISTENT_ATTEMPTS and v["p"] < 0.4):
            if cid.startswith("comm_"):
                out.append({"trigger": "persistent_struggle", "category": "career", "concept_id": cid,
                            "reason": f"Still below 'developing' on {c.concepts[cid].name} after {v['n_evidence']} attempts. A Margdarshak can help with interview behaviour and communication practice."})
            elif len(strategies) >= PERSISTENT_STRATEGIES:
                out.append({"trigger": "persistent_struggle", "category": "technical", "concept_id": cid,
                            "reason": f"Still below 'developing' on {c.concepts[cid].name} after {v['n_evidence']} attempts and {len(strategies)} different teaching approaches."})
    for m in misconception.describe(db, learner.id):
        if m["concept_id"] in open_concepts:
            continue
        if m["cycles"] >= MISCONCEPTION_CYCLES:
            out.append({"trigger": "unresolved_misconception", "category": "technical", "concept_id": m["concept_id"],
                        "reason": f"The misconception '{m['name']}' came back after {m['cycles']} correction cycles."})
    return out


# ---------------------------------------------------------------------------------------------------
# report, matching, lifecycle
# ---------------------------------------------------------------------------------------------------

def build_report(db: Session, learner: Learner, category: str, concept_id: Optional[str], trigger: str, reason: str,
                 learner_note: str, share_transcript: bool) -> dict[str, Any]:
    c = get_content()
    views = mastery.concept_views(db, learner)
    report: dict[str, Any] = {
        "learner": {"first_name": learner.name.split()[0] if learner.name else "Learner", "age_band": "under_18" if safeguarding.is_minor(learner) else "adult",
                    "language": learner.language_pref, "goal": c.role(learner.role_id or "backend_developer")["title"]},
        "category": category, "trigger": trigger, "reason": reason, "learner_note": learner_note,
    }
    if concept_id and concept_id in c.concepts:
        v = views[concept_id]
        events = list(db.scalars(select(EvidenceEvent).where(
            EvidenceEvent.learner_id == learner.id, EvidenceEvent.concept_id == concept_id)
            .order_by(EvidenceEvent.created_at.desc()).limit(8)))
        outcomes = list(db.scalars(select(StrategyOutcome).where(
            StrategyOutcome.learner_id == learner.id, StrategyOutcome.concept_id == concept_id)))
        mis = [m for m in misconception.describe(db, learner.id) if m["concept_id"] == concept_id]
        weakest_prereqs = [{"concept": c.concepts[p].name, "level": views[p]["level"]} for p in c.prereqs(concept_id)
                           if views[p]["n_evidence"] > 0]
        report["concept"] = {"id": concept_id, "name": c.concepts[concept_id].name, "level": v["level"], "p": v["p"],
                             "confidence": v["confidence"], "flags": v["flags"]}
        report["evidence_timeline"] = [{"source": e.source_type, "correct": e.correct, "item": e.item_id,
                                        "at": e.created_at.isoformat(timespec="minutes")} for e in reversed(events)]
        report["misconceptions"] = [{"name": m["name"], "status": m["status"], "cycles": m["cycles"],
                                     "learner_statement": m["statement"]} for m in mis]
        report["strategies_tried"] = [{"strategy": o.strategy, "gain": o.gain} for o in outcomes]
        report["prerequisite_state"] = weakest_prereqs
        sugg = []
        if mis:
            sugg.append(f"Work through a contrasting example for '{mis[0]['name']}', then ask the learner to predict the output before running.")
        elif weakest_prereqs and any(w["level"] in ("unknown", "developing") for w in weakest_prereqs):
            sugg.append("Check the weak prerequisite first; the difficulty here may come from there.")
        else:
            sugg.append("Ask the learner to talk through one failing query line by line.")
        report["suggested_intervention"] = sugg
    if share_transcript:
        sess = db.scalars(select(LearningSession).where(LearningSession.learner_id == learner.id)
                          .order_by(LearningSession.created_at.desc())).first()
        if sess:
            turns = list(db.scalars(select(TranscriptTurn).where(TranscriptTurn.session_id == sess.id)
                                    .order_by(TranscriptTurn.created_at.desc()).limit(6)))
            report["transcript_excerpts"] = [{"role": t.role, "text": t.text[:240]} for t in reversed(turns)]
    report["shared"] = {"transcript": share_transcript}
    return report


def _tags_for(category: str, concept_id: Optional[str]) -> list[str]:
    tags: list[str] = []
    if category == "career":
        return ["career", "interview", "motivation"]
    if concept_id:
        tags.append(concept_id)
        if concept_id.startswith("sql_"):
            tags.append("sql")
        if concept_id.startswith("comm_"):
            tags.append("interview")
    return tags or ["sql"]


def _active_load(db: Session, mentor_id: str) -> int:
    return db.scalar(select(func.count()).select_from(MentorCase).where(
        MentorCase.mentor_id == mentor_id, MentorCase.status.in_(ACTIVE_STATUSES))) or 0


def match_mentor(db: Session, learner: Learner, category: str, concept_id: Optional[str],
                 exclude: frozenset = frozenset()) -> Optional[tuple[MentorRecord, list[str]]]:
    tier = "margdarshak" if category == "career" else "skill_mentor"
    tags = _tags_for(category, concept_id)
    c = get_content()
    best: Optional[tuple[float, MentorRecord, list[str]]] = None
    for m in adapters.mentors().list(db, tier):
        if m.verification_status != "verified" or m.id in exclude:
            continue
        if safeguarding.is_minor(learner) and not m.is_mock:
            from . import mentor_apply          # policy: real mentors need identity + reference + police verification for under-18 learners
            if not mentor_apply.has_minor_checks(db, m.id):
                continue
        load = _active_load(db, m.id)
        if load >= m.active_case_cap:
            continue
        score = 0.0
        reasons: list[str] = []
        exact = [t for t in tags if t in m.expertise]
        if concept_id and concept_id in m.expertise:
            score += 3
            reasons.append(f"Specialises in {c.concepts[concept_id].name}")
        elif exact:
            score += 2
            reasons.append("Covers " + ", ".join(t.replace('_', ' ') for t in exact[:2]))
        lang_ok = learner.language_pref in m.languages or (learner.language_pref == "hinglish" and ("hindi" in m.languages or "english" in m.languages))
        if lang_ok:
            score += 2
            reasons.append(f"Speaks {learner.language_pref.capitalize() if learner.language_pref != 'hinglish' else 'Hindi/English'}")
        if m.availability:
            score += 1
            reasons.append(f"Free {m.availability[0]}")
        score -= 0.25 * load
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, m, reasons)
    return (best[1], best[2]) if best else None


def open_case(db: Session, learner: Learner, *, category: str, concept_id: Optional[str], trigger: str, reason: str,
              learner_note: str = "", share_transcript: bool = False) -> dict[str, Any]:
    """Create a case. Wellbeing goes to the safeguarding path; minors need guardian consent first."""
    c = get_content()
    if category == "wellbeing":
        rep = SafeguardingReport(reporter_id=learner.id, category="wellbeing", detail=(learner_note or reason)[:500])
        db.add(rep)
        db.flush()
        notify.notify_admins(db, "safeguarding_report", {}, "/admin", dedupe_key=f"report:{rep.id}")
        case = MentorCase(learner_id=learner.id, tier="safeguarding", category="wellbeing", concept_id=None, trigger=trigger,
                          status="escalated", report={"note": "Safeguarding lead notified. No mentor session was created."},
                          is_mock=True)
        db.add(case)
        db.flush()
        return {"case_id": case.id, "status": "escalated", "category": "wellbeing", "tier": "safeguarding",
                "helpline": HELPLINE, "safeguarding_report_id": rep.id,
                "message": "I'm glad you told us. A trained safeguarding lead has been notified. If you feel unsafe right now, "
                           f"please call {HELPLINE['number']} ({HELPLINE['name']}) or a trusted adult."}
    if category not in ("technical", "career"):
        raise ValueError("unknown category")
    existing = db.scalars(select(MentorCase).where(MentorCase.learner_id == learner.id, MentorCase.category == category,
                                                   MentorCase.concept_id == concept_id,
                                                   MentorCase.status.in_(ACTIVE_STATUSES))).first()
    if existing:
        return {"case_id": existing.id, "status": existing.status, "duplicate": True, "category": category,
                "tier": existing.tier, "message": "You already have an open case for this."}
    tier = "margdarshak" if category == "career" else "skill_mentor"
    report = build_report(db, learner, category, concept_id, trigger, reason, learner_note, share_transcript)
    v = mastery.concept_views(db, learner).get(concept_id) if concept_id in c.concepts else None
    case = MentorCase(learner_id=learner.id, tier=tier, category=category, concept_id=concept_id, trigger=trigger,
                      status="open", report=report, p_at_open=v["p"] if v else None, is_mock=adapters.mentors().is_mock)
    db.add(case)
    db.flush()
    consent = adapters.consent().status(db, learner, "mentor_sessions")
    if consent != "granted":
        case.status = "awaiting_consent"
        db.flush()
        req = adapters.consent().request(db, learner, "mentor_sessions")
        return {"case_id": case.id, "status": "awaiting_consent", "category": category, "tier": tier,
                "consent_required": True, "guardian_token": req.get("guardian_token") if adapters.consent().is_mock else None,
                "message": "Because you are under 18, a parent or guardian must approve mentor sessions first.",
                "mock_consent": adapters.consent().is_mock}
    return _match_and_accept(db, learner, case)


def _match_and_accept(db: Session, learner: Learner, case: MentorCase) -> dict[str, Any]:
    declined = frozenset(db.scalars(select(CaseExclusion.mentor_id).where(CaseExclusion.case_id == case.id)))
    found = match_mentor(db, learner, case.category, case.concept_id, declined)
    if not found:
        case.status = "open"
        db.flush()
        return {"case_id": case.id, "status": "open", "tier": case.tier, "category": case.category,
                "message": "All suitable mentors are busy right now. Your case is queued; I'll keep helping in the meantime."}
    mentor, reasons = found
    case.mentor_id = mentor.id
    case.match_reasons = reasons
    case.status = "accepted" if adapters.mentors().is_mock else "matched"
    case.scheduled_for = mentor.availability[0] if (mentor.availability and case.status == "accepted") else None
    case.updated_at = now()
    db.add(CaseMessage(case_id=case.id, sender="system", is_mock=adapters.mentors().is_mock,
                       text=f"Case opened and matched with {mentor.name}. " + ("(Demo mentor) " if mentor.is_mock else "")))
    db.flush()
    if case.status == "matched" and not mentor.is_mock:
        c = get_content()
        notify.notify(db, mentor.id, "case_assigned", {"concept": c.concepts[case.concept_id].name if case.concept_id in c.concepts else "Career guidance"},
                      f"/mentor-console/{case.id}", dedupe_key=f"case:{case.id}:assigned")
    return {"case_id": case.id, "status": case.status, "tier": case.tier, "category": case.category,
            "mentor": mentor.public(), "match_reasons": reasons, "scheduled_for": case.scheduled_for,
            "mock_mentor": mentor.is_mock}


def resume_after_consent(db: Session, learner: Learner) -> list[dict[str, Any]]:
    out = []
    for case in db.scalars(select(MentorCase).where(MentorCase.learner_id == learner.id, MentorCase.status == "awaiting_consent")):
        out.append(_match_and_accept(db, learner, case))
    return out


def case_view(db: Session, case: MentorCase, with_messages: bool = True) -> dict[str, Any]:
    mentor = adapters.mentors().get(db, case.mentor_id) if case.mentor_id else None
    c = get_content()
    d: dict[str, Any] = {
        "id": case.id, "status": case.status, "tier": case.tier, "category": case.category,
        "concept_id": case.concept_id, "concept_name": c.concepts[case.concept_id].name if case.concept_id in c.concepts else None,
        "trigger": case.trigger, "mentor": mentor.public() if mentor else None, "match_reasons": case.match_reasons or [],
        "scheduled_for": case.scheduled_for, "report": case.report, "outcome": case.outcome or None,
        "followup": case.followup or None, "created_at": case.created_at.isoformat(timespec="minutes"), "is_mock": case.is_mock,
    }
    if with_messages:
        msgs = db.scalars(select(CaseMessage).where(CaseMessage.case_id == case.id).order_by(CaseMessage.created_at))
        d["messages"] = [{"id": m.id, "sender": m.sender, "text": m.text, "is_mock": m.is_mock, "at": m.created_at.isoformat(timespec="minutes")}
                         for m in msgs if m.screened]
    return d


def send_message(db: Session, learner: Learner, case: MentorCase, text: str) -> dict[str, Any]:
    ok, why = screen_message(text)
    if not ok:
        db.add(CaseMessage(case_id=case.id, sender="learner", text=text[:300], screened=False, blocked_reason=why))
        db.flush()
        return {"sent": False, "blocked": True, "reason": why}
    db.add(CaseMessage(case_id=case.id, sender="learner", text=text.strip()))
    db.flush()
    reply = None
    if case.mentor_id and case.status in ("accepted", "scheduled", "held", "matched"):
        mentor = adapters.mentors().get(db, case.mentor_id)
        concept_name = get_content().concepts[case.concept_id].name if case.concept_id in get_content().concepts else "your goal"
        txt = adapters.responder().reply(mentor=mentor, case_category=case.category, concept_name=concept_name, learner_message=text) if mentor else None
        if txt:
            db.add(CaseMessage(case_id=case.id, sender="mentor", text=txt, is_mock=True))
            reply = txt
    case.updated_at = now()
    db.flush()
    if notify.recipient_is_real_account(case) and case.status in ("accepted", "scheduled", "held", "matched"):
        notify.notify(db, case.mentor_id, "case_message", {"name": notify.first_name(learner.name, "The learner")},
                      f"/mentor-console/{case.id}", dedupe_key=f"case:{case.id}:msg")
    return {"sent": True, "mentor_reply": reply, "mock_reply": bool(reply)}


def record_outcome(db: Session, learner: Learner, case: MentorCase, notes: str, rating: float, next_step: str) -> dict[str, Any]:
    """Mentor outcome becomes EVIDENCE with its own weight - mentors never set mastery directly."""
    case.outcome = {"notes": notes, "next_step": next_step, "mentor_rating": rating}
    case.status = "followup"
    case.updated_at = now()
    due_at = (mastery.learner_now(learner) + timedelta(days=3)).date().isoformat()
    case.followup = dict(case.followup or {}, due_at=due_at)
    ev = None
    if case.concept_id:
        ev = mastery.apply_evidence(db, learner, case.concept_id, "mentor", score=max(0.0, min(1.0, rating)),
                                    item_id=case.id, grader=f"mentor:{case.mentor_id}", detail={"notes": notes[:300]})
    db.add(CaseMessage(case_id=case.id, sender="system", text="Session outcome recorded. A short follow-up check will confirm it helped.", is_mock=case.is_mock))
    db.flush()
    return {"status": case.status, "mastery": ev}


def followup_check(db: Session, learner: Learner, case: MentorCase) -> dict[str, Any]:
    """Success is judged by the learner's later evidence, not by a star rating."""
    if not case.concept_id:
        return {"status": case.status}
    v = mastery.concept_views(db, learner)[case.concept_id]
    before = case.p_at_open or 0.0
    gain = round(v["p"] - before, 3)
    case.followup = {"p_at_open": before, "p_now": v["p"], "gain": gain, "improved": gain >= 0.1}
    case.status = "closed"
    case.updated_at = now()
    db.flush()
    return {"status": "closed", "followup": case.followup}
