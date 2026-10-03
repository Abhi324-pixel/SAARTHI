"""Auth, profile, health, dashboard, graph, roadmap, genome, dev tools."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import adapters, privacy
from ..config import settings
from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..engines import escalation, hooks, mastery, mentor_console, misconception, planner, safeguarding, strategy, streak as streak_engine, progress as progress_engine, phases as phases_engine
from ..llm import gateway
from ..models import (EvidenceEvent, Learner, Mentor, LearnerCorrection, MentorCase, StrategyOutcome, MisconceptionInstance,
                      ConceptState, RoadmapVersion, LearningSession)
from ..voice import elevenlabs

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------------------------------
# health / public
# ---------------------------------------------------------------------------------------------------

@router.get("/health")
def health():
    c = get_content()
    return {
        "ok": True, "env": settings.env, "llm": gateway.status(), "voice": elevenlabs.status(),
        "adapters": adapters.describe(), "content_version": c.version,
        "content_review": "AI-drafted, pending human review" if "pending-review" in c.version else "reviewed",
        "counts": {"concepts": len(c.concepts), "items": len(c.items), "sql_tasks": len(c.tasks),
                   "misconceptions": len(c.misconceptions), "rubrics": len(c.rubrics)},
        "test_llm": settings.llm_mode == "fake",
    }


@router.get("/roles")
def roles():
    c = get_content()
    return [{"id": r["id"], "title": r["title"], "title_hi": r["title_hi"], "blurb": r["blurb"], "available": r["available"]}
            for r in c.roles.values()]


class LoginIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    age: int = Field(ge=10, le=100)
    language: str = "english"
    email: Optional[str] = None


@router.post("/auth/dev-login")
def dev_login(body: LoginIn, db: Session = Depends(get_db)):
    prov = adapters.auth()
    if not prov.is_mock:
        raise HTTPException(400, "Sign-in happens through Supabase Auth in the browser.")
    out = prov.login(db, name=body.name, age=body.age, language=body.language, email=body.email)
    return out


# ---------------------------------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------------------------------

def _me(db: Session, lr: Learner) -> dict[str, Any]:
    return {
        "id": lr.id, "name": lr.name, "age": lr.age, "is_minor": safeguarding.is_minor(lr), "age_confirmed": safeguarding.age_confirmed(lr),
        "needs_profile": not safeguarding.age_confirmed(lr), "is_admin": lr.id in settings.admin_ids, "is_mentor": mentor_console.mentor_allowed(db.get(Mentor, lr.id)), "language": lr.language_pref,
        "role_id": lr.role_id, "weekly_hours": lr.weekly_hours, "horizon_weeks": lr.horizon_weeks,
        "onboarded": lr.onboarded, "is_mock": lr.is_mock,
        "consent": {"mentor_sessions": adapters.consent().status(db, lr, "mentor_sessions"),
                    "transcript_share": adapters.consent().status(db, lr, "transcript_share")},
        "clock_offset_days": lr.clock_offset_days,
    }


@router.get("/me")
def me(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return _me(db, lr)


class OnboardIn(BaseModel):
    role_id: str = "backend_developer"
    weekly_hours: float = Field(default=6.0, ge=1, le=60)
    horizon_weeks: int = Field(default=12, ge=2, le=52)
    language: Optional[str] = None


@router.post("/me/onboard")
def onboard(body: OnboardIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    c = get_content()
    role = c.roles.get(body.role_id)
    if not role or not role["available"]:
        raise HTTPException(400, "That role is not available yet.")
    lr.role_id = body.role_id
    lr.weekly_hours = body.weekly_hours
    lr.horizon_weeks = body.horizon_weeks
    if body.language in ("english", "hindi", "hinglish"):
        lr.language_pref = body.language
    lr.onboarded = True
    mastery.ensure_states(db, lr)
    rm = planner.refresh(db, lr, "setup")
    return {"me": _me(db, lr), "roadmap": {"version": rm["version"], "summary": rm["summary"]}}


class PrefsIn(BaseModel):
    language: Optional[str] = None
    weekly_hours: Optional[float] = Field(default=None, ge=1, le=60)
    horizon_weeks: Optional[int] = Field(default=None, ge=2, le=52)


@router.patch("/me")
def update_me(body: PrefsIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    if body.language in ("english", "hindi", "hinglish"):
        lr.language_pref = body.language
    if body.weekly_hours:
        lr.weekly_hours = body.weekly_hours
    if body.horizon_weeks:
        lr.horizon_weeks = body.horizon_weeks
    if body.weekly_hours or body.horizon_weeks:
        planner.refresh(db, lr, "your new schedule")
    return _me(db, lr)


@router.get("/me/export")
def export_me(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    ev = db.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == lr.id).order_by(EvidenceEvent.created_at))
    return {
        "profile": _me(db, lr),
        "concepts": mastery.concept_views(db, lr),
        "evidence": [{"concept": e.concept_id, "source": e.source_type, "score": e.score, "correct": e.correct,
                      "grader": e.grader, "at": e.created_at.isoformat()} for e in ev],
        "misconceptions": misconception.describe(db, lr.id),
        "more": privacy.export_all(db, lr),     # data added by feature specs (models_ext/*.py register themselves)
    }


@router.delete("/me")
def delete_me(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    privacy.delete_all(db, lr)
    db.delete(lr)
    db.flush()
    return {"deleted": True}


# ---------------------------------------------------------------------------------------------------
# graph + dashboard
# ---------------------------------------------------------------------------------------------------

def _graph(db: Session, lr: Learner) -> dict[str, Any]:
    c = get_content()
    views = mastery.concept_views(db, lr)
    req = c.role(lr.role_id or "backend_developer")["requirements"]
    nodes = []
    for cid in c.order:
        v = views[cid]
        nodes.append({"id": cid, "name": c.concepts[cid].name, "name_hi": c.concepts[cid].name_hi,
                      "domain": c.concepts[cid].domain, "level": v["level"], "p": v["p"], "confidence": v["confidence"],
                      "flags": v["flags"], "in_role": cid in req, "target": req.get(cid, {}).get("target"),
                      "has_rubric": c.has_rubric(cid), "n_tasks": len(c.tasks_by_concept.get(cid, [])),
                      "n_items": len(c.items_by_concept.get(cid, [])), "misconceptions": v["misconceptions"]})
    edges = [{"from": p, "to": cid} for cid in c.order for p in c.concepts[cid].prereqs]
    return {"nodes": nodes, "edges": edges}


@router.get("/graph")
def graph(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return _graph(db, lr)


def _calibration(db: Session, lr: Learner) -> dict[str, Any]:
    rows = list(db.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == lr.id,
                                                        EvidenceEvent.stated_confidence.is_not(None),
                                                        EvidenceEvent.score.is_not(None))))
    bins = {"low": [0, 0], "mid": [0, 0], "high": [0, 0]}
    for e in rows:
        b = "low" if e.stated_confidence <= 2 else "mid" if e.stated_confidence == 3 else "high"
        bins[b][0] += 1
        bins[b][1] += 1 if e.score >= 0.6 else 0
    out = {k: {"n": v[0], "correct": v[1], "accuracy": round(v[1] / v[0], 2) if v[0] else None} for k, v in bins.items()}
    high = out["high"]
    msg = None
    if high["n"] >= 3 and high["accuracy"] is not None and high["accuracy"] < 0.6:
        msg = f"When you feel very sure, you are right {int(high['accuracy']*100)}% of the time — double-check confident answers."
    elif out["low"]["n"] >= 3 and out["low"]["accuracy"] is not None and out["low"]["accuracy"] >= 0.7:
        msg = "You often know more than you think — trust yourself a little more."
    return {"bins": out, "message": msg, "n": len(rows)}


@router.get("/dashboard")
def dashboard(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    c = get_content()
    role = c.role(lr.role_id or "backend_developer")
    views = mastery.concept_views(db, lr)
    rm = planner.current(db, lr)
    mis = misconception.describe(db, lr.id)
    cases = list(db.scalars(select(MentorCase).where(MentorCase.learner_id == lr.id).order_by(MentorCase.created_at.desc()).limit(5)))
    levels = {k: 0 for k in mastery.LEVELS}
    for cid in role["requirements"]:
        levels[views[cid]["level"]] += 1
    n_evidence = db.scalar(select(EvidenceEvent.id).where(EvidenceEvent.learner_id == lr.id).limit(1))
    return {
        "me": _me(db, lr),
        "overall": mastery.overall_mastery(views, role["requirements"]),
        "levels": levels, "role": {"id": role["id"], "title": role["title"]},
        "graph": _graph(db, lr), "misconceptions": mis, "mission": planner.today_mission(db, lr, rm),
        "roadmap": {"version": rm["version"], "summary": rm["summary"], "change_reason": rm["change_reason"],
                    "diff": rm["diff"], "next": [i for i in rm["items"] if i["status"] != "done"][:4]},
        "calibration": _calibration(db, lr),
        "cases": [escalation.case_view(db, k, with_messages=False) for k in cases],
        "due_reviews": sum(1 for v in views.values() if v["due_for_review"]),
        "has_evidence": n_evidence is not None,
        "escalation_suggestions": escalation.check_triggers(db, lr),
        "streak": {**streak_engine.for_learner(db, lr), "show": bool((lr.settings or {}).get("streak_show", True))},   # the card hides itself without this flag
        "sparkline": progress_engine.sparkline(db, lr, n_days=14),
    }


# ---------------------------------------------------------------------------------------------------
# roadmap
# ---------------------------------------------------------------------------------------------------

@router.get("/roadmap")
def roadmap(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    rm = planner.current(db, lr)
    for it in rm["items"]:
        it["why"] = planner.why_text(it, lr.language_pref)
    versions = list(db.scalars(select(RoadmapVersion).where(RoadmapVersion.learner_id == lr.id).order_by(RoadmapVersion.version.desc()).limit(6)))
    plan_start = phases_engine.get_plan_start(lr, db)
    views = mastery.concept_views(db, lr)
    today = mastery.learner_now(lr).date()
    phase_list = phases_engine.phases(
        rm["items"],
        plan_start=plan_start,
        deadlines=(lr.settings or {}).get("deadlines", {}),
        weekly_hours=lr.weekly_hours or 6.0,
        today=today,
        views=views,
    )
    return {
        **rm,
        "phases": phase_list,
        "history": [{"version": v.version, "reason": v.change_reason, "at": v.created_at.isoformat(timespec="minutes"),
                     "diff": v.diff} for v in versions],
    }


@router.post("/roadmap/refresh")
def roadmap_refresh(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return planner.refresh(db, lr, "a manual refresh", force=False)


class WhatIfIn(BaseModel):
    weekly_hours: float = Field(ge=1, le=60)
    horizon_weeks: int = Field(ge=2, le=52)


@router.post("/roadmap/what-if")
def what_if(body: WhatIfIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    out = planner.what_if(db, lr, body.weekly_hours, body.horizon_weeks)
    out["items"] = [{"concept_id": i["concept_id"], "title": i["title"], "week": i["week"], "minutes": i["minutes"]} for i in out["items"]]
    return out


@router.get("/roadmap/why-not/{concept_id}")
def why_not(concept_id: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        return planner.why_not(db, lr, concept_id)
    except KeyError:
        raise HTTPException(404, "unknown concept")


# ---------------------------------------------------------------------------------------------------
# genome (the learner-facing view of the Learner Twin)
# ---------------------------------------------------------------------------------------------------

@router.get("/genome")
def genome(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    c = get_content()
    views = mastery.concept_views(db, lr)
    req = c.role(lr.role_id or "backend_developer")["requirements"]
    assessed = [v for cid, v in views.items() if v["n_evidence"] > 0 and cid in req]
    strengths = sorted([v for v in assessed if v["level"] in ("proficient", "mastered")], key=lambda v: -v["p"])[:5]
    bottlenecks = sorted([v for v in assessed if v["level"] in ("unknown", "developing") and (v["flags"] or v["p"] < 0.5)],
                         key=lambda v: v["p"])[:5]
    outcomes = strategy.outcomes_summary(db, lr.id)
    events = list(db.scalars(select(EvidenceEvent).where(EvidenceEvent.learner_id == lr.id).order_by(EvidenceEvent.created_at.desc()).limit(25)))
    first = db.scalar(select(EvidenceEvent.created_at).where(EvidenceEvent.learner_id == lr.id).order_by(EvidenceEvent.created_at).limit(1))
    return {
        "name": lr.name, "goal": c.role(lr.role_id or "backend_developer")["title"], "weekly_hours": lr.weekly_hours,
        "strengths": [{"concept_id": v["concept_id"], "name": v["name"], "level": v["level"], "p": v["p"]} for v in strengths],
        "bottlenecks": [{"concept_id": v["concept_id"], "name": v["name"], "level": v["level"], "p": v["p"], "flags": v["flags"]} for v in bottlenecks],
        "misconceptions": misconception.describe(db, lr.id),
        "strategies": [{"strategy": k, "label": strategy.LABELS.get(k, k), **v} for k, v in outcomes.items()],
        "strategy_note": "Shown only as evidence per concept. SAARTHI does not label you with a 'learning style'.",
        "calibration": _calibration(db, lr),
        "evidence": [{"id": e.id, "concept_id": e.concept_id, "concept": c.concepts[e.concept_id].name, "source": e.source_type,
                      "score": e.score, "correct": e.correct, "moved": e.changed_mastery, "grader": e.grader,
                      "p_before": e.p_before, "p_after": e.p_after, "confidence": e.stated_confidence,
                      "at": e.created_at.isoformat(timespec="minutes")} for e in events],
        "since": first.isoformat(timespec="minutes") if first else None,
        "corrections": [{"id": x.id, "concept_id": x.concept_id, "kind": x.kind, "status": x.status, "resolution": x.resolution}
                        for x in db.scalars(select(LearnerCorrection).where(LearnerCorrection.learner_id == lr.id).order_by(LearnerCorrection.created_at.desc()).limit(10))],
    }


class DisputeIn(BaseModel):
    concept_id: str
    kind: str = "dispute_level"  # dispute_level | already_know
    note: str = ""


@router.post("/genome/dispute")
def dispute(body: DisputeIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    c = get_content()
    if body.concept_id not in c.concepts:
        raise HTTPException(404, "unknown concept")
    cs = mastery.ensure_states(db, lr)[body.concept_id]
    cs.disputed = True
    corr = LearnerCorrection(learner_id=lr.id, concept_id=body.concept_id, kind=body.kind, note=body.note[:400],
                             resolution="Quick re-check offered: answer a short question to update this estimate.")
    db.add(corr)
    db.flush()
    from ..engines import diagnostic
    probe = diagnostic.next_probe(db, lr, count=1, concept_id=body.concept_id)
    return {"correction_id": corr.id, "message": "Thanks - your correction is recorded and shown with the estimate. "
            "A short re-check will update it with real evidence.", "recheck": probe[0] if probe else None}


# ---------------------------------------------------------------------------------------------------
# dev tools (disabled when SAARTHI_ENV=prod)
# ---------------------------------------------------------------------------------------------------

def _dev_only():
    if settings.is_prod:
        raise HTTPException(404, "Not found")


class AdvanceIn(BaseModel):
    days: float = Field(ge=0, le=365)


@router.post("/dev/advance-time")
def advance_time(body: AdvanceIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Demo helper: move this learner's clock forward so spaced review / delayed checks can be shown."""
    _dev_only()
    lr.clock_offset_days = (lr.clock_offset_days or 0.0) + body.days
    rm = planner.refresh(db, lr, f"{body.days:g} days passing")
    return {"clock_offset_days": lr.clock_offset_days, "roadmap": {"version": rm["version"], "changed": rm["changed"],
                                                                   "diff": rm["diff"], "reason": rm["change_reason"]}}


