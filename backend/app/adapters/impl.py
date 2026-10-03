"""Mock and real implementations of the ports. Same interface, same contract tests."""

from __future__ import annotations

import hashlib

import json
import logging
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Optional

import jwt
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SEED_DIR, settings
from ..engines import cohort as cohort_engine
from ..engines import safeguarding
from ..models import CohortMember, Consent, Learner, Mentor, new_id, now
from .base import MentorRecord, Principal

CONSENT_SCOPES = ("mentor_sessions", "transcript_share")
_log = logging.getLogger("saarthi.auth")


# ===================================================================================================
# auth
# ===================================================================================================

class AuthError(Exception):
    pass


class MockAuth:
    """Dev login: name + age + language -> a signed token. Creates a `mock_` learner. NOT for production."""
    name = "mock"
    is_mock = True

    def login(self, db: Session, *, name: str, age: int, language: str, email: Optional[str]) -> dict[str, Any]:
        lr = Learner(id=new_id("mock_"), name=name.strip()[:80] or "Learner", email=email, age=age,
                     language_pref=language if language in ("english", "hindi", "hinglish") else "english", is_mock=True)
        db.add(lr)
        db.flush()
        tok = jwt.encode({"sub": lr.id, "name": lr.name, "iat": int(time.time()), "mock": True}, settings.secret, algorithm="HS256")
        return {"token": tok, "learner_id": lr.id}

    def authenticate(self, db: Session, token: str) -> Principal:
        try:
            claims = jwt.decode(token, settings.secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise AuthError("invalid token") from exc
        if not claims.get("mock"):
            raise AuthError("not a mock-login token")
        lr = db.get(Learner, claims["sub"])
        if lr is None:
            raise AuthError("unknown learner")
        return Principal(learner_id=lr.id, name=lr.name, email=lr.email, is_mock=True)

    def verify_token(self, token: str) -> Principal:
        try:
            claims = jwt.decode(token, settings.secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise AuthError("invalid token") from exc
        if not claims.get("mock"):
            raise AuthError("not a mock-login token")
        return Principal(learner_id=claims["sub"], name=claims.get("name", ""), email=None, is_mock=True)


class AuthUnavailable(Exception):
    """The auth backend (JWKS endpoint) could not be reached. Mapped to HTTP 503, NOT 401, so a brief outage
    does not make the browser throw away a perfectly good session."""


SUPABASE_ASYMMETRIC_ALGS = ["ES256", "RS256"]


class SupabaseAuth:
    """Verifies Supabase access tokens signed with the project's asymmetric JWT Signing Keys.

    Keys come from {SUPABASE_URL}/auth/v1/.well-known/jwks.json (cached; chosen by the token's `kid`). Allowed algorithms are
    ES256 and RS256 only; audience must be "authenticated" and issuer {SUPABASE_URL}/auth/v1. HS256 with SUPABASE_JWT_SECRET is
    accepted ONLY if that optional setting is present (for projects still on the legacy shared secret). First sight of a user
    creates the learner row from the token's user_metadata (name, age, language).
    """
    name = "supabase"
    is_mock = False

    def __init__(self, jwks_client: Any = None) -> None:
        if not settings.supabase_url:
            raise RuntimeError("SAARTHI_AUTH=supabase but SUPABASE_URL is not set (e.g. https://<project-ref>.supabase.co)")
        self.issuer = settings.supabase_url.rstrip("/") + "/auth/v1"
        self.jwks_url = self.issuer + "/.well-known/jwks.json"
        self._jwks = jwks_client or jwt.PyJWKClient(self.jwks_url, cache_keys=True, cache_jwk_set=True, lifespan=600, timeout=5)

    def login(self, db, *, name, age, language, email):
        raise AuthError("Sign-in happens through Supabase Auth in the browser; the backend only verifies tokens.")

    def _verify(self, token: str) -> dict[str, Any]:
        try:
            alg = jwt.get_unverified_header(token).get("alg")
        except jwt.PyJWTError as exc:
            raise AuthError("invalid token") from exc
        common = {"audience": "authenticated", "issuer": self.issuer, "options": {"require": ["exp", "sub"]}}
        try:
            if alg == "HS256":
                if not settings.supabase_jwt_secret:
                    raise AuthError("HS256 tokens are not accepted (no SUPABASE_JWT_SECRET configured)")
                return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], **common)
            if alg in SUPABASE_ASYMMETRIC_ALGS:
                try:
                    key = self._jwks.get_signing_key_from_jwt(token).key
                except jwt.PyJWKClientConnectionError as exc:
                    raise AuthUnavailable("could not fetch Supabase signing keys") from exc
                except jwt.PyJWKClientError as exc:
                    _log.warning("sign-in token rejected: alg=%s reason=unknown signing key (%s)", alg, exc)
                    raise AuthError("unknown signing key") from exc
                return jwt.decode(token, key, algorithms=SUPABASE_ASYMMETRIC_ALGS, **common)
        except jwt.PyJWTError as exc:
            _log.warning("sign-in token rejected: alg=%s reason=%s", alg, exc)      # the reason only; never the token
            raise AuthError("invalid token") from exc
        raise AuthError("unsupported token algorithm")

    def verify_token(self, token: str) -> Principal:
        """Who is this? Verifies the token exactly like `authenticate` but never creates a learner row."""
        claims = self._verify(token)
        meta = claims.get("user_metadata") or {}
        name = meta.get("name") or meta.get("full_name") or (claims.get("email") or "").split("@")[0]
        return Principal(learner_id=claims["sub"], name=str(name)[:120], email=claims.get("email"), is_mock=False)

    def authenticate(self, db: Session, token: str) -> Principal:
        claims = self._verify(token)
        uid = claims["sub"]
        lr = db.get(Learner, uid)
        if lr is None:
            meta = claims.get("user_metadata") or {}
            # Age is only trusted when the sign-up supplied a sensible one (e-mail sign-up does; Google does not). Otherwise the
            # learner is treated as a minor until they complete their profile (engines/safeguarding.py, POST /api/me/complete-profile).
            try:
                age = int(meta.get("age"))
                confirmed = safeguarding.MIN_AGE <= age <= safeguarding.MAX_AGE
            except (TypeError, ValueError):
                age, confirmed = 0, False
            if not confirmed:
                age = safeguarding.UNCONFIRMED_PLACEHOLDER_AGE
            lang = meta.get("language") if meta.get("language") in ("english", "hindi", "hinglish") else "english"
            provider = (claims.get("app_metadata") or {}).get("provider")
            display = meta.get("name") or meta.get("full_name") or (claims.get("email") or "Learner").split("@")[0]
            lr = Learner(id=uid, name=str(display)[:80], email=claims.get("email"), age=age, language_pref=lang, is_mock=False,
                         settings={"age_confirmed": confirmed, "signup_provider": provider or "email"})
            db.add(lr)
            db.flush()
        return Principal(learner_id=lr.id, name=lr.name, email=lr.email, is_mock=False)


