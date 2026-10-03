"""T05 — Roadmap phases, deadlines and personal checkpoints.

Adds `learner_checkpoints` table for personal goals (free-text or concept-linked).
Registers export with privacy.register_export.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .. import privacy
from ..models import Base, Learner, new_id, now


class LearnerCheckpoint(Base):
    __tablename__ = "learner_checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cp_"))
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    concept_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


def _export_checkpoints(db: Session, learner: Learner) -> list[dict[str, Any]]:
    rows = list(db.scalars(
        select(LearnerCheckpoint)
        .where(LearnerCheckpoint.learner_id == learner.id)
        .order_by(LearnerCheckpoint.created_at)
    ))
    return [
        {
            "id": r.id,
            "title": r.title,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "concept_id": r.concept_id,
            "done_at": r.done_at.isoformat() if r.done_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


privacy.register_export("T05_checkpoints", _export_checkpoints)
