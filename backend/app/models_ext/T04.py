"""T04 — Streak & daily goal.

No new table: streak settings are stored in Learner.settings["daily_goal"]
and Learner.settings["streak_show"]. Streak values are computed on demand
from existing evidence_events.

This module registers a privacy export so /api/me/export includes the
learner's streak settings (and therefore their daily_goal preference).
There are no learner-specific rows to delete beyond the Learner record itself.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .. import privacy
from ..models import Learner


def _export_streak_settings(db: Session, learner: Learner) -> dict[str, Any]:
    settings = learner.settings or {}
    return {
        "daily_goal": settings.get("daily_goal", 3),
        "streak_show": settings.get("streak_show", True),
    }


privacy.register_export("T04_streak_settings", _export_streak_settings)
