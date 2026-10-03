"""Fetches web resources (Tavily) for every concept in English and Hindi and stores them in the cache, so the first learner never waits.

    python scripts/prewarm_resources.py            # only concepts with no fresh cache
    python scripts/prewarm_resources.py --refresh  # search everything again

Uses one Tavily credit per search (about 2 x the number of concepts). Needs TAVILY_API_KEY in backend/.env.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.content import get_content  # noqa: E402
from app.engines import resources  # noqa: E402


def main() -> None:
    if not resources.configured():
        sys.exit("TAVILY_API_KEY is not set in backend/.env")
    refresh = "--refresh" in sys.argv
    db.init_db()
    ok = empty = failed = skipped = 0
    for cid in get_content().concepts:
        for lang in ("english", "hindi"):
            with db.session_scope() as s:
                if not refresh and not resources.needs_search(s, cid, lang):
                    skipped += 1
                    continue
                r = resources.for_concept(s, cid, lang, refresh=refresh)
            if r["status"] == "ok" and r["items"]:
                ok += 1
            elif r["status"] == "ok":
                empty += 1
            else:
                failed += 1
            print(f"{cid:28s} {lang:8s} {r['status']:12s} {len(r['items'])} resources")
            time.sleep(0.3)
    print(f"done: {ok} with resources, {empty} empty, {failed} failed, {skipped} already cached")


if __name__ == "__main__":
    main()
