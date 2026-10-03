"""Write one audit row. Never raises into the caller's transaction for a logging problem."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models_ext.audit import AuditLog

log = logging.getLogger("saarthi.audit")


def record(db: Session, *, actor_id: str, actor_role: str, action: str, subject_type: str = "", subject_id: str = "",
           detail: Optional[dict[str, Any]] = None) -> None:
    try:
        with db.begin_nested():
            db.add(AuditLog(actor_id=actor_id, actor_role=actor_role, action=action, subject_type=subject_type,
                            subject_id=subject_id, detail=detail or {}))
    except Exception:  # noqa: BLE001 - an audit failure must not break the action it describes
        log.exception("could not write audit row %s", action)
