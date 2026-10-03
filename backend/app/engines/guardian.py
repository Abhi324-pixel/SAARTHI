"""Real guardian consent for learners under 18 (spec docs/features/D01).

Flow: the minor gives a guardian e-mail -> `send_request` mails a signed, single-use link -> the guardian opens a public page
(no account) -> `preview` / `decide` (approve or decline) -> after approval `withdraw` is possible from a long-lived link.
The signed token only ever travels to the guardian's inbox, never to the learner's own session. Every invalid, used, expired
or tampered link gets the SAME answer, so nothing can be probed.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Optional

from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import adapters
from ..config import settings
from ..models import Consent, Learner, MentorCase, now
from ..models_ext.D01 import ConsentToken, GuardianRequest, mask_email
from . import audit, escalation, notify

APPROVE_TTL = 7 * 86400
WITHDRAW_TTL = 365 * 86400
MAX_REQUESTS_PER_LEARNER_PER_DAY = 3
ADDRESS_COOLDOWN_MIN = 10
MAX_REQUESTS_PER_ADDRESS_PER_DAY = 5
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")

SCOPE_TEXT = {
    "english": "talk to a SAARTHI mentor in a private, text-only case chat inside the app",
    "hindi": "ऐप के अंदर एक निजी, सिर्फ़ टेक्स्ट वाली केस चैट में SAARTHI मेंटर से बात करना",
}
MENTORS_SEE = {
    "english": ["Their first name, age group (under 18), language and learning goal",
                "Which topic they are stuck on, their recent practice results and misconceptions",
                "Only what the learner chooses to share from their conversations"],
    "hindi": ["उनका पहला नाम, आयु वर्ग (18 से कम), भाषा और सीखने का लक्ष्य",
              "वे किस विषय पर अटके हैं, हाल के अभ्यास के नतीजे और ग़लत धारणाएँ",
              "बातचीत का सिर्फ़ वही हिस्सा जो सीखने वाला ख़ुद साझा करे"],
}


class GuardianError(Exception):
    """A rejected request; `status` is the HTTP status the route should use."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


class InvalidLink(Exception):
    """The link is not usable (unknown, tampered, expired, used, withdrawn). Deliberately says nothing more."""


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret, salt="saarthi-guardian-link-v2")


def _mint(db: Session, req: GuardianRequest, purpose: str) -> str:
    tok = ConsentToken(request_id=req.id, purpose=purpose)
    db.add(tok)
    db.flush()
    return _serializer().dumps({"t": tok.token_id, "r": req.id, "p": purpose})


def _open(db: Session, token: str, purpose: str) -> tuple[GuardianRequest, ConsentToken, Learner]:
    try:
        data = _serializer().loads(token or "", max_age=APPROVE_TTL if purpose == "approve" else WITHDRAW_TTL)
        row = db.get(ConsentToken, data["t"])
        req = db.get(GuardianRequest, data["r"])
        if data.get("p") != purpose or row is None or req is None or row.purpose != purpose or row.request_id != req.id or row.used_at:
            raise InvalidLink()
        if purpose == "approve" and req.status != "sent":
            raise InvalidLink()
        if purpose == "withdraw" and req.status != "approved":
            raise InvalidLink()
        learner = db.get(Learner, req.learner_id)
        if learner is None:
            raise InvalidLink()
        return req, row, learner
    except (BadSignature, KeyError, TypeError):
        raise InvalidLink() from None


def _email_text(lang: str, first_name: str, link: str, days: int) -> tuple[str, str]:
    if lang == "hindi":
        return (f"{first_name} को SAARTHI मेंटर से बात करने के लिए आपकी अनुमति चाहिए",
                f"नमस्ते,\n\n{first_name} (18 वर्ष से कम) SAARTHI नाम के सीखने वाले ऐप में एक मेंटर से मदद लेना चाहते हैं। "
                f"नियमों के अनुसार इसके लिए माता-पिता या अभिभावक की अनुमति ज़रूरी है।\n\n"
                f"क्या होगा: एक निजी, सिर्फ़ टेक्स्ट वाली चैट, जो ऐप के अंदर ही रहती है; संपर्क-विवरण साझा करना रोका जाता है; सारी बातचीत दर्ज होती है।\n\n"
                f"देखने और निर्णय लेने के लिए (लॉगिन की ज़रूरत नहीं): {link}\n\n"
                f"यह लिंक {days} दिन तक चलेगा और एक ही बार इस्तेमाल हो सकता है। अगर आप इस व्यक्ति को नहीं जानते, तो इस ईमेल को अनदेखा करें; कुछ नहीं होगा।")
    return (f"{first_name} needs your OK to talk to a SAARTHI mentor",
            f"Hello,\n\n{first_name} (under 18) would like help from a mentor in SAARTHI, a learning app. Because they are under 18, "
            f"a parent or guardian has to approve this first.\n\n"
            f"What it means: a private, text-only chat that stays inside the app; sharing contact details is blocked; all messages are logged.\n\n"
            f"To see the details and decide (no account needed): {link}\n\n"
            f"The link works for {days} days and can be used once. If you do not know this person, ignore this e-mail; nothing will happen.")