# ===================================================================================================
# mentors
# ===================================================================================================

def _load_mentor_fixtures() -> list[MentorRecord]:
    raw = json.loads((SEED_DIR / "mentors.json").read_text(encoding="utf-8"))["mentors"]
    return [MentorRecord(is_mock=True, **m) for m in raw]


class MockMentorDirectory:
    name = "mock"
    is_mock = True

    def list(self, db: Session, tier: Optional[str] = None) -> list[MentorRecord]:
        return [m for m in _load_mentor_fixtures() if tier in (None, m.tier)]

    def get(self, db: Session, mentor_id: str) -> Optional[MentorRecord]:
        return next((m for m in _load_mentor_fixtures() if m.id == mentor_id), None)


def _row_to_record(r: Mentor) -> MentorRecord:
    return MentorRecord(id=r.id, name=r.name, tier=r.tier, headline=r.headline, bio=r.bio, expertise=list(r.expertise or []),
                        languages=list(r.languages or []), availability=list(r.availability or []),
                        verification_status=r.verification_status, active_case_cap=r.active_case_cap, is_mock=r.is_mock)


class DbMentorDirectory:
    name = "db"
    is_mock = False

    def list(self, db: Session, tier: Optional[str] = None) -> list[MentorRecord]:
        q = select(Mentor)
        if tier:
            q = q.where(Mentor.tier == tier)
        return [_row_to_record(r) for r in db.scalars(q.order_by(Mentor.id))]

    def get(self, db: Session, mentor_id: str) -> Optional[MentorRecord]:
        r = db.get(Mentor, mentor_id)
        return _row_to_record(r) if r else None