class SimStruggleIn(BaseModel):
    concept_id: str = "sql_outer_join"


@router.post("/dev/simulate-struggle")
def simulate_struggle(body: SimStruggleIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Demo helper: records a realistic persistent failure (3 failed attempts, 2 teaching strategies tried)
    so the mentor-handoff flow can be shown without waiting. Everything it writes is labelled `simulated`."""
    _dev_only()
    c = get_content()
    if body.concept_id not in c.concepts:
        raise HTTPException(404, "unknown concept")
    for i in range(3):
        mastery.apply_evidence(db, lr, body.concept_id, "work_product", correct=False, item_id=f"sim_{i}",
                               grader="simulated", detail={"simulated": True})
    for st in ("analogy", "worked_example"):
        v = mastery.concept_views(db, lr)[body.concept_id]
        db.add(StrategyOutcome(learner_id=lr.id, concept_id=body.concept_id, cluster=c.concepts[body.concept_id].domain,
                               strategy=st, p_before=v["p"], p_after=v["p"], gain=0.0))
    db.flush()
    return {"simulated": True, "after": hooks.after_evidence(db, lr, body.concept_id, "repeated attempts on " + c.concepts[body.concept_id].name)}


DEMO_HISTORY = [
    # (concept, source, score, count)  - a learner who knows Python basics, some SQL, and has not met HTTP yet
    ("py_basics", "work_product", 1.0, 3), ("py_functions", "question", 1.0, 2), ("py_collections", "question", 1.0, 2),
    ("git_basics", "question", 1.0, 2), ("sql_relational_model", "question", 1.0, 3), ("sql_select", "work_product", 1.0, 3),
    ("sql_filtering", "question", 1.0, 2), ("sql_sorting_limit", "question", 1.0, 2), ("sql_aggregates", "question", 1.0, 1),
    ("sql_null", "question", 0.0, 1), ("http_basics", "question", 0.0, 1),
]


@router.post("/dev/seed-demo")
def seed_demo(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    """Demo helper: give this learner a believable starting history (labelled `simulated` in the evidence log),
    so a live demo can jump straight to the interesting part - the LEFT JOIN misconception."""
    _dev_only()
    for cid, src, score, n in DEMO_HISTORY:
        for i in range(n):
            mastery.apply_evidence(db, lr, cid, src, score=score, item_id=f"demo_{cid}_{i}", grader="simulated",
                                   stated_confidence=3, detail={"simulated": True})
    rm = planner.refresh(db, lr, "your earlier practice")
    return {"seeded": True, "roadmap": {"version": rm["version"], "reason": rm["change_reason"]}}


@router.post("/dev/reset")
def reset_me(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    _dev_only()
    for model in (EvidenceEvent, MisconceptionInstance, ConceptState, RoadmapVersion, StrategyOutcome, LearnerCorrection):
        db.execute(delete(model).where(model.learner_id == lr.id))
    for k in db.scalars(select(MentorCase).where(MentorCase.learner_id == lr.id)):
        db.delete(k)
    lr.clock_offset_days = 0.0
    db.flush()
    mastery.ensure_states(db, lr)
    planner.refresh(db, lr, "reset")
    return {"reset": True}
