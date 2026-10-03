"""SAARTHI API entry point.   Run:  uvicorn app.main:app --reload --port 8000   (from the backend folder)"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import adapters, db
from .config import BACKEND_DIR, settings
from .content import get_content
from .routes import core
from .routes import guardian
from .routes import learn
from .routes import mentor
from .routes import mentor_apply
from .routes import mentor_console
from .routes import notifications
from .routes import profile_complete
from .routes import voice
from .routes import case_notes
from .routes import chat
from .routes import case_sync
from .routes import interview_ext
from .routes import video_interview
from .routes import class_view
from .routes import i18n as i18n_routes
from .routes import resources as resources_routes
from .routes import streak
from .routes import progress
from .routes import feedback
from .routes import phases
from .routes import intake
from .routes import profile
from .routes import map as map_route
from .routes import vakh

log = logging.getLogger("saarthi")


def _mount_frontend(app: FastAPI) -> None:
    """If `frontend/dist` exists (after `npm run build`), serve it so the whole app runs from one port."""
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    dist = BACKEND_DIR.parent / "frontend" / "dist"
    if not (dist / "index.html").exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(404, "Not found")
        f = (dist / path).resolve()
        if path and f.is_file() and dist in f.parents:
            return FileResponse(f)
        return FileResponse(dist / "index.html")


def create_app() -> FastAPI:
    app = FastAPI(title="SAARTHI API", version="0.1.0",
                  description="Adaptive AI mentor: Learner Twin, evidence-based roadmap, explain-back, Chhatrachhaya mentors.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    get_content()          # fail at start-up if the curated content is inconsistent
    adapters.describe()    # fail at start-up if a "real" switch is misconfigured (no silent fallback)
    db.init_db()
    # one router per line: a new spec adds its own import above and its own line here
    for r in (
        core.router,
        guardian.router,
        learn.router,
        mentor.router,
        mentor_apply.router,
        mentor_console.router,
        notifications.router,
        profile_complete.router,
        voice.router,
        case_notes.router,
        chat.router,
        case_sync.router,
        interview_ext.router,
        video_interview.router,
        class_view.router,
        i18n_routes.router,
        resources_routes.router,
        streak.router,
        progress.router,
        feedback.router,
        phases.router,
        intake.router,
        profile.router,
        map_route.router,
        vakh.router,
    ):
        app.include_router(r)
    _mount_frontend(app)
    mocks = adapters.describe()["mock_areas"]
    log.info("SAARTHI started | env=%s | mock areas: %s | llm=%s", settings.env, mocks or "none", settings.llm_mode)
    return app


app = create_app()
