"""Diagnostic engine: choose what to ask, grade it, and turn wrong answers into misconception signals.

Probe selection ports the idea from TESSA's `probe_skills`: ask where the goal matters AND the estimate is
shakiest. Added here: concepts whose assessed prerequisite is weak are de-prioritised (they would mostly
fail for a reason we already know), and items are chosen near the current estimate.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..content import get_content
from ..models import EvidenceEvent, Learner
from . import mastery, misconception, sqlcheck


def _seed(learner: Learner) -> str:
    return hashlib.sha1(learner.id.encode()).hexdigest()[:8]


def answered_item_ids(db: Session, learner_id: str) -> set[str]:
    rows = db.scalars(select(EvidenceEvent.item_id).where(
        EvidenceEvent.learner_id == learner_id, EvidenceEvent.source_type == "question"))
    return {r for r in rows if r}


def pick_concepts(db: Session, learner: Learner, n: int, role_id: Optional[str] = None) -> list[str]:
    content = get_content()
    role = content.role(role_id or learner.role_id or "backend_developer")
    views = mastery.concept_views(db, learner)
    self_reported = set(db.scalars(
        select(EvidenceEvent.concept_id).where(
            EvidenceEvent.learner_id == learner.id,
            EvidenceEvent.source_type == "self_report",
        )
    ))
    scored: list[tuple[float, str]] = []
    for cid, req in role["requirements"].items():
        v = views[cid]
        if v["n_evidence"] >= 3:
            continue
        p = v["p"]
        uncertainty = 1.0 - abs(p - 0.5) * 2.0
        score = req["weight"] * max(req["target"] - p, 0.15) * (0.4 + uncertainty)
        if v["n_evidence"] == 0:
            score *= 1.15  # unmeasured concepts are the most informative first questions
            if cid in self_reported:
                score *= 1.35  # claimed skills are prioritized for placement verification
        if "blocked" in v["flags"]:
            score *= 0.3
        scored.append((score, cid))
    scored.sort(reverse=True)
    return [cid for _, cid in scored[:n]]


def next_probe(db: Session, learner: Learner, count: int = 1, role_id: Optional[str] = None,
               concept_id: Optional[str] = None, harder: bool = False) -> list[dict[str, Any]]:
    content = get_content()
    seen = answered_item_ids(db, learner.id)
    seed = _seed(learner)
    views = mastery.concept_views(db, learner)
    concepts = [concept_id] if concept_id else pick_concepts(db, learner, count * 3, role_id)
    out: list[dict[str, Any]] = []
    for cid in concepts:
        pool = [i for i in content.items_by_concept.get(cid, []) if i["id"] not in seen]
        if not pool:
            continue
        target = views[cid]["p"]
        target_diff = (0.5 + 0.4 * target) if harder else (0.25 + 0.5 * target)
        pool.sort(key=lambda i: abs(i.get("difficulty", 0.4) - target_diff))
        item = pool[0]
        pub = content.public_item(item, seed)
        pub["concept_name"] = content.concepts[cid].name
        out.append(pub)
        if len(out) >= count:
            break
    return out


def grade_mcq(db: Session, learner: Learner, item_id: str, option_index: int,
              stated_confidence: Optional[int] = None) -> dict[str, Any]:
    content = get_content()
    item = content.items.get(item_id)
    if item is None:
        raise KeyError(item_id)
    opts = content.shuffled_options(item, _seed(learner))
    if not (0 <= option_index < len(opts)):
        raise ValueError("option_index out of range")
    chosen = opts[option_index]
    correct = bool(chosen.get("correct"))
    mid = chosen.get("misconception_id")
    res = mastery.apply_evidence(
        db, learner, item["concept_id"], "question", correct=correct, item_id=item_id,
        stated_confidence=stated_confidence, grader="mcq",
        detail={"chosen": chosen["text"], "misconception_id": mid},
    )
    flag = None
    advanced: list[dict] = []
    if mid:
        flag = misconception.register_signal(db, learner, mid, "question", res["evidence_id"])
    if correct:
        advanced = misconception.on_success(db, learner, item["concept_id"], "question")
    correct_text = next(o["text"] for o in item["options"] if o.get("correct"))
    return {
        "correct": correct, "explanation": item["explain"], "correct_option": correct_text,
        "concept_id": item["concept_id"], "concept_name": content.concepts[item["concept_id"]].name,
        "mastery": res, "misconception": flag, "misconception_progress": advanced,
        "calibration": _calibration_note(stated_confidence, correct),
    }


def _calibration_note(stated: Optional[int], correct: bool) -> Optional[str]:
    if stated is None:
        return None
    if stated >= 4 and not correct:
        return "You were very sure, but this one was wrong — worth a closer look."
    if stated <= 2 and correct:
        return "You were unsure, yet you got it right — you know more than you think."
    return None


# ---------------------------------------------------------------------------------------------------
# SQL work products
# ---------------------------------------------------------------------------------------------------

def public_task(task: dict) -> dict[str, Any]:
    return {"id": task["id"], "concept_id": task["concept_id"], "prompt": task["prompt"],
            "difficulty": task.get("difficulty", 0.4), "hints": task.get("hints", [])}


def tasks_for(db: Session, learner: Learner, concept_id: Optional[str] = None) -> list[dict[str, Any]]:
    content = get_content()
    if concept_id:
        return [public_task(t) for t in content.tasks_by_concept.get(concept_id, [])]
    return [public_task(t) for t in content.tasks.values()]


def submit_work_product(db: Session, learner: Learner, task_id: str, query: str,
                        stated_confidence: Optional[int] = None) -> dict[str, Any]:
    content = get_content()
    task = content.tasks.get(task_id)
    if task is None:
        raise KeyError(task_id)
    verdict = sqlcheck.evaluate(task, query)
    res_obj = verdict.result
    # a query that fails to run is not evidence about understanding; only graded runs count
    ran = bool(res_obj and res_obj.ok)
    mastery_res = None
    flag = None
    advanced: list[dict] = []
    if ran:
        mastery_res = mastery.apply_evidence(
            db, learner, task["concept_id"], "work_product", correct=verdict.correct, item_id=task_id,
            stated_confidence=stated_confidence, grader="sql_exec",
            detail={"query": query[:600], "misconception_id": verdict.misconception_id, "matched_by": verdict.matched_by},
        )
        if verdict.misconception_id:
            flag = misconception.register_signal(db, learner, verdict.misconception_id, "work_product",
                                                 mastery_res["evidence_id"])
        if verdict.correct:
            advanced = misconception.on_success(db, learner, task["concept_id"], "work_product")
    elif verdict.misconception_id and verdict.matched_by == "error":
        # error-signature misconceptions (e.g. aggregate in WHERE) are objective even though the query errored
        mastery_res = mastery.apply_evidence(
            db, learner, task["concept_id"], "work_product", correct=False, item_id=task_id,
            stated_confidence=stated_confidence, grader="sql_exec",
            detail={"query": query[:600], "misconception_id": verdict.misconception_id, "matched_by": "error"},
        )
        flag = misconception.register_signal(db, learner, verdict.misconception_id, "work_product",
                                             mastery_res["evidence_id"])
    m = content.misconceptions.get(verdict.misconception_id) if verdict.misconception_id else None
    return {
        "task_id": task_id, "concept_id": task["concept_id"], "ran": ran, "correct": verdict.correct,
        "columns": res_obj.columns if res_obj else [], "rows": res_obj.rows if res_obj else [],
        "truncated": res_obj.truncated if res_obj else False, "error": None if ran else (res_obj.error if res_obj else None),
        "hints": verdict.hints, "matched_by": verdict.matched_by,
        "misconception": ({"id": m["id"], "name": m["name"], "description": m["description"],
                           "counter_example": m["counter_example"], "fix_hint": m["fix_hint"],
                           "instance": flag} if m else None),
        "mastery": mastery_res, "misconception_progress": advanced,
        "calibration": _calibration_note(stated_confidence, verdict.correct) if ran else None,
    }


def run_free_query(query: str) -> dict[str, Any]:
    r = sqlcheck.run_query(query)
    return {"ok": r.ok, "columns": r.columns, "rows": r.rows, "truncated": r.truncated, "error": r.error}
