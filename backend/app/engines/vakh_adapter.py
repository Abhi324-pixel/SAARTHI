"""Vakh integration adapter: challenge links, signed review webhook, and evidence ingestion.

Connects a reviewed Vakh submission to SAARTHI's one evidence pipeline (`mastery.apply_evidence`) and the adaptive roadmap.

Safety rules (each has a test in tests/test_vakh_security.py):
- Nothing is assumed about Vakh. With no VAKH_BASE_URL or no VAKH_WEBHOOK_SECRET the feature is off and says so.
- A review is accepted only with a valid HMAC-SHA256 signature of the exact request body. There is no shipped default secret
  and no "send the secret itself" shortcut.
- The learner is identified by an opaque signed `state` token that SAARTHI put in the launch link, so the learner's internal
  id is never put in a URL sent to a third party.
- Only a FINAL review with a real numeric score becomes evidence. No score means no evidence (nothing is invented), and a
  rejected review is never credited.
- Bad input is a clear 4xx error, never a 500 with internal text.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import AliasChoices, BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..content import get_content
from ..models import Learner, now
from ..models_ext.G01 import VakhSubmission, VakhChallenge
from . import challenge_generator, mastery, planner

log = logging.getLogger("saarthi.vakh")

STATE_MAX_AGE_S = 30 * 24 * 3600
APPROVED = {"approved", "reviewed", "passed", "accepted"}
REJECTED = {"rejected", "failed", "changes_requested", "needs_changes"}
FINAL = APPROVED | REJECTED


class VakhError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class VakhEvent(BaseModel):
    """What SAARTHI accepts from Vakh. Anything else is refused with a 422 instead of being guessed at."""
    post_id: str = Field(min_length=1, max_length=120, validation_alias=AliasChoices("post_id", "vakh_post_id"))
    state: Optional[str] = Field(default=None, max_length=600)
    learner_id: Optional[str] = Field(default=None, max_length=64)
    concept_id: Optional[str] = Field(default=None, max_length=64)
    challenge_id: Optional[str] = Field(default=None, max_length=64)
    status: str = Field(default="reviewed", max_length=24)
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    submission_url: str = Field(default="", max_length=400)
    review_notes: str = Field(default="", max_length=2000, validation_alias=AliasChoices("review_notes", "feedback"))
    reviewer_type: str = Field(default="mentor", max_length=24)


# ---------------------------------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------------------------------

def base_url() -> Optional[str]:
    """The configured Vakh address, or None (also None when it is not a safe web address)."""
    u = (settings.vakh_base_url or "").strip().rstrip("/")
    if not u:
        return None
    if u.startswith("https://") or (not settings.is_prod and (u.startswith("http://localhost") or u.startswith("http://127.0.0.1"))):
        return u
    return None


def launch_ready() -> bool:
    return bool(settings.vakh_enabled and base_url())


def webhook_ready() -> bool:
    return bool(settings.vakh_enabled and (settings.vakh_webhook_secret or "").strip())


# ---------------------------------------------------------------------------------------------------
# launch link (opaque state, no internal ids in the URL)
# ---------------------------------------------------------------------------------------------------

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret, salt="saarthi-vakh-launch")


def make_state(learner_id: str, concept_id: str) -> str:
    return _serializer().dumps({"l": learner_id, "c": concept_id})


def read_state(token: str) -> tuple[str, str]:
    try:
        d = _serializer().loads(token, max_age=STATE_MAX_AGE_S)
        return str(d["l"]), str(d["c"])
    except SignatureExpired:
        raise VakhError(400, "This Vakh link has expired. Please open the challenge again from SAARTHI.")
    except (BadSignature, KeyError, TypeError):
        raise VakhError(400, "The Vakh link could not be verified.")


def get_vakh_launcher_url(
    db: Session,
    learner: Learner,
    concept_id: str
) -> dict[str, Any]:
    """The challenge SAARTHI generated for this concept, and (only if Vakh is configured) the link to open it on Vakh.

    Whether Vakh pre-fills a form from the link is not confirmed, so the link carries one opaque `state` value and nothing else."""
    if concept_id not in get_content().concepts:
        raise VakhError(404, "Unknown concept.")
    ch = challenge_generator.get_or_create_challenge(db, concept_id, learner)
    out: dict[str, Any] = {"challenge": ch, "concept_id": concept_id, "configured": launch_ready(), "launch_url": None, "prefill_verified": False}
    if not launch_ready():
        out["message"] = "Vakh is not connected yet, so this challenge cannot be opened there. You can still build it yourself using the requirements above."
        return out
    form_id = quote(str(ch.get("vakh_form_id") or f"vakh_form_{concept_id}"), safe="")
    out["vakh_form_id"] = form_id
    out["launch_url"] = f"{base_url()}/forms/{form_id}?state={quote(make_state(learner.id, concept_id), safe='')}"
    return out


def verify_webhook_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """HMAC-SHA256 of the exact request body, compared in constant time. No signature, no secret, or a mismatch all fail."""
    secret = (settings.vakh_webhook_secret or "").strip()
    if not secret or not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    given = signature_header.strip().removeprefix("sha256=")
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def sign_body(payload_bytes: bytes) -> str:
    """Helper for tests and for documenting the contract: the header value Vakh must send."""
    return "sha256=" + hmac.new((settings.vakh_webhook_secret or "").encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def process_vakh_webhook(
    db: Session,
    payload: dict[str, Any],
    raw_body: bytes,
    signature: Optional[str]
) -> dict[str, Any]:
    """Idempotently turns a final Vakh review into evidence."""
    if not webhook_ready():
        raise VakhError(503, "The Vakh integration is not configured on this server.")
    if not verify_webhook_signature(raw_body, signature):
        raise VakhError(401, "Invalid Vakh signature.")
    try:
        ev = VakhEvent.model_validate(payload)
    except ValidationError as e:
        bad = ", ".join(sorted({str(x["loc"][-1]) for x in e.errors()})) or "payload"
        raise VakhError(422, f"Invalid Vakh event (check: {bad}).")

    # who and what: the signed state token wins; otherwise the (already signature-protected) ids in the body
    if ev.state:
        learner_id, concept_id = read_state(ev.state)
        if ev.concept_id and ev.concept_id != concept_id:
            raise VakhError(422, "The event's concept does not match the link it came from.")
    else:
        learner_id, concept_id = ev.learner_id, ev.concept_id
    if not learner_id or not concept_id:
        raise VakhError(422, "Invalid Vakh event (a state token, or learner_id and concept_id, is required).")
    if concept_id not in get_content().concepts:
        raise VakhError(422, "Invalid Vakh event (unknown concept).")

    status = ev.status.strip().lower()
    if status not in FINAL:
        return {"ok": True, "recorded": False, "message": "Not a final review yet; nothing was recorded."}

    existing = db.scalars(select(VakhSubmission).where(VakhSubmission.vakh_post_id == ev.post_id)).first()
    if existing:
        log.info("Vakh post %s was already processed; skipping.", ev.post_id)
        return {"ok": True, "already_processed": True, "submission_id": existing.id, "message": "Submission already recorded; no duplicate evidence applied."}

    learner = db.get(Learner, learner_id)
    if not learner:
        raise VakhError(404, "Learner not found.")

    # A numeric score from the reviewer is the only thing that can become evidence. Nothing is invented.
    if ev.score is None and status in APPROVED:
        raise VakhError(422, "A reviewed submission needs a numeric score between 0 and 1; no evidence was recorded.")
    challenge_id = ev.challenge_id or f"vch_{concept_id}"
    evidence_id: Optional[str] = None
    p_after = None
    if ev.score is not None:
        res = mastery.apply_evidence(
            db=db, learner=learner, concept_id=concept_id, source_type="work_product", score=float(ev.score),
            stated_confidence=5, grader=f"vakh:{ev.reviewer_type}", item_id=f"vakh:{ev.post_id}",
            detail={"vakh_post_id": ev.post_id, "challenge_id": challenge_id, "submission_url": ev.submission_url,
                    "reviewer_feedback": ev.review_notes, "reviewer_type": ev.reviewer_type, "status": status},
        )
        evidence_id, p_after = res.get("evidence_id"), res.get("p_after")
    sub = VakhSubmission(
        learner_id=learner.id, challenge_id=challenge_id, concept_id=concept_id, vakh_post_id=ev.post_id,
        submission_url=ev.submission_url, score=ev.score, status="rejected" if status in REJECTED else "reviewed",
        reviewer_type=ev.reviewer_type, reviewer_feedback=ev.review_notes or "Review received from Vakh.",
        evidence_event_id=evidence_id, reviewed_at=now(),
    )
    db.add(sub)
    db.commit()

    out: dict[str, Any] = {"ok": True, "already_processed": False, "submission_id": sub.id, "evidence_id": evidence_id, "new_mastery": p_after,
                           "recorded": True, "evidence_recorded": evidence_id is not None}
    if evidence_id is not None:
        rm = planner.refresh(db=db, learner=learner, trigger=f"Vakh build review on {concept_id} (score {int(float(ev.score) * 100)}%)", force=True)
        out.update({"roadmap_version": rm["version"], "roadmap_change": rm.get("change_reason", "")})
    log.info("Vakh submission %s processed for a learner on %s (evidence=%s)", ev.post_id, concept_id, evidence_id is not None)
    return out
