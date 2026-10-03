"""Ports (interfaces) for everything that is mocked today and real later.

Engines and routes depend ONLY on these protocols. Each has a mock implementation and a real one, and the
SAME contract tests (tests/test_adapter_contracts.py) run against both - that is what makes the later swap safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from sqlalchemy.orm import Session

from ..models import Learner


@dataclass
class Principal:
    learner_id: str
    name: str = ""
    email: Optional[str] = None
    is_mock: bool = False


@dataclass
class MentorRecord:
    id: str
    name: str
    tier: str
    headline: str = ""
    bio: str = ""
    expertise: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    availability: list[str] = field(default_factory=list)
    verification_status: str = "unverified"
    active_case_cap: int = 3
    is_mock: bool = False

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "tier": self.tier, "headline": self.headline, "bio": self.bio,
                "expertise": self.expertise, "languages": self.languages, "availability": self.availability,
                "verification_status": self.verification_status, "is_mock": self.is_mock}


class AuthProvider(Protocol):
    name: str
    is_mock: bool

    def login(self, db: Session, *, name: str, age: int, language: str, email: Optional[str]) -> dict[str, Any]: ...
    def authenticate(self, db: Session, token: str) -> Principal: ...
    def verify_token(self, token: str) -> Principal: ...   # who is this? Never creates a learner (mentors and admins use it)


class MentorDirectory(Protocol):
    name: str
    is_mock: bool

    def list(self, db: Session, tier: Optional[str] = None) -> list[MentorRecord]: ...
    def get(self, db: Session, mentor_id: str) -> Optional[MentorRecord]: ...


class ConsentProvider(Protocol):
    name: str
    is_mock: bool

    def status(self, db: Session, learner: Learner, scope: str) -> str: ...
    def request(self, db: Session, learner: Learner, scope: str, guardian_email: Optional[str] = None,
                lang: str = "english") -> dict[str, Any]: ...
    def grant(self, db: Session, learner: Learner, scope: str, granted_by: str, token: Optional[str] = None) -> dict[str, Any]: ...
    def revoke(self, db: Session, learner: Learner, scope: str) -> dict[str, Any]: ...


class MailSender(Protocol):
    """Outgoing e-mail (used only for guardian consent). Mock: keeps messages in memory. Real: SMTP."""
    name: str
    is_mock: bool

    def send(self, to: str, subject: str, text: str) -> None: ...


class CohortProvider(Protocol):
    name: str
    is_mock: bool

    def summary(self, db: Session, cohort_id: str) -> dict[str, Any]: ...


class MentorResponder(Protocol):
    """Produces mentor-side replies. Mock: canned guidance. Real: None (a human replies)."""
    name: str
    is_mock: bool

    def reply(self, *, mentor: MentorRecord, case_category: str, concept_name: str, learner_message: str) -> Optional[str]: ...
