"""C02 — mentors who declined (or timed out on) a case, so the matcher never offers it to them again."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, new_id, now


class CaseExclusion(Base):
    __tablename__ = "case_exclusions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ce_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("mentor_cases.id", ondelete="CASCADE"), index=True)
    mentor_id: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(24), default="")      # busy | outside_expertise | conflict | other | timeout
    at: Mapped[datetime] = mapped_column(DateTime, default=now)
