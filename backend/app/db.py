"""Database access. One SQLAlchemy engine; the connection string decides SQLite (local) vs Postgres (Supabase).

The same models and the same migrations-by-metadata work on both, which is what makes the later
Supabase swap a one-line configuration change. Tests call `configure("sqlite://")` for a fresh in-memory DB.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

engine: Engine
SessionLocal: sessionmaker[Session]


def configure(url: str | None = None) -> Engine:
    """(Re)build the engine. `sqlite://` gives an isolated in-memory database."""
    global engine, SessionLocal
    url = url or settings.resolved_database_url
    for prefix in ("postgres://", "postgresql://"):  # Supabase shows these; SQLAlchemy needs the psycopg driver name
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
    kwargs: dict = {}
    if not url.startswith("sqlite"):
        kwargs["pool_pre_ping"] = True  # hosted Postgres drops idle connections
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, future=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    return engine


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)
    from . import models_ext  # noqa: F401  (tables added by feature specs; auto-imported)
    models.Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


configure()
