"""V01: video interview. A resume summary (never the file) and the practice sessions built on it.

The camera picture and microphone audio never reach the server: they are recorded in the learner's own browser. Only the typed or
transcribed answers, the model's grounded feedback and a few numbers the browser measured are stored here."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .. import privacy
from ..models import Base, Learner, new_id, now


class ResumeSummary(Base):
    __tablename__ = "resume_summaries"
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), primary_key=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class VideoInterview(Base):
    __tablename__ = "video_interviews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("vi_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), default="active")      # active | done
    use_resume: Mapped[bool] = mapped_column(default=False)
    language: Mapped[str] = mapped_column(String(16), default="english")
    total: Mapped[int] = mapped_column(default=5)
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)   # [{question, answer, feedback}]
    client_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class VideoInterviewSummary(Base):
    """The short written summary of one finished interview (model-written from the interview's own facts, then checked by code)."""
    __tablename__ = "video_interview_summaries"
    interview_id: Mapped[str] = mapped_column(ForeignKey("video_interviews.id", ondelete="CASCADE"), primary_key=True)
    text: Mapped[str] = mapped_column(String(900))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


def _export_resume(db: Session, learner: Learner) -> Optional[dict[str, Any]]:
    r = db.get(ResumeSummary, learner.id)
    return None if r is None else {"summary": r.summary, "updated_at": r.updated_at.isoformat()}


def _export_interviews(db: Session, learner: Learner) -> list[dict[str, Any]]:
    rows = db.scalars(select(VideoInterview).where(VideoInterview.learner_id == learner.id).order_by(VideoInterview.created_at))
    out = []
    for v in rows:
        sm = db.get(VideoInterviewSummary, v.id)
        out.append({"id": v.id, "role_id": v.role_id, "status": v.status, "use_resume": v.use_resume, "turns": v.turns,
                    "client_metrics": v.client_metrics, "summary": sm.text if sm else None, "created_at": v.created_at.isoformat()})
    return out


privacy.register_export("resume_summary", _export_resume)
privacy.register_export("video_interviews", _export_interviews)
