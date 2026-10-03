"""The ONE place that decides whether a learner is treated as a minor (under 18).

Age is self-declared and cannot be verified by SAARTHI. The rule is therefore: until the learner has told us their age
(`settings["age_confirmed"]` is False, which happens for sign-ups through Google/OAuth that carry no age), they are treated as a
minor. Learners created before this flag existed, mock logins and e-mail sign-ups all supplied an age, so a missing flag means
"confirmed". Never compare `learner.age` with 18 anywhere else (tests/test_age_gate.py fails if someone does).
"""

from __future__ import annotations

from fastapi import HTTPException

from ..models import Learner

MIN_AGE, MAX_AGE = 10, 100
UNCONFIRMED_PLACEHOLDER_AGE = 17     # fail-safe value stored until the learner tells us; the flag is what really matters


def age_confirmed(learner: Learner) -> bool:
    return bool((learner.settings or {}).get("age_confirmed", True))


def is_minor(learner: Learner) -> bool:
    return (not age_confirmed(learner)) or learner.age < 18


def require_age(learner: Learner) -> None:
    """For features that expose a learner to another person: refuse until the age is known (the learning features stay open)."""
    if not age_confirmed(learner):
        raise HTTPException(409, {"code": "AGE_REQUIRED", "message": "Please tell us your age first (Profile > complete your profile)."})