def seed_mentors(db: Session) -> int:
    """Load the mock fixtures into the mentors table (used by scripts/seed.py and the contract tests)."""
    n = 0
    for m in _load_mentor_fixtures():
        if db.get(Mentor, m.id) is None:
            db.add(Mentor(id=m.id, name=m.name, tier=m.tier, headline=m.headline, bio=m.bio, expertise=m.expertise,
                          languages=m.languages, availability=m.availability, verification_status=m.verification_status,
                          active_case_cap=m.active_case_cap, is_mock=True))
            n += 1
    db.flush()
    return n


# ===================================================================================================
# consent
# ===================================================================================================

def _consent_row(db: Session, learner_id: str, scope: str) -> Optional[Consent]:
    return db.get(Consent, (learner_id, scope))


def _guardian_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret, salt="saarthi-guardian-consent")


def mint_guardian_token(learner: Learner, scope: str) -> str:
    """Signed token that proves a guardian approved `scope` for `learner`.

    Internal. Only the code that DELIVERS the link to the guardian (e-mail; see docs/features/D01) may hold this. It must never
    be returned to the learner's own session: whoever holds it can call `DbConsent.grant`, so handing it to the minor lets
    the minor approve themselves.
    """
    return _guardian_serializer().dumps({"learner": learner.id, "scope": scope})


class _ConsentBase:
    is_mock = False
    name = "db"

    def status(self, db: Session, learner: Learner, scope: str) -> str:
        if scope not in CONSENT_SCOPES:
            raise ValueError("unknown consent scope")
        if not safeguarding.is_minor(learner) and scope == "mentor_sessions":
            return "granted"  # adults consent for themselves by using the feature
        row = _consent_row(db, learner.id, scope)
        return row.status if row else "pending"

    def _set(self, db: Session, learner: Learner, scope: str, status: str, by: str) -> Consent:
        row = _consent_row(db, learner.id, scope)
        if row is None:
            row = Consent(learner_id=learner.id, scope=scope, is_mock=self.is_mock)
            db.add(row)
        row.status, row.granted_by, row.updated_at = status, by, now()
        db.flush()
        return row

    def request(self, db: Session, learner: Learner, scope: str, guardian_email: Optional[str] = None,
                lang: str = "english") -> dict[str, Any]:
        st = self.status(db, learner, scope)
        out: dict[str, Any] = {"scope": scope, "status": st, "needs_guardian": safeguarding.is_minor(learner) and st != "granted"}
        if out["needs_guardian"] and self.is_mock:
            # Demo only. The real adapter must NEVER return the token to the learner (they could approve themselves);
            # it is meant for the guardian's e-mail (D01) and, until that exists, real consent simply stays "pending".
            out["guardian_token"] = mint_guardian_token(learner, scope)
        return out

    def revoke(self, db: Session, learner: Learner, scope: str) -> dict[str, Any]:
        self._set(db, learner, scope, "revoked", "learner")
        return {"scope": scope, "status": "revoked"}


