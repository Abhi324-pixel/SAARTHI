"""V01: resume upload and the video interview. Camera and microphone data never come here (they stay in the learner's browser)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import ratelimit
from ..db import get_db
from ..deps import current_learner
from ..engines import resume as resume_engine, video_interview as vi
from ..models import Learner

router = APIRouter(prefix="/api")


def _run(fn, *a):
    try:
        return fn(*a)
    except (vi.InterviewError, resume_engine.ResumeError) as e:
        raise HTTPException(e.status, e.message)


@router.post("/resume")
async def upload_resume(file: UploadFile = File(...), lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    if not ratelimit.allow(f"resume:{lr.id}", 8, 3600):
        raise HTTPException(429, "Too many uploads. Please try again later.")
    data = await file.read(resume_engine.MAX_BYTES + 1)
    text = _run(resume_engine.extract_text, file.filename or "", data)
    summary = _run(resume_engine.parse, text)
    resume_engine.save(db, lr, summary)
    return {"summary": resume_engine.load(db, lr)}


@router.get("/resume")
def get_resume(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return {"summary": resume_engine.load(db, lr)}


@router.delete("/resume")
def delete_resume(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return {"deleted": resume_engine.delete(db, lr)}


class StartIn(BaseModel):
    role_id: Optional[str] = Field(default=None, max_length=64)
    use_resume: bool = False


class AnswerIn(BaseModel):
    text: str = Field(max_length=4000)


class FinishIn(BaseModel):
    client_metrics: Optional[dict[str, Any]] = None


@router.post("/video-interview/start")
def start(body: StartIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    if not ratelimit.allow(f"vi:{lr.id}", 12, 3600):
        raise HTTPException(429, "You have started a lot of interviews this hour. Please take a break and try again.")
    return _run(vi.start, db, lr, body.role_id, body.use_resume)


@router.post("/video-interview/{vid}/answer")
def answer(vid: str, body: AnswerIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return _run(vi.answer, db, lr, vid, body.text)


@router.post("/video-interview/{vid}/finish")
def finish(vid: str, body: FinishIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return _run(vi.finish, db, lr, vid, body.client_metrics)


@router.post("/video-interview/{vid}/focus")
def add_focus(vid: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return _run(vi.add_focus_to_plan, db, lr, vid)


@router.get("/video-interview/{vid}")
def get_report(vid: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return _run(vi.report, db, lr, vid)


@router.get("/video-interview")
def history(lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    return {"interviews": vi.history(db, lr)}
