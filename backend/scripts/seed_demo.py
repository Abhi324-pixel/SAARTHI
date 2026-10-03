"""Seeds a local demo: the mock mentors, one under-18 learner, one adult learner, and prints sign-in tokens for them.

    set SAARTHI_AUTH=mock, SAARTHI_MENTORS=db, SAARTHI_CONSENT=db, SAARTHI_MAIL=mock, DATABASE_URL= (local SQLite), then
    python scripts/seed_demo.py

Safe to run twice (it reuses the accounts). Refuses to run against a real sign-in, a production setting or a hosted database:
these accounts are fakes and must never exist next to real learners.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt  # noqa: E402

from app import adapters, db  # noqa: E402
from app.adapters import impl  # noqa: E402
from app.config import settings  # noqa: E402
from app.demo_accounts import DEMO_MENTOR_IDS, LEARNERS, ensure_mentor_learner  # noqa: E402
from app.engines import mastery, planner  # noqa: E402
from app.models import Learner, Mentor  # noqa: E402
from app.routes.core import DEMO_HISTORY  # noqa: E402

def token(sub: str, name: str) -> str:
    return jwt.encode({"sub": sub, "name": name, "iat": int(time.time()), "mock": True}, settings.secret, algorithm="HS256")


def main() -> None:
    url = settings.resolved_database_url
    if settings.is_prod or not url.startswith("sqlite") or settings.auth_mode != "mock":
        sys.exit("Refusing: demo accounts are only for a local setup (SAARTHI_ENV=dev, SQLite, SAARTHI_AUTH=mock).")
    if settings.mentors_mode != "db":
        sys.exit("Set SAARTHI_MENTORS=db first (the console and cases need the mentors table).")
    db.init_db()
    role = json.loads((Path(__file__).resolve().parent.parent / "app" / "content" / "roles.json").read_text(encoding="utf-8"))
    roles = role["roles"] if isinstance(role, dict) and "roles" in role else role
    role_id = roles[0]["id"]
    out = []
    with db.session_scope() as s:
        print(f"mentors inserted: {impl.seed_mentors(s)}")
        for spec in LEARNERS:
            lr = s.get(Learner, spec["id"])
            fresh = lr is None
            if fresh:
                lr = Learner(id=spec["id"], name=spec["name"], age=spec["age"], language_pref=spec["language"], is_mock=True,
                             role_id=role_id, onboarded=True, weekly_hours=6.0, horizon_weeks=12)
                s.add(lr)
                s.flush()
                for cid, src, score, n in DEMO_HISTORY:
                    for i in range(n):
                        mastery.apply_evidence(s, lr, cid, src, score=score, item_id=f"demo_{cid}_{i}", grader="simulated",
                                               stated_confidence=3, detail={"simulated": True})
                planner.refresh(s, lr, "your earlier practice")
            out.append((lr.name, token(lr.id, lr.name)))
        for m in s.query(Mentor).filter(Mentor.id.in_(DEMO_MENTOR_IDS)):
            ensure_mentor_learner(s, m)
            out.append((f"MENTOR {m.name} ({m.id})", token(m.id, m.name)))
    print("\nSign in as any of these: open the app, press F12, Console, paste the line, then reload the page.\n")
    for name, tok in out:
        print(f"# {name}\nlocalStorage.setItem('saarthi.token','{tok}')\n")
    print("Demo walk-through: docs/DEMO_ACCOUNTS.md")


if __name__ == "__main__":
    main()
