"""Registry that keeps data export and account deletion complete as features add tables.

`GET /api/me/export` and `DELETE /api/me` (routes/core.py) call `export_all` / `delete_all`. A feature registers its own
hooks from its `models_ext/<spec>.py`, so nobody has to edit `routes/core.py` (a hot-spot file) and a new learner table
cannot be forgotten silently. Tables with `ForeignKey("learners.id", ondelete="CASCADE")` are deleted by the database
cascade; register a delete hook only for rows that are NOT covered by that (for example rows keyed by a plain user id).
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from .models import Learner

Exporter = Callable[[Session, Learner], Any]
Deleter = Callable[[Session, Learner], None]

_exporters: dict[str, Exporter] = {}
_deleters: list[Deleter] = []


def register_export(key: str, fn: Exporter) -> None:
    """`fn(db, learner)` must return JSON-serialisable data about this learner only. `key` appears under `more` in the export."""
    if not key or key in _exporters:
        raise ValueError(f"export key {key!r} is empty or already registered")
    _exporters[key] = fn


def register_delete(fn: Deleter) -> None:
    _deleters.append(fn)


def export_all(db: Session, learner: Learner) -> dict[str, Any]:
    return {key: fn(db, learner) for key, fn in sorted(_exporters.items())}


def delete_all(db: Session, learner: Learner) -> None:
    for fn in _deleters:
        fn(db, learner)
