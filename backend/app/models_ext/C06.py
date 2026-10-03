"""C06 — Learner profile privacy export hook."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from .. import privacy
from ..models import Learner


def export_profile(db: Session, learner: Learner) -> dict[str, Any]:
    settings = dict(learner.settings or {})
    return {
        "profile": settings.get("profile", {}),
        "goal_text": settings.get("goal_text"),
        "wanted_goal": settings.get("wanted_goal"),
    }


privacy.register_export("profile", export_profile)
