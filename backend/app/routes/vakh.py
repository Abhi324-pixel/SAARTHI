"""Vakh Integration Router: endpoints for Vakh challenge launch, specs, and webhook ingestion."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..content import get_content
from ..deps import current_learner, get_db
from ..engines import challenge_generator, vakh_adapter
from ..models import Learner

log = logging.getLogger("saarthi.vakh")
router = APIRouter(prefix="/api/vakh", tags=["vakh"])


@router.post("/webhook")
async def vakh_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_vakh_signature: Optional[str] = Header(None, alias="X-Vakh-Signature"),
):
    """Receives a final review from Vakh. Needs `X-Vakh-Signature: sha256=<HMAC-SHA256 of the raw body with VAKH_WEBHOOK_SECRET>`.

    Idempotent per `post_id`. Records evidence only for a final review with a real score."""
    raw_body = await request.body()
    if len(raw_body) > 20_000:
        raise HTTPException(413, "Payload too large")
    try:
        payload = json.loads(raw_body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(400, "Invalid JSON payload")
    try:
        return vakh_adapter.process_vakh_webhook(db, payload, raw_body, x_vakh_signature)
    except vakh_adapter.VakhError as ve:
        raise HTTPException(ve.status, ve.message)
    except Exception:
        log.exception("Vakh webhook failed")
        raise HTTPException(500, "The Vakh event could not be processed.")


@router.get("/launch/{concept_id}")
def vakh_launch(
    concept_id: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db)
):
    """The challenge for this concept and, when Vakh is configured, the link that opens it on Vakh."""
    try:
        return vakh_adapter.get_vakh_launcher_url(db, lr, concept_id)
    except vakh_adapter.VakhError as ve:
        raise HTTPException(ve.status, ve.message)


@router.get("/challenges/{concept_id}")
def get_challenge(
    concept_id: str,
    lr: Learner = Depends(current_learner),
    db: Session = Depends(get_db)
):
    """Retrieves the tailored practical challenge specification for a concept."""
    if concept_id not in get_content().concepts:
        raise HTTPException(404, "Unknown concept.")
    return challenge_generator.get_or_create_challenge(db, concept_id, lr)
