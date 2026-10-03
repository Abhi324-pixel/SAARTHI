"""T05 — Roadmap phases, deadlines and personal checkpoints routes.

PUT    /api/phases/{key}/deadline     → set/update phase deadline
DELETE /api/phases/{key}/deadline     → clear phase deadline
POST   /api/phases/{key}/check        → generate mixed check for concepts in phase
GET    /api/checkpoints               → list learner personal checkpoints
POST   /api/checkpoints               → create personal checkpoint
PATCH  /api/checkpoints/{id}          → toggle free-text checkpoint done state
DELETE /api/checkpoints/{id}          → delete checkpoint
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..engines import diagnostic, mastery, phases as phases_engine, planner
from ..models import Learner
from ..models_ext.T05 import LearnerCheckpoint

router = APIRouter(prefix="/api")


class DeadlineIn(BaseModel):
    date: str  # YYYY-MM-DD


class CheckpointIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    due_date: Optional[str] = None  # YYYY-MM-DD
    concept_id: Optional[str] = None


@router.put("/phases/{key}/deadline")
def set_phase_deadline(
    key: str,
    body: DeadlineIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    try:
        dl_date = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(422, "Invalid date format. Expected YYYY-MM-DD.")

    today = mastery.learner_now(lr).date()
    if dl_date <= today:
        raise HTTPException(422, "Deadline must be in the future.")
    if (dl_date - today).days > 365 * 2:
        raise HTTPException(422, "Deadline cannot be more than 2 years in the future.")

    settings = dict(lr.settings or {})
    deadlines = dict(settings.get("deadlines") or {})
    deadlines[key] = body.date
    settings["deadlines"] = deadlines
    lr.settings = settings
    db.flush()

    rm = planner.current(db, lr)
    plan_start = phases_engine.get_plan_start(lr, db)
    views = mastery.concept_views(db, lr)
    phase_list = phases_engine.phases(
        rm["items"],
        plan_start=plan_start,
        deadlines=deadlines,
        weekly_hours=lr.weekly_hours or 6.0,
        today=today,
        views=views,
    )
    target_phase = next((p for p in phase_list if p["key"] == key), None)
    if not target_phase:
        raise HTTPException(404, f"Phase {key} not found in current roadmap.")

    return {
        "ok": True,
        "phase": target_phase,
        "deadline_status": target_phase.get("deadline_status"),
    }


@router.delete("/phases/{key}/deadline")
def delete_phase_deadline(
    key: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    settings = dict(lr.settings or {})
    deadlines = dict(settings.get("deadlines") or {})
    if key in deadlines:
        del deadlines[key]
        settings["deadlines"] = deadlines
        lr.settings = settings
        db.flush()
    return {"ok": True}


@router.post("/phases/{key}/check")
def phase_check(
    key: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    rm = planner.current(db, lr)
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
    target_phase = next((p for p in phase_list if p["key"] == key), None)
    if not target_phase:
        raise HTTPException(404, f"Phase {key} not found in roadmap.")

    content = get_content()
    role = content.role(lr.role_id or "backend_developer")
    req = role["requirements"]

    # Sort concepts weakest first, prioritizing those below target
    cids = target_phase["concept_ids"]
    scored = []
    for cid in cids:
        p = views.get(cid, {}).get("p", 0.0)
        tgt = req.get(cid, {}).get("target", 0.8)
        is_below = p < 0.95 * tgt
        scored.append((0 if is_below else 1, p, cid))
    scored.sort()

    # Collect up to 5 unseen MCQs
    items: list[dict[str, Any]] = []
    seen_ids = set()
    for _, _, cid in scored:
        if len(items) >= 5:
            break
        probes = diagnostic.next_probe(db, lr, count=1, concept_id=cid)
        for p in probes:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                items.append(p)
                if len(items) >= 5:
                    break

    return {
        "phase_key": key,
        "phase_title": target_phase["title"],
        "items": items,
        "count": len(items),
    }


# ---- Checkpoints CRUD --------------------------------------------------------

@router.get("/checkpoints")
def list_checkpoints(
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    content = get_content()
    views = mastery.concept_views(db, lr)
    role = content.role(lr.role_id or "backend_developer")
    req = role["requirements"]

    rows = list(db.scalars(
        select(LearnerCheckpoint)
        .where(LearnerCheckpoint.learner_id == lr.id)
        .order_by(LearnerCheckpoint.created_at.desc())
    ))

    result = []
    for cp in rows:
        if cp.concept_id:
            tgt = req.get(cp.concept_id, {}).get("target", 0.8)
            p = views.get(cp.concept_id, {}).get("p", 0.0)
            done = bool(p >= 0.95 * tgt)
            c_name = content.concepts[cp.concept_id].name if cp.concept_id in content.concepts else cp.concept_id
        else:
            done = cp.done_at is not None
            c_name = None

        result.append({
            "id": cp.id,
            "title": cp.title,
            "due_date": cp.due_date.isoformat() if cp.due_date else None,
            "concept_id": cp.concept_id,
            "concept_name": c_name,
            "done": done,
            "is_concept_linked": cp.concept_id is not None,
            "done_at": cp.done_at.isoformat() if cp.done_at else None,
            "created_at": cp.created_at.isoformat(),
        })

    return {"checkpoints": result}


@router.post("/checkpoints")
def create_checkpoint(
    body: CheckpointIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    content = get_content()
    if body.concept_id and body.concept_id not in content.concepts:
        raise HTTPException(404, f"Unknown concept {body.concept_id}")

    due = None
    if body.due_date:
        try:
            due = date.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(422, "Invalid due_date format. Expected YYYY-MM-DD.")

    cp = LearnerCheckpoint(
        learner_id=lr.id,
        title=body.title.strip(),
        due_date=due,
        concept_id=body.concept_id,
    )
    db.add(cp)
    db.flush()

    return {
        "id": cp.id,
        "title": cp.title,
        "due_date": cp.due_date.isoformat() if cp.due_date else None,
        "concept_id": cp.concept_id,
        "done": False,
        "is_concept_linked": cp.concept_id is not None,
        "created_at": cp.created_at.isoformat(),
    }


@router.patch("/checkpoints/{checkpoint_id}")
def toggle_checkpoint(
    checkpoint_id: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    cp = db.scalar(
        select(LearnerCheckpoint).where(
            LearnerCheckpoint.id == checkpoint_id,
            LearnerCheckpoint.learner_id == lr.id,
        )
    )
    if not cp:
        raise HTTPException(404, "Checkpoint not found")

    if cp.concept_id:
        raise HTTPException(
            409,
            "This checkpoint completes automatically when your check shows you've reached target mastery.",
        )

    now_dt = mastery.learner_now(lr)
    cp.done_at = None if cp.done_at else now_dt
    db.flush()

    return {
        "id": cp.id,
        "done": cp.done_at is not None,
        "done_at": cp.done_at.isoformat() if cp.done_at else None,
    }


@router.delete("/checkpoints/{checkpoint_id}")
def delete_checkpoint(
    checkpoint_id: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    cp = db.scalar(
        select(LearnerCheckpoint).where(
            LearnerCheckpoint.id == checkpoint_id,
            LearnerCheckpoint.learner_id == lr.id,
        )
    )
    if not cp:
        raise HTTPException(404, "Checkpoint not found")

    db.delete(cp)
    db.flush()
    return {"ok": True}
