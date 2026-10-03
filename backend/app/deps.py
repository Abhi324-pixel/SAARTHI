"""Request dependencies: DB session and the authenticated learner."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import adapters
from .adapters.impl import AuthError, AuthUnavailable
from .db import get_db
from .adapters.base import Principal
from .config import settings
from .models import Learner


def current_learner(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)) -> Learner:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in first.")
    token = authorization.split(None, 1)[1]
    try:
        principal = adapters.auth().authenticate(db, token)
    except AuthUnavailable as exc:
        raise HTTPException(503, str(exc))
    except AuthError as exc:
        raise HTTPException(401, str(exc))
    lr = db.get(Learner, principal.learner_id)
    if lr is None:
        raise HTTPException(401, "unknown learner")
    return lr


def current_account(authorization: Optional[str] = Header(default=None)) -> Principal:
    """The signed-in person, WITHOUT creating or requiring a learner row (mentors and admins are accounts, not necessarily learners)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in first.")
    try:
        return adapters.auth().verify_token(authorization.split(None, 1)[1])
    except AuthUnavailable as exc:
        raise HTTPException(503, str(exc))
    except AuthError as exc:
        raise HTTPException(401, str(exc))


def current_admin(principal: Principal = Depends(current_account)) -> Principal:
    """Safeguarding lead / admin: the account id must be listed in SAARTHI_ADMINS (ids only; e-mail addresses are never trusted)."""
    if principal.learner_id not in settings.admin_ids:
        raise HTTPException(403, "Not allowed.")
    return principal
