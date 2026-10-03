"""Public guardian-consent endpoints (no sign-in: the guardian is not a SAARTHI user) and the dev-only outbox. Spec: docs/features/D01."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import adapters, ratelimit
from ..config import settings
from ..db import get_db
from ..deps import current_learner
from ..engines import guardian
from ..models import Learner

router = APIRouter(prefix="/api")

_INVALID = "This link is not valid any more. If you still want to help, ask the learner to send a new request."


def _throttle(request: Request, what: str) -> None:
    ip = request.client.host if request.client else "unknown"
    if not ratelimit.allow(f"guardian:{what}:{ip}", 20, 60):
        raise HTTPException(429, "Too many attempts. Please wait a minute and try again.")


@router.get("/guardian/preview")
def preview(token: str, request: Request, db: Session = Depends(get_db)):
    _throttle(request, "preview")
    try:
        return guardian.preview(db, token)
    except guardian.InvalidLink:
        raise HTTPException(404, _INVALID)


class DecisionIn(BaseModel):
    token: str = Field(max_length=2000)
    decision: str = Field(max_length=10)


@router.post("/guardian/decision")
def decision(body: DecisionIn, request: Request, db: Session = Depends(get_db)):
    _throttle(request, "decision")
    try:
        return guardian.decide(db, body.token, body.decision)
    except guardian.InvalidLink:
        db.rollback()
        raise HTTPException(404, _INVALID)


class WithdrawIn(BaseModel):
    token: str = Field(max_length=2000)


@router.post("/guardian/withdraw")
def withdraw(body: WithdrawIn, request: Request, db: Session = Depends(get_db)):
    _throttle(request, "withdraw")
    try:
        return guardian.withdraw(db, body.token)
    except guardian.InvalidLink:
        db.rollback()
        raise HTTPException(404, _INVALID)


@router.get("/dev/outbox")
def outbox(lr: Learner = Depends(current_learner)):
    """Dev only (mock mailer): the e-mails that would have been sent, so the guardian link can be tried without a mail server."""
    if settings.is_prod or not adapters.mailer().is_mock:
        raise HTTPException(404, "Not found")
    return {"messages": list(adapters.MockMailer.outbox)[-10:]}