def send_request(db: Session, learner: Learner, scope: str, email: str, lang: str = "english") -> str:
    """Create the request, mint the single-use link and mail it. Returns the masked address for the learner's screen."""
    email = (email or "").strip()
    if not _EMAIL.match(email) or len(email) > 200:
        raise GuardianError(422, "Please enter a valid e-mail address for your parent or guardian.")
    if learner.email and email.lower() == learner.email.lower():
        raise GuardianError(422, "Please use your parent or guardian's own e-mail address, not yours.")
    if lang not in ("english", "hindi"):
        lang = "hindi" if lang == "hinglish" else "english"
    day_ago = now() - timedelta(days=1)
    if (db.scalar(select(func.count()).select_from(GuardianRequest).where(
            GuardianRequest.learner_id == learner.id, GuardianRequest.created_at > day_ago)) or 0) >= MAX_REQUESTS_PER_LEARNER_PER_DAY:
        raise GuardianError(429, "You have asked a few times today. Please wait until tomorrow or check your guardian's inbox.")
    same = select(func.count()).select_from(GuardianRequest).where(func.lower(GuardianRequest.guardian_email) == email.lower())
    if (db.scalar(same.where(GuardianRequest.created_at > now() - timedelta(minutes=ADDRESS_COOLDOWN_MIN))) or 0) >= 1:
        raise GuardianError(429, "A message was just sent to that address. Please wait a few minutes before asking again.")
    if (db.scalar(same.where(GuardianRequest.created_at > day_ago)) or 0) >= MAX_REQUESTS_PER_ADDRESS_PER_DAY:
        raise GuardianError(429, "That address has received several requests today. Please try again tomorrow.")

    for old in db.scalars(select(GuardianRequest).where(
            GuardianRequest.learner_id == learner.id, GuardianRequest.scope == scope, GuardianRequest.status == "sent")):
        old.status = "superseded"
    req = GuardianRequest(learner_id=learner.id, scope=scope, guardian_email=email, lang=lang,
                          expires_at=now() + timedelta(seconds=APPROVE_TTL))
    db.add(req)
    db.flush()
    token = _mint(db, req, "approve")
    link = f"{settings.public_base_url.rstrip('/')}/guardian/{token}"
    first = (learner.name or "A learner").split()[0]
    subject, body = _email_text(lang, first, link, APPROVE_TTL // 86400)
    adapters.mailer().send(email, subject, body)       # a delivery failure raises: the request must not look "sent" when it was not
    audit.record(db, actor_id=learner.id, actor_role="learner", action="consent_requested", subject_type="guardian_request",
                 subject_id=req.id, detail={"scope": scope, "lang": lang})
    return mask_email(email)


def current_request(db: Session, learner: Learner, scope: str) -> Optional[dict[str, Any]]:
    req = db.scalars(select(GuardianRequest).where(GuardianRequest.learner_id == learner.id, GuardianRequest.scope == scope)
                     .order_by(GuardianRequest.created_at.desc())).first()
    if req is None:
        return None
    return {"status": req.status, "masked_email": mask_email(req.guardian_email) or None,
            "sent_at": req.created_at.isoformat(timespec="minutes"),
            "can_resend_at": (req.created_at + timedelta(minutes=ADDRESS_COOLDOWN_MIN)).isoformat(timespec="minutes")}


def preview(db: Session, token: str) -> dict[str, Any]:
    req, _, learner = _open(db, token, "approve")
    lang = req.lang
    audit.record(db, actor_id="guardian", actor_role="guardian", action="consent_link_viewed", subject_type="guardian_request", subject_id=req.id)
    return {"learner_first_name": (learner.name or "A learner").split()[0], "lang": lang,
            "scope_text": SCOPE_TEXT[lang], "mentors_see": MENTORS_SEE[lang], "expires_at": req.expires_at.isoformat(timespec="minutes")}


def decide(db: Session, token: str, decision: str) -> dict[str, Any]:
    if decision not in ("approve", "decline"):
        raise InvalidLink()
    req, row, learner = _open(db, token, "approve")
    row.used_at = now()
    req.decided_at = now()
    c = db.get(Consent, (learner.id, req.scope))
    if c is None:
        c = Consent(learner_id=learner.id, scope=req.scope, is_mock=False)
        db.add(c)
    c.updated_at = now()
    out: dict[str, Any] = {"decision": decision}
    if decision == "approve":
        req.status, c.status, c.granted_by = "approved", "granted", "guardian"
        out["withdraw_token"] = _mint(db, req, "withdraw")
        db.flush()
        if req.scope == "mentor_sessions":
            escalation.resume_after_consent(db, learner)
    else:
        req.status, c.status, c.granted_by = "declined", "declined", "guardian"
        req.guardian_email = ""
    db.flush()
    audit.record(db, actor_id="guardian", actor_role="guardian", action=f"consent_{decision}d", subject_type="guardian_request", subject_id=req.id)
    notify.notify(db, learner.id, "consent_granted" if decision == "approve" else "consent_declined", {}, "/mentors", dedupe_key=f"consent:{req.id}")
    return out


def withdraw(db: Session, token: str) -> dict[str, Any]:
    req, row, learner = _open(db, token, "withdraw")
    row.used_at = now()
    req.status, req.decided_at, req.guardian_email = "withdrawn", now(), ""
    c = db.get(Consent, (learner.id, req.scope))
    if c is not None:
        c.status, c.granted_by, c.updated_at = "revoked", "guardian", now()
    paused = 0
    if req.scope == "mentor_sessions":
        for case in db.scalars(select(MentorCase).where(MentorCase.learner_id == learner.id,
                                                        MentorCase.status.in_(("open", "matched", "accepted", "scheduled")))):
            case.status, case.updated_at = "awaiting_consent", now()
            paused += 1
    db.flush()
    audit.record(db, actor_id="guardian", actor_role="guardian", action="consent_withdrawn", subject_type="guardian_request",
                 subject_id=req.id, detail={"cases_paused": paused})
    notify.notify(db, learner.id, "consent_withdrawn", {}, "/mentors", dedupe_key=f"consent:{req.id}:withdrawn")
    return {"withdrawn": True}
