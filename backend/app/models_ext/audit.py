"""Audit trail for safeguarding-relevant actions (consent requests and decisions now; mentor decisions and case changes later).

Rows hold ids and short codes only, never message text or contact details, so keeping them after an account is deleted does
not retain personal content. Written through `engines/audit.record`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, new_id, now


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("au_"))
    at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), default="")        # learner / mentor / admin id, or "guardian"
    actor_role: Mapped[str] = mapped_column(String(16), default="")      # learner | guardian | mentor | admin | system
    action: Mapped[str] = mapped_column(String(48))                      # e.g. consent_requested, consent_approved
    subject_type: Mapped[str] = mapped_column(String(24), default="")
    subject_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
