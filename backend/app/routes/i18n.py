"""I18N: translate interface text into the learner's language (cached, checked). See engines/ui_translate.py."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import ratelimit
from ..db import get_db
from ..deps import current_learner
from ..engines import ui_translate
from ..models import Learner

router = APIRouter(prefix="/api/i18n", tags=["i18n"])


class TranslateIn(BaseModel):
    lang: str = Field(max_length=10)
    texts: list[str] = Field(max_length=ui_translate.MAX_BATCH)


@router.post("/translate")
def translate(body: TranslateIn, lr: Learner = Depends(current_learner), db: Session = Depends(get_db)):
    if body.lang not in ui_translate.LANGS:
        raise HTTPException(422, "Unsupported language.")
    if any(len(t) > ui_translate.MAX_LEN * 4 for t in body.texts):
        raise HTTPException(422, "A text is too long.")
    if not ratelimit.allow(f"i18n:{lr.id}", 240, 3600):
        raise HTTPException(429, "Too many translation requests. Please wait a little.")
    return {"lang": body.lang, "translations": ui_translate.translate(db, body.lang, body.texts)}
