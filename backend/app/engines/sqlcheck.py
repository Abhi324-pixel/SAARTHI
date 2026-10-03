"""SQL work-product checker — the most reliable evidence channel (checked by execution, no model judgement).

Safety: the learner's text runs inside a throw-away in-memory SQLite database, with an authorizer that
only allows SELECT (no ATTACH, PRAGMA, writes or extension loading), a row cap and a time limit.

Diagnosis is layered:
  1. result equals the reference result                      -> correct
  2. error text matches a known-misconception variant        -> that misconception (e.g. "misuse of aggregate")
  3. result equals a precomputed WRONG-VARIANT result         -> that misconception
  4. static text rules (`= NULL`, `<> NULL`)                  -> that misconception
  5. otherwise a plain-language structural hint (missing rows, extra rows, duplicates, column count)
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

from ..config import CONTENT_DIR

MAX_ROWS = 200
MAX_SECONDS = 2.0
MAX_QUERY_CHARS = 4000

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}


@lru_cache(maxsize=1)
def _dataset_sql() -> str:
    return (CONTENT_DIR / "shop.sql").read_text(encoding="utf-8")


def _fresh_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(_dataset_sql())
    return conn


def _authorizer(action: int, arg1: Any, arg2: Any, dbname: Any, source: Any) -> int:
    if action in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


@dataclass
class QueryResult:
    ok: bool
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    truncated: bool = False
    error: Optional[str] = None


def run_query(query: str) -> QueryResult:
    """Run a learner query safely. Never raises."""
    q = (query or "").strip().rstrip(";").strip()
    if not q:
        return QueryResult(ok=False, error="Write a query first.")
    if len(q) > MAX_QUERY_CHARS:
        return QueryResult(ok=False, error="Query is too long.")
    if ";" in q:
        return QueryResult(ok=False, error="Run one statement at a time (remove the extra ';').")
    head = q.lstrip("( \n\t").split(None, 1)[0].lower() if q.lstrip("( \n\t") else ""
    if head not in ("select", "with"):
        return QueryResult(ok=False, error="Only SELECT queries can be run in this practice area.")
    conn = _fresh_connection()
    try:
        conn.set_authorizer(_authorizer)
        try:
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)  # blocks memory bombs such as hex(zeroblob(1e9))
        except (AttributeError, sqlite3.Error):  # pragma: no cover - Python < 3.11
            pass
        deadline = time.monotonic() + MAX_SECONDS
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
        cur = conn.execute(q)
        cols = [d[0] for d in (cur.description or [])]
        fetched = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(fetched) > MAX_ROWS
        rows = [list(r) for r in fetched[:MAX_ROWS]]
        return QueryResult(ok=True, columns=cols, rows=rows, truncated=truncated)
    except sqlite3.Error as e:
        msg = str(e)
        if "interrupted" in msg.lower():
            msg = "The query took too long and was stopped."
        elif "not authorized" in msg.lower():
            msg = "That statement is not allowed here (SELECT only)."
        return QueryResult(ok=False, error=msg)
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------------
# comparing results
# ---------------------------------------------------------------------------------------------------

def _norm_cell(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, str):
        return v
    return v


def _norm_rows(rows: list[list[Any]]) -> list[tuple]:
    return [tuple(_norm_cell(c) for c in r) for r in rows]


def _key(t: tuple) -> tuple:
    return tuple((0, "") if c is None else (1, c) if not isinstance(c, str) else (2, c) for c in t)


def result_signature(rows: list[list[Any]], ordered: bool) -> tuple:
    n = _norm_rows(rows)
    return tuple(n) if ordered else tuple(sorted(n, key=_key))


def same_result(a: QueryResult, b: QueryResult, ordered: bool) -> bool:
    if not (a.ok and b.ok):
        return False
    if len(a.columns) != len(b.columns):
        return False
    return result_signature(a.rows, ordered) == result_signature(b.rows, ordered)


_STATIC_RULES = [
    (re.compile(r"(?<![<>!=])(=|<>|!=)\s*null\b", re.I), "null_comparison"),
]


@dataclass
class Verdict:
    correct: bool
    misconception_id: Optional[str] = None
    hints: list[str] = field(default_factory=list)
    result: Optional[QueryResult] = None
    matched_by: Optional[str] = None  # error | variant | static | structure


def _structure_hints(learner: QueryResult, ref: QueryResult, ordered: bool) -> list[str]:
    hints: list[str] = []
    if len(learner.columns) != len(ref.columns):
        hints.append(f"Your query returns {len(learner.columns)} column(s); the task expects {len(ref.columns)}.")
        return hints
    ln, rn = _norm_rows(learner.rows), _norm_rows(ref.rows)
    from collections import Counter
    lc, rc = Counter(ln), Counter(rn)
    missing = sum((rc - lc).values())
    extra = sum((lc - rc).values())
    if len(ln) < len(rn):
        hints.append(f"Your result has {len(ln)} row(s) but {len(rn)} are expected — some rows are missing.")
    elif len(ln) > len(rn):
        hints.append(f"Your result has {len(ln)} row(s) but {len(rn)} are expected — there are extra or repeated rows.")
    elif missing or extra:
        hints.append("The number of rows is right, but some values differ from what is expected.")
    elif ordered and ln != rn:
        hints.append("The rows are right but not in the expected order.")
    if len(set(ln)) < len(ln) and len(set(rn)) == len(rn):
        hints.append("Your result contains duplicate rows — a join may be repeating rows.")
    return hints or ["The result does not match the expected output."]


def evaluate(task: dict, query: str, variants: Optional[list[dict]] = None) -> Verdict:
    """Evaluate a learner query against a task definition (from sql_tasks.json)."""
    ordered = bool(task.get("order_sensitive"))
    learner = run_query(query)
    ref = _reference_result(task["id"], task["reference_query"])

    if not learner.ok:
        for v in task.get("variants", []):
            needle = v.get("error_contains")
            if needle and learner.error and needle.lower() in learner.error.lower():
                return Verdict(False, v["misconception_id"], [v.get("note", learner.error)], learner, "error")
        return Verdict(False, None, [learner.error or "The query could not run."], learner, "error")

    if same_result(learner, ref, ordered):
        return Verdict(True, None, [], learner, None)

    # static text rules first — they explain *why* an empty/odd result happened
    for pat, mid in _STATIC_RULES:
        if pat.search(query):
            for v in task.get("variants", []):
                if v["misconception_id"] == mid:
                    return Verdict(False, mid, [v.get("note", "")], learner, "static")
            if mid in task.get("static_ok", []):
                return Verdict(False, mid, [], learner, "static")

    for v in task.get("variants", []):
        if "query" not in v:
            continue
        vr = _variant_result(task["id"], v["query"])
        if vr.ok and same_result(learner, vr, ordered):
            return Verdict(False, v["misconception_id"], [v.get("note", "")], learner, "variant")

    return Verdict(False, None, _structure_hints(learner, ref, ordered), learner, "structure")


@lru_cache(maxsize=256)
def _reference_cached(task_id: str, query: str) -> QueryResult:
    return run_query(query)


def _reference_result(task_id: str, query: str) -> QueryResult:
    return _reference_cached(task_id, query)


@lru_cache(maxsize=512)
def _variant_cached(task_id: str, query: str) -> QueryResult:
    return run_query(query)


def _variant_result(task_id: str, query: str) -> QueryResult:
    return _variant_cached(task_id, query)
