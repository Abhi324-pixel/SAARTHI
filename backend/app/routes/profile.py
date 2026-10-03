"""C06 — Learner profile page routes.

GET   /api/profile   → Profile details, real activity stats, consent, and mentor visibility
PATCH /api/profile   → Update learner name, education level, institution, goal text
"""

from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import adapters
from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..engines import escalation, profile_stats, safeguarding
from ..models import Learner

router = APIRouter(prefix="/api/profile")

VALID_EDUCATION_LEVELS = {
    "school_9_12",
    "diploma",
    "undergraduate",
    "postgraduate",
    "working",
    "other",
}


def _strip_ctrl(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", s).strip()
    return cleaned


class ProfilePatchIn(BaseModel):
    name: Optional[str] = None
    education: Optional[str] = None
    institution: Optional[str] = None
    goal_text: Optional[str] = None


@router.get("")
def get_profile(
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    c = get_content()
    settings = dict(lr.settings or {})
    prof = dict(settings.get("profile") or {})
    role = c.roles.get(lr.role_id or "backend_developer")
    role_title = role["title"] if role else "Backend Developer"

    # Exact keys from escalation.build_report learner block
    sample_report = escalation.build_report(
        db, lr, "technical", None, "trigger", "reason", "", False
    )
    mentor_keys = list(sample_report["learner"].keys())

    stats_data = profile_stats.stats(db, lr)

    mentor_consent = adapters.consent().status(db, lr, "mentor_sessions")
    transcript_consent = adapters.consent().status(db, lr, "transcript_share")

    return {
        "profile": {
            "name": lr.name,
            "email": lr.email,
            "age": lr.age,
            "is_minor": safeguarding.is_minor(lr),
            "education": prof.get("education"),
            "institution": prof.get("institution"),
            "goal_text": prof.get("goal_text") or settings.get("goal_text"),
            "language": lr.language_pref,
            "role_id": lr.role_id,
            "role_title": role_title,
        },
        "stats": stats_data,
        "consent": {
            "mentor_sessions": mentor_consent,
            "transcript_share": transcript_consent,
            "is_minor": safeguarding.is_minor(lr),
            "guardian_status": mentor_consent if safeguarding.is_minor(lr) else "not_applicable",
        },
        "what_mentors_see": {
            "keys": mentor_keys,
            "values": sample_report["learner"],
            "never_shared": [
                "full_name",
                "email",
                "exact_age",
                "institution",
                "account_id",
                "unrelated_data",
            ],
        },
    }


@router.patch("")
def patch_profile(
    body: ProfilePatchIn,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    # Validate education
    if body.education is not None:
        edu = body.education.strip().lower()
        if edu and edu not in VALID_EDUCATION_LEVELS:
            raise HTTPException(422, f"Invalid education level. Allowed: {sorted(VALID_EDUCATION_LEVELS)}")
    else:
        edu = None

    # Validate institution length
    if body.institution is not None:
        inst = _strip_ctrl(body.institution)
        if inst and len(inst) > 80:
            raise HTTPException(422, "Institution name cannot exceed 80 characters.")
    else:
        inst = None

    # Validate goal text length
    if body.goal_text is not None:
        gt = _strip_ctrl(body.goal_text)
        if gt and len(gt) > 200:
            raise HTTPException(422, "Goal text cannot exceed 200 characters.")
    else:
        gt = None

    # Validate name
    if body.name is not None:
        cleaned_name = _strip_ctrl(body.name)
        if not cleaned_name or len(cleaned_name) > 80:
            raise HTTPException(422, "Name must be between 1 and 80 characters.")
        lr.name = cleaned_name

    # Apply to learner settings
    settings = dict(lr.settings or {})
    prof = dict(settings.get("profile") or {})

    if body.education is not None:
        prof["education"] = edu if edu else None
    if body.institution is not None:
        prof["institution"] = inst if inst else None
    if body.goal_text is not None:
        prof["goal_text"] = gt if gt else None
        settings["goal_text"] = gt if gt else None

    settings["profile"] = prof
    lr.settings = settings
    db.flush()

    return get_profile(lr=lr, db=db)
