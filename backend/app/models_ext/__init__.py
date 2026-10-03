"""Tables added by individual feature specs (docs/features): one module per spec, e.g. `T04.py`, `C03.py`.

Every module in this package is imported automatically when the database is initialised (see `db.init_db`), so a new
spec only has to add its own file here — nobody edits `models.py` or an import list, which keeps parallel work conflict-free.

A module looks like:

    from sqlalchemy import ForeignKey, String
    from sqlalchemy.orm import Mapped, mapped_column
    from .. import privacy
    from ..models import Base, new_id, now

    class CaseNote(Base):
        __tablename__ = "case_notes"
        ...

    privacy.register_export("case_notes", lambda db, learner: [...])      # what GET /api/me/export should include
    privacy.register_delete(lambda db, learner: ...)                     # only for rows NOT removed by FK cascade

Rules: portable column types only; new tables only (never new columns on existing tables — `create_all` does not alter
them); learner-owned tables use `ForeignKey("learners.id", ondelete="CASCADE")`. See docs/features/00-PLAYBOOK.md §5a.
"""

from __future__ import annotations

import importlib
import pkgutil

for _mod in sorted(m.name for m in pkgutil.iter_modules(__path__)):
    importlib.import_module(f"{__name__}.{_mod}")
