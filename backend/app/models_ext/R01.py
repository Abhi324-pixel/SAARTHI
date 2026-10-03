"""R01: cached web learning resources per concept (found with Tavily).

Not learner data: it is a shared cache of public web pages, so it needs no privacy export or delete. The learner is never part of a search
(the query is built only from the concept name and a language hint)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base, now


class WebResourceCache(Base):
    __tablename__ = "web_resource_cache"

    concept_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lang_bucket: Mapped[str] = mapped_column(String(8), primary_key=True)      # "en" or "hi"
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=now)
