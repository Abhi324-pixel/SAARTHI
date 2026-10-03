"""Loads the mock fixtures into the database so a mock area can be switched to its real (DB) implementation.

    python scripts/seed.py            # mentors + demo cohort
    python scripts/seed.py --mentors  # only mentors

After seeding, set SAARTHI_MENTORS=db (and/or SAARTHI_COHORT=db) in backend/.env. The contract tests prove that the
mock and DB implementations return identical data, so the switch changes where data comes from and nothing else.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.adapters import impl  # noqa: E402


def main() -> None:
    only_mentors = "--mentors" in sys.argv
    db.init_db()
    with db.session_scope() as s:
        n = impl.seed_mentors(s)
        print(f"mentors inserted: {n}")
        if not only_mentors:
            k = impl.seed_cohort(s)
            print(f"cohort learners inserted: {k}")
    print("done. Now set SAARTHI_MENTORS=db / SAARTHI_COHORT=db in backend/.env, then restart the API.")


if __name__ == "__main__":
    main()
