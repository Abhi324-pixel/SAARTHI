"""Learning loop endpoints: placement/probe, SQL work products, teaching, explain-back, interview, misconceptions, reviews, stuck."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..engines import diagnostic, explainback, feedback as feedback_engine, hooks, mastery, misconception, sqlcheck, strategy, stuck
from ..llm import gateway
from ..models import Learner

router = APIRouter(prefix="/api")


def _404(e: Exception):
    raise HTTPException(404, f"not found: {e}")


# ---- probe / quiz -------------------------------------------------------------------------------------
class ProbeIn(BaseModel):
    count: int = Field(default=1, ge=1, le=6)
    concept_id: Optional[str] = None


@router.post("/probe/next")
def probe_next(body: ProbeIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    items = diagnostic.next_probe(db, lr, count=body.count, concept_id=body.concept_id)
    return {"items": items}


class AnswerIn(BaseModel):
    item_id: str
    option_index: int = Field(ge=0, le=9)
    stated_confidence: Optional[int] = Field(default=None, ge=1, le=5)


@router.post("/probe/answer")
def probe_answer(body: AnswerIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        res = diagnostic.grade_mcq(db, lr, body.item_id, body.option_index, body.stated_confidence)
    except KeyError as e:
        _404(e)
    except ValueError as e:
        raise HTTPException(400, str(e))
    feedback_engine.on_probe_answered(db, lr, body.item_id, bool(res.get("correct")))
    res["after"] = hooks.after_evidence(db, lr, res["concept_id"], "your last answer")
    return res


# ---- SQL ---------------------------------------------------------------------------------------------------
@router.get("/sql/tasks")
def sql_tasks(concept_id: Optional[str] = None, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return {"tasks": diagnostic.tasks_for(db, lr, concept_id)}


@router.get("/sql/schema")
def sql_schema(lr: Learner = Depends(current_learner)):
    import sqlite3
    conn = sqlite3.connect(":memory:")
    from ..engines.sqlcheck import _dataset_sql
    conn.executescript(_dataset_sql())
    out = []
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        cols = [{"name": r[1], "type": r[2], "pk": bool(r[5])} for r in conn.execute(f"PRAGMA table_info({name})")]
        rows = [list(r) for r in conn.execute(f"SELECT * FROM {name} LIMIT 20")]
        out.append({"table": name, "columns": cols, "sample": rows, "count": conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]})
    conn.close()
    return {"tables": out}


class RunIn(BaseModel):
    query: str = Field(max_length=4000)


@router.post("/sql/run")
def sql_run(body: RunIn, lr: Learner = Depends(current_learner)):
    return diagnostic.run_free_query(body.query)


class SubmitIn(BaseModel):
    task_id: str
    query: str = Field(max_length=4000)
    stated_confidence: Optional[int] = Field(default=None, ge=1, le=5)


@router.post("/sql/submit")
def sql_submit(body: SubmitIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        res = diagnostic.submit_work_product(db, lr, body.task_id, body.query, body.stated_confidence)
    except KeyError as e:
        _404(e)
    if res["mastery"] is not None or res["misconception"]:
        res["after"] = hooks.after_evidence(db, lr, res["concept_id"], "your last SQL query")
    return res


# ---- teaching ----------------------------------------------------------------------------------------------
class TeachIn(BaseModel):
    concept_id: str
    strategy: Optional[str] = None
    misconception_id: Optional[str] = None


@router.post("/teach/explain")
def teach(body: TeachIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        out = strategy.explain(db, lr, body.concept_id, body.strategy, body.misconception_id)
    except KeyError as e:
        _404(e)
    c = get_content()
    out["has_tasks"] = bool(c.tasks_by_concept.get(body.concept_id))
    out["has_rubric"] = c.has_rubric(body.concept_id)
    out["misconceptions_known"] = [{"id": m["id"], "name": m["name"]} for m in c.misc_by_concept.get(body.concept_id, [])]
    return out


@router.get("/concepts/{concept_id}")
def concept_detail(concept_id: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    c = get_content()
    if concept_id not in c.concepts:
        _404(concept_id)
    v = mastery.concept_views(db, lr)[concept_id]
    cc = c.concepts[concept_id]
    return {"concept": {"id": cc.id, "name": cc.name, "name_hi": cc.name_hi, "domain": cc.domain, "minutes": cc.minutes,
                        "prereqs": [{"id": p, "name": c.concepts[p].name} for p in cc.prereqs]},
            "state": v, "note": c.note(concept_id), "tasks": diagnostic.tasks_for(db, lr, concept_id),
            "has_rubric": c.has_rubric(concept_id), "n_items": len(c.items_by_concept.get(concept_id, [])),
            "misconceptions_known": [{"id": m["id"], "name": m["name"]} for m in c.misc_by_concept.get(concept_id, [])]}


# ---- explain-back ---------------------------------------------------------------------------------------------
class EBStart(BaseModel):
    concept_id: str
    channel: str = "text"


@router.post("/explainback/start")
def eb_start(body: EBStart, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        return explainback.start(db, lr, body.concept_id, body.channel)
    except KeyError as e:
        _404(e)


class SpeechPausesIn(BaseModel):
    count_over_1s: int = Field(default=0, ge=0)
    longest_s: float = Field(default=0.0, ge=0.0)


class SpeechMetricsIn(BaseModel):
    words: int = Field(default=0, ge=0)
    speaking_seconds: float = Field(default=0.0, ge=0.0)
    wpm: Optional[int] = Field(default=None, ge=20, le=400)
    pauses: Optional[SpeechPausesIn] = None
    markers: dict[str, int] = Field(default_factory=dict)
    markers_per_100_words: Optional[float] = Field(default=None, ge=0.0)
    tips: list[str] = Field(default_factory=list)


class EBAnswer(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=4000)
    stated_confidence: Optional[int] = Field(default=None, ge=1, le=5)
    audio_seconds: Optional[float] = None
    channel: Optional[str] = None
    speech: Optional[SpeechMetricsIn] = None


@router.post("/explainback/answer")
def eb_answer(body: EBAnswer, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        out = explainback.answer(db, lr, body.session_id, body.text, stated_confidence=body.stated_confidence,
                                 audio_seconds=body.audio_seconds, channel=body.channel,
                                 speech=body.speech.model_dump() if body.speech else None)
    except KeyError as e:
        _404(e)
    if out.get("final"):
        out["after"] = hooks.after_evidence(db, lr, out["concept_id"], "your explanation")
    return out


class EBFinish(BaseModel):
    session_id: str


@router.post("/explainback/finish")
def eb_finish(body: EBFinish, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    from ..models import LearningSession
    sess = db.get(LearningSession, body.session_id)
    if sess is None or sess.learner_id != lr.id:
        _404(body.session_id)
    if not sess.state.get("covered") and not sess.state.get("turns"):
        raise HTTPException(400, "Nothing to score yet - give an explanation first.")
    final = explainback.finalize(db, lr, sess)
    return {"final": final, "session_id": sess.id, "concept_id": sess.concept_id,
            "after": hooks.after_evidence(db, lr, sess.concept_id, "your explanation")}


# ---- interview -------------------------------------------------------------------------------------------------
class InterviewStart(BaseModel):
    n_topics: int = Field(default=4, ge=1, le=8)
    channel: str = "text"
    round: str = Field(default="technical")
    pack_id: Optional[str] = None


@router.post("/interview/start")
def interview_start(body: InterviewStart, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        return explainback.interview_start(db, lr, body.n_topics, body.channel, round=body.round, pack_id=body.pack_id)
    except KeyError as e:
        _404(e)


class InterviewAnswer(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=4000)
    stated_confidence: Optional[int] = Field(default=None, ge=1, le=5)
    audio_seconds: Optional[float] = None
    channel: Optional[str] = None
    speech: Optional[SpeechMetricsIn] = None


@router.post("/interview/answer")
def interview_answer(body: InterviewAnswer, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        out = explainback.interview_answer(db, lr, body.session_id, body.text, stated_confidence=body.stated_confidence,
                                          audio_seconds=body.audio_seconds, channel=body.channel,
                                          speech=body.speech.model_dump() if body.speech else None)
    except KeyError as e:
        _404(e)
    if out.get("done") or out.get("previous"):
        out["after"] = hooks.after_evidence(db, lr, out.get("concept_id"), "your interview answers")
    return out


# ---- misconceptions -----------------------------------------------------------------------------------------------
@router.get("/misconceptions")
def misconceptions(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return {"active": misconception.describe(db, lr.id)}


class ConfirmIn(BaseModel):
    confirmed: bool


@router.post("/misconceptions/{instance_id}/confirm")
def confirm(instance_id: str, body: ConfirmIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        out = misconception.confirm_statement(db, lr, instance_id, body.confirmed)
    except KeyError as e:
        _404(e)
    out["after"] = hooks.after_evidence(db, lr, None, "your confirmation")
    return out


@router.post("/misconceptions/{instance_id}/dispute")
def dispute_m(instance_id: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    try:
        out = misconception.dispute(db, lr, instance_id)
    except KeyError as e:
        _404(e)
    out["after"] = hooks.after_evidence(db, lr, None, "your correction")
    return out


@router.get("/misconception-library/{misconception_id}/plan")
def plan(misconception_id: str, lr: Learner = Depends(current_learner)):
    if misconception_id not in get_content().misconceptions:
        _404(misconception_id)
    return misconception.correction_plan(misconception_id)


# ---- reviews --------------------------------------------------------------------------------------------------------
@router.get("/reviews/due")
def reviews_due(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    views = mastery.concept_views(db, lr)
    due = [v for v in views.values() if v["due_for_review"]]
    items = []
    for v in due[:5]:
        probe = diagnostic.next_probe(db, lr, count=1, concept_id=v["concept_id"])
        if probe:
            items.append({"concept_id": v["concept_id"], "concept_name": v["name"], "item": probe[0]})
    return {"due": [{"concept_id": v["concept_id"], "name": v["name"], "p": v["p"], "next_review_at": v["next_review_at"]} for v in due],
            "items": items}


# ---- stuck --------------------------------------------------------------------------------------------------------------
class StuckIn(BaseModel):
    text: str = Field(default="", max_length=2000)
    query: Optional[str] = Field(default=None, max_length=4000)
    task_id: Optional[str] = None
    concept_id: Optional[str] = None


@router.post("/stuck")
def stuck_ep(body: StuckIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    if not body.text.strip() and not (body.query and body.query.strip()):
        raise HTTPException(400, "Tell me what you are stuck on, or paste your query.")
    out = stuck.diagnose(db, lr, text=body.text, query=body.query, task_id=body.task_id, concept_id=body.concept_id)
    if out.get("concept_id"):
        out["after"] = hooks.after_evidence(db, lr, out["concept_id"], "your 'stuck' question")
    return out
