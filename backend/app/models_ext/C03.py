from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from .. import privacy
from ..models import Base, Learner, new_id, now


class CaseNote(Base):
    """C03: Learner prep notes before a mentor session and summary after it."""
    __tablename__ = "case_notes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cn_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("mentor_cases.id", ondelete="CASCADE"), index=True)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # "learner_prep" | "session_summary"
    body: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


def _export_case_notes(db: Session, learner: Learner) -> list[dict[str, Any]]:
    notes = list(db.scalars(
        select(CaseNote).where(CaseNote.learner_id == learner.id).order_by(CaseNote.created_at)
    ))
    return [
        {
            "id": n.id,
            "case_id": n.case_id,
            "kind": n.kind,
            "body": n.body,
            "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ]


privacy.register_export("case_notes", _export_case_notes)
