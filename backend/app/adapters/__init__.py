"""Adapter factory. One switch per area (SAARTHI_AUTH / MENTORS / CONSENT / COHORT).

There is NO silent fallback: a "real" switch with missing configuration raises at start-up instead of
quietly serving mock data.
"""

from __future__ import annotations

from functools import lru_cache

from ..config import settings
from .base import (AuthProvider, CohortProvider, ConsentProvider, MailSender, MentorDirectory, MentorRecord, MentorResponder,
                   Principal)
from .impl import (AuthError, AuthUnavailable, DbCohort, DbConsent, DbMentorDirectory, MockAuth, MockCohort, MockConsent,
                   MockMailer, MockMentorDirectory, MockMentorResponder, NoResponder, SmtpMailer, SupabaseAuth)


def _choose(area: str, value: str, options: dict):
    if value not in options:
        raise RuntimeError(f"SAARTHI_{area}={value!r} is not valid; choose one of {sorted(options)}")
    return options[value]()


@lru_cache(maxsize=1)
def auth() -> AuthProvider:
    return _choose("AUTH", settings.auth_mode, {"mock": MockAuth, "supabase": SupabaseAuth})


@lru_cache(maxsize=1)
def mentors() -> MentorDirectory:
    return _choose("MENTORS", settings.mentors_mode, {"mock": MockMentorDirectory, "db": DbMentorDirectory})


@lru_cache(maxsize=1)
def consent() -> ConsentProvider:
    return _choose("CONSENT", settings.consent_mode, {"mock": MockConsent, "db": DbConsent})


@lru_cache(maxsize=1)
def cohort() -> CohortProvider:
    return _choose("COHORT", settings.cohort_mode, {"mock": MockCohort, "db": DbCohort})


@lru_cache(maxsize=1)
def mailer() -> MailSender:
    return _choose("MAIL", settings.mail_mode, {"mock": MockMailer, "smtp": SmtpMailer})


@lru_cache(maxsize=1)
def responder() -> MentorResponder:
    # replies are only auto-generated while mentors are mocked
    return MockMentorResponder() if settings.mentors_mode == "mock" else NoResponder()


def reset() -> None:
    for f in (auth, mentors, consent, cohort, mailer, responder):
        f.cache_clear()


def describe() -> dict:
    return {"auth": auth().name, "mentors": mentors().name, "consent": consent().name, "cohort": cohort().name, "mail": mailer().name,
            "mock_areas": [n for n, p in (("auth", auth()), ("mentors", mentors()), ("consent", consent()), ("cohort", cohort())) if p.is_mock]}
