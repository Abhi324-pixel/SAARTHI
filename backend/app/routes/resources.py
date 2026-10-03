"""R01: real web resources for a concept (Tavily, cached). See engines/resources.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import ratelimit
from ..content import get_content
from ..db import get_db
from ..deps import current_learner
from ..engines import resources
from ..models import Learner

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("/{concept_id}")
def concept_resources(concept_id: str, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    if concept_id not in get_content().concepts:
        raise HTTPException(404, "Unknown concept.")
    if resources.needs_search(db, concept_id, lr.language_pref) and not ratelimit.allow(f"res:{lr.id}", 40, 3600):
        raise HTTPException(429, "Too many searches this hour. Please try again later.")
    return {"concept_id": concept_id, **resources.for_concept(db, concept_id, lr.language_pref),
            "label": "Found on the web with Tavily. SAARTHI has not reviewed these pages."}
