"""Live updates in the mentor case chat (C04).

Endpoints:
  GET /api/cases/{case_id}/state
  GET /api/cases/{case_id}/messages?since=...
  GET /api/mentor-console/cases/{case_id}/state
  GET /api/mentor-console/cases/{case_id}/messages?since=...
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_learner
from ..models import CaseMessage, Learner, Mentor, MentorCase
from .mentor_console import current_mentor

router = APIRouter(prefix="/api")


def _learner_case(db: Session, lr: Learner, case_id: str) -> MentorCase:
    case = db.get(MentorCase, case_id)
    if case is None or case.learner_id != lr.id:
        raise HTTPException(404, "case not found")
    return case


def _mentor_case(db: Session, m: Mentor, case_id: str) -> MentorCase:
    case = db.get(MentorCase, case_id)
    if case is None or case.mentor_id != m.id:
        raise HTTPException(404, "case not found")
    return case


def _parse_since(since_str: Optional[str]) -> Optional[datetime]:
    if not since_str:
        return None
    try:
        dt = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        raise HTTPException(400, "invalid since timestamp, expected ISO-8601")


def _case_state_response(case: MentorCase, db: Session, request: Request) -> Response:
    row = db.execute(
        select(
            func.count(CaseMessage.id),
            func.max(CaseMessage.created_at),
        ).where(
            CaseMessage.case_id == case.id,
            CaseMessage.screened == True,
        )
    ).one()
    count = row[0] or 0
    max_created_at: Optional[datetime] = row[1]

    max_iso = max_created_at.isoformat() if max_created_at else "none"
    etag_raw = f"{case.id}:{case.status}:{case.updated_at.isoformat()}:{count}:{max_iso}"
    etag = hashlib.sha256(etag_raw.encode()).hexdigest()

    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        client_etag = if_none_match.strip().strip('"')
        if client_etag == etag:
            return Response(status_code=304, headers={"ETag": f'"{etag}"'})

    content = {
        "status": case.status,
        "updated_at": case.updated_at.isoformat(),
        "last_message_at": max_created_at.isoformat() if max_created_at else None,
        "message_count": count,
    }
    return JSONResponse(content=content, headers={"ETag": f'"{etag}"'})


def _case_messages_response(case: MentorCase, since_str: Optional[str], db: Session) -> dict:
    q = select(CaseMessage).where(
        CaseMessage.case_id == case.id,
        CaseMessage.screened == True,
    )
    if since_str:
        since_dt = _parse_since(since_str)
        if since_dt:
            q = q.where(CaseMessage.created_at > since_dt)

    q = q.order_by(CaseMessage.created_at.asc(), CaseMessage.id.asc()).limit(100)
    msgs = list(db.scalars(q))

    next_since = msgs[-1].created_at.isoformat() if msgs else since_str

    return {
        "messages": [
            {
                "id": m.id,
                "sender": m.sender,
                "text": m.text,
                "is_mock": m.is_mock,
                "at": m.created_at.isoformat(timespec="minutes"),
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
        "next_since": next_since,
    }


@router.get("/cases/{case_id}/state")
def learner_case_state(
    case_id: str,
    request: Request,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    case = _learner_case(db, lr, case_id)
    return _case_state_response(case, db, request)


@router.get("/cases/{case_id}/messages")
def learner_case_messages(
    case_id: str,
    since: Optional[str] = Query(default=None),
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db),
):
    case = _learner_case(db, lr, case_id)
    return _case_messages_response(case, since, db)


@router.get("/mentor-console/cases/{case_id}/state")
def mentor_case_state(
    case_id: str,
    request: Request,
    m: Mentor = Depends(current_mentor),
    db: Session = Depends(get_db),
):
    case = _mentor_case(db, m, case_id)
    return _case_state_response(case, db, request)


@router.get("/mentor-console/cases/{case_id}/messages")
def mentor_case_messages(
    case_id: str,
    since: Optional[str] = Query(default=None),
    m: Mentor = Depends(current_mentor),
    db: Session = Depends(get_db),
):
    case = _mentor_case(db, m, case_id)
    return _case_messages_response(case, since, db)
