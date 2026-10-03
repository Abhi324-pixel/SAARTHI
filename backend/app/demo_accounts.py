"""The fixed fake accounts used by scripts/seed_demo.py and the dev-only "Demo accounts" menu on the login page."""

LEARNERS = [
    {"id": "mock_demo_riya", "name": "Riya (demo, age 15)", "age": 15, "language": "hinglish", "note": "under 18: guardian consent"},
    {"id": "mock_demo_arjun", "name": "Arjun (demo, age 22)", "age": 22, "language": "english", "note": "adult"},
]
DEMO_MENTOR_IDS = ["mock_sm_ananya", "mock_sm_vikram"]


def ensure_mentor_learner(db, mentor) -> None:
    """A real mentor is also a signed-up account with a learner row; the app calls /me on every page, so a demo mentor needs one too."""
    from .models import Learner
    if db.get(Learner, mentor.id) is None:
        db.add(Learner(id=mentor.id, name=mentor.name, age=35, is_mock=True, onboarded=True))
        db.flush()