class DbConsent(_ConsentBase):
    """Real flow: the guardian receives a signed single-use link by e-mail; only a valid token can grant (engines/guardian.py)."""
    name = "db"
    is_mock = False

    def request(self, db: Session, learner: Learner, scope: str, guardian_email: Optional[str] = None,
                lang: str = "english") -> dict[str, Any]:
        out = super().request(db, learner, scope)          # {scope, status, needs_guardian} - never a token
        out["guardian_hint"] = None
        if out["needs_guardian"] and guardian_email:
            from ..engines import guardian
            out["guardian_hint"] = guardian.send_request(db, learner, scope, guardian_email, lang)
            out["status"] = "requested"
            self._set(db, learner, scope, "requested", "pending-guardian")
        return out

    def grant(self, db: Session, learner: Learner, scope: str, granted_by: str, token: Optional[str] = None) -> dict[str, Any]:
        if safeguarding.is_minor(learner):
            try:
                data = _guardian_serializer().loads(token or "", max_age=7 * 86400)
            except BadSignature as exc:
                raise PermissionError("a valid guardian link is required") from exc
            if data.get("learner") != learner.id or data.get("scope") != scope:
                raise PermissionError("guardian link does not match")
        self._set(db, learner, scope, "granted", granted_by)
        return {"scope": scope, "status": "granted", "granted_by": granted_by}


class MockConsent(_ConsentBase):
    """Demo flow: a clearly-labelled 'approve as guardian' button grants without a real guardian."""
    name = "mock"
    is_mock = True

    def grant(self, db: Session, learner: Learner, scope: str, granted_by: str, token: Optional[str] = None) -> dict[str, Any]:
        self._set(db, learner, scope, "granted", f"{granted_by} (demo)")
        return {"scope": scope, "status": "granted", "granted_by": f"{granted_by} (demo)", "mock": True}


# ===================================================================================================
# cohort
# ===================================================================================================

MOCK_COHORT_ID = "mock_cohort_bca_2"
MOCK_COHORT_NAME = "BCA 2nd year — Databases (demo class)"


class MockCohort:
    name = "mock"
    is_mock = True

    def summary(self, db: Session, cohort_id: str) -> dict[str, Any]:
        return cohort_engine.aggregate(cohort_engine.synthetic_cohort(), MOCK_COHORT_ID, MOCK_COHORT_NAME, True)


OPEN_COHORT_ID = "saarthi-learners"
OPEN_COHORT_NAME = "SAARTHI learners who chose to be included"
MIN_CLASS_SIZE = 5     # below this, nothing about the group is shown: a handful of people could be recognised from their numbers


class DbCohort:
    name = "db"
    is_mock = False

    def summary(self, db: Session, cohort_id: str) -> dict[str, Any]:
        cid = cohort_id
        recs = cohort_engine.records_from_db(db, cid)
        name = OPEN_COHORT_NAME if cid == OPEN_COHORT_ID else cid
        members = {m.learner_id: m for m in db.scalars(select(CohortMember).where(CohortMember.cohort_id == cid))}
        real = {ref for ref, m in members.items() if not m.is_mock}
        only_fixture = bool(members) and not real          # the seeded test class, never a real group
        if len(recs) < MIN_CLASS_SIZE and not only_fixture:
            return {"cohort_id": cid, "name": name, "n_learners": len(recs), "is_mock": False, "hidden": True, "min_learners": MIN_CLASS_SIZE,
                    "concepts": [], "top_misconceptions": [], "needs_attention": [],
                    "privacy_note": f"Nothing is shown until at least {MIN_CLASS_SIZE} learners have joined, so no one can be picked out from the numbers."}
        for r in recs:      # real learners are never shown by name: a stable pseudonym instead
            if r["ref"] in real:
                r["display_name"] = "Learner " + str(100 + int(hashlib.sha1(r["ref"].encode()).hexdigest()[:6], 16) % 900)
        out = cohort_engine.aggregate(recs, cid, name, False)
        out["hidden"] = False
        return out


