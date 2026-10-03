"""Misconception lifecycle.

  candidate -> confirmed -> correcting -> pending_verify -> resolved
                  \\-> dismissed (learner said the read-back was wrong)

Detection channels and how they confirm:
  work_product : a wrong-output pattern from an executed query is objective -> confirmed immediately
  question     : the learner picked the option written for this misconception -> candidate; a second
                 independent signal confirms it
  explain_back : a statement in the transcript -> candidate with a READ-BACK statement; the learner's
                 yes/no confirms or dismisses it (speech can be mis-transcribed, so no silent flags)

A misconception is only `resolved` after a success AT LEAST `VERIFY_AFTER_DAYS` later (a delayed check).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import Learner, MisconceptionInstance
from .mastery import learner_now

VERIFY_AFTER_DAYS = 1.0
ACTIVE = ("confirmed", "correcting", "pending_verify")
OPEN = ("candidate",) + ACTIVE


def _find_open(db: Session, learner_id: str, misconception_id: str) -> Optional[MisconceptionInstance]:
    return db.scalars(select(MisconceptionInstance).where(
        MisconceptionInstance.learner_id == learner_id,
        MisconceptionInstance.misconception_id == misconception_id,
        MisconceptionInstance.status.in_(OPEN),
    )).first()


def register_signal(db: Session, learner: Learner, misconception_id: str, channel: str,
                    evidence_id: Optional[str] = None, statement: Optional[str] = None) -> dict[str, Any]:
    content = get_content()
    m = content.misconceptions[misconception_id]
    inst = _find_open(db, learner.id, misconception_id)
    now = learner_now(learner)
    created = False
    if inst is None:
        inst = MisconceptionInstance(learner_id=learner.id, concept_id=m["concept_id"], misconception_id=misconception_id,
                                     status="candidate", channel=channel, evidence_ids=[], detected_at=now)
        db.add(inst)
        created = True
    ids = list(inst.evidence_ids or [])
    if evidence_id:
        ids.append(evidence_id)
    inst.evidence_ids = ids
    prev = inst.status

    if channel == "work_product":
        if inst.status in ("candidate",):
            inst.status = "confirmed"
        elif inst.status == "pending_verify":
            inst.status = "confirmed"
            inst.cycles += 1
        elif inst.status in ("correcting",):
            inst.cycles += 1
    elif channel == "question":
        if inst.status == "candidate" and len(ids) >= 2:
            inst.status = "confirmed"
        elif inst.status == "pending_verify":
            inst.status = "confirmed"
            inst.cycles += 1
    elif channel == "explain_back":
        inst.statement = statement or inst.statement
        if inst.status == "pending_verify":
            inst.status = "confirmed"
            inst.cycles += 1
    db.flush()
    return {
        "instance_id": inst.id, "misconception_id": misconception_id, "name": m["name"], "status": inst.status,
        "created": created, "status_changed": prev != inst.status, "needs_readback": channel == "explain_back" and inst.status == "candidate",
        "statement": inst.statement,
    }


def confirm_statement(db: Session, learner: Learner, instance_id: str, confirmed: bool) -> dict[str, Any]:
    inst = db.get(MisconceptionInstance, instance_id)
    if inst is None or inst.learner_id != learner.id:
        raise KeyError(instance_id)
    if inst.status != "candidate":
        return {"instance_id": inst.id, "status": inst.status, "changed": False}
    inst.status = "confirmed" if confirmed else "dismissed"
    db.flush()
    return {"instance_id": inst.id, "misconception_id": inst.misconception_id, "status": inst.status, "changed": True}


def on_success(db: Session, learner: Learner, concept_id: str, source_type: str) -> list[dict[str, Any]]:
    """Call after a successful (correct) piece of evidence on a concept. Advances correction cycles."""
    out: list[dict[str, Any]] = []
    now = learner_now(learner)
    for inst in db.scalars(select(MisconceptionInstance).where(
            MisconceptionInstance.learner_id == learner.id,
            MisconceptionInstance.concept_id == concept_id,
            MisconceptionInstance.status.in_(ACTIVE))):
        if source_type not in ("work_product", "explain_back", "question"):
            continue
        if inst.status == "confirmed":
            inst.status = "correcting"
            out.append({"instance_id": inst.id, "misconception_id": inst.misconception_id, "status": "correcting"})
        elif inst.status == "correcting" and source_type in ("work_product", "explain_back"):
            inst.status = "pending_verify"
            inst.verify_after = now + timedelta(days=VERIFY_AFTER_DAYS)
            out.append({"instance_id": inst.id, "misconception_id": inst.misconception_id, "status": "pending_verify",
                        "verify_after": inst.verify_after.isoformat()})
        elif inst.status == "pending_verify" and inst.verify_after and now >= inst.verify_after \
                and source_type in ("work_product", "explain_back"):
            inst.status = "resolved"
            inst.resolved_at = now
            out.append({"instance_id": inst.id, "misconception_id": inst.misconception_id, "status": "resolved"})
    db.flush()
    return out


def dispute(db: Session, learner: Learner, instance_id: str) -> dict[str, Any]:
    inst = db.get(MisconceptionInstance, instance_id)
    if inst is None or inst.learner_id != learner.id:
        raise KeyError(instance_id)
    inst.status = "dismissed"
    db.flush()
    return {"instance_id": inst.id, "status": inst.status}


def describe(db: Session, learner_id: str) -> list[dict[str, Any]]:
    content = get_content()
    out = []
    rows = db.scalars(select(MisconceptionInstance).where(MisconceptionInstance.learner_id == learner_id,
                                                          MisconceptionInstance.status.in_(OPEN)))
    for inst in rows:
        m = content.misconceptions[inst.misconception_id]
        out.append({
            "instance_id": inst.id, "misconception_id": inst.misconception_id, "concept_id": inst.concept_id,
            "concept_name": content.concepts[inst.concept_id].name, "name": m["name"], "description": m["description"],
            "status": inst.status, "cycles": inst.cycles, "channel": inst.channel, "statement": inst.statement,
            "counter_example": m["counter_example"], "check_question": m["check_question"], "fix_hint": m["fix_hint"],
            "verify_after": inst.verify_after.isoformat() if inst.verify_after else None,
        })
    return out


def correction_plan(misconception_id: str) -> dict[str, Any]:
    content = get_content()
    m = content.misconceptions[misconception_id]
    tasks = [t["id"] for t in content.tasks_by_concept.get(m["concept_id"], [])
             if any(v["misconception_id"] == misconception_id for v in t.get("variants", []))]
    return {
        "misconception_id": misconception_id, "name": m["name"], "concept_id": m["concept_id"],
        "steps": [
            {"step": "counter_example", "text": m["counter_example"]["explanation"], "query": m["counter_example"].get("query") or None},
            {"step": "check_question", "text": m["check_question"]},
            {"step": "practice_tasks", "task_ids": tasks},
            {"step": "explain_again", "text": "Now explain it again in your own words."},
            {"step": "delayed_check", "text": f"A short re-check after {int(VERIFY_AFTER_DAYS)} day confirms it is gone."},
        ],
    }
