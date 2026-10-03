"""I18N: shared cache of translated interface text (Hindi and Hinglish).

Not learner data: it maps one exact English sentence to its translation, the same for everybody, so it has no owner to export or delete.
The server refuses to store text that looks like personal data (e-mail addresses, links, phone numbers)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, now


class UiTranslation(Base):
    __tablename__ = "ui_translations"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)         # sha256 of language + source text
    lang: Mapped[str] = mapped_column(String(10), primary_key=True)        # hindi | hinglish
    source: Mapped[str] = mapped_column(Text)
    translated: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