def seed_cohort(db: Session, cohort_id: str = MOCK_COHORT_ID) -> int:
    """Insert the synthetic class as real learner rows + concept states (for the DB-provider contract test)."""
    from ..content import get_content
    from ..models import ConceptState, MisconceptionInstance
    n = 0
    c = get_content()
    for rec in cohort_engine.synthetic_cohort():
        if db.get(Learner, rec["ref"]) is None:
            db.add(Learner(id=rec["ref"], name=rec["display_name"], age=20, is_mock=True))
            db.flush()
            n += 1
        for cid, p in rec["p"].items():
            db.add(ConceptState(learner_id=rec["ref"], concept_id=cid, p_known=p, n_evidence=rec["n_evidence"][cid],
                                n_success=1, source_types=["question", "work_product"]))
        for mid in rec["misconceptions"]:
            db.add(MisconceptionInstance(learner_id=rec["ref"], concept_id=c.misconceptions[mid]["concept_id"],
                                         misconception_id=mid, status="confirmed", channel="work_product"))
        if db.get(CohortMember, (cohort_id, rec["ref"])) is None:
            db.add(CohortMember(cohort_id=cohort_id, learner_id=rec["ref"], display_name=rec["display_name"], is_mock=True))
    db.flush()
    return n


# ===================================================================================================
# mentor-side replies
# ===================================================================================================

class MockMentorResponder:
    """Canned, clearly-labelled demo replies so the case flow can be shown without a human."""
    name = "mock"
    is_mock = True

    def reply(self, *, mentor: MentorRecord, case_category: str, concept_name: str, learner_message: str) -> Optional[str]:
        first = mentor.name.split()[0]
        m = learner_message.lower()
        if case_category == "career":
            if "interview" in m:
                return (f"Namaste! {first} here. For interviews, don't memorise answers — practise explaining one project in "
                        "three sentences: the problem, what you did, and what changed. Shall we rehearse that on Saturday?")
            return (f"Namaste! {first} here. Let's first write down where you want to be in two years, then pick the next "
                    "one skill that moves you toward it. What matters most to you right now - a first job or a better one?")
        if "join" in m or "left" in m:
            return (f"Hi, {first} here. Quick trick for joins: before running the query, say out loud which table must keep ALL its rows. "
                    "If it's the left table, that's a LEFT JOIN - and any filter on the right table belongs in ON, not WHERE. Try that on your last query.")
        if "null" in m:
            return (f"Hi, {first} here. Remember NULL means 'unknown'. Anything compared with = or <> against unknown is unknown, "
                    "so use IS NULL / IS NOT NULL. Can you rewrite your filter that way?")
        return (f"Hi, {first} here. I read your case report on {concept_name}. Let's take one failing query together - paste it here and "
                "tell me what you expected to see versus what you got.")


class NoResponder:
    """Real mode: humans reply; nothing is auto-generated."""
    name = "none"
    is_mock = False

    def reply(self, *, mentor: MentorRecord, case_category: str, concept_name: str, learner_message: str) -> Optional[str]:
        return None


# ===================================================================================================
# mail (guardian consent only)
# ===================================================================================================

class MockMailer:
    """Keeps messages in memory (dev outbox) and logs them. Nothing leaves the machine."""
    name = "mock"
    is_mock = True
    outbox: list[dict[str, str]] = []

    def send(self, to: str, subject: str, text: str) -> None:
        MockMailer.outbox.append({"to": to, "subject": subject, "text": text})
        del MockMailer.outbox[:-50]


class SmtpMailer:
    """Real delivery over SMTP with STARTTLS (settings SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / MAIL_FROM)."""
    name = "smtp"
    is_mock = False

    def __init__(self) -> None:
        if not (settings.smtp_host and settings.mail_from):
            raise RuntimeError("SAARTHI_MAIL=smtp but SMTP_HOST and MAIL_FROM are not both set")

    def send(self, to: str, subject: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, subject
        msg.set_content(text)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)
