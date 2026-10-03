"""Settings. Everything environment-specific lives here; nothing else reads os.environ.

The mock-vs-real switches (AUTH / MENTORS / CONSENT / COHORT) are deliberately separate so one area
can go live at a time. There is no silent fallback: if a switch says "real" and the real source is
not configured, the adapter factory raises instead of quietly using mock data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CONTENT_DIR = Path(__file__).resolve().parent / "content"
SEED_DIR = Path(__file__).resolve().parent / "seed"


def _alias(*names: str):
    return Field(default=None, validation_alias=AliasChoices(*names))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore", populate_by_name=True)

    env: str = Field(default="dev", validation_alias=AliasChoices("SAARTHI_ENV"))
    secret: str = Field(default="dev-secret-change-me-dev-secret-change-me",
                        validation_alias=AliasChoices("SAARTHI_SECRET"))
    database_url: str = Field(default="", validation_alias=AliasChoices("DATABASE_URL"))

    # language model
    gemini_api_key: Optional[str] = _alias("GEMINI_API_KEY")
    model: str = Field(default="gemini-3.5-flash-lite", validation_alias=AliasChoices("SAARTHI_MODEL"))
    model_fallbacks: str = Field(default="", validation_alias=AliasChoices("SAARTHI_MODEL_FALLBACKS"))
    llm_mode: str = Field(default="gemini", validation_alias=AliasChoices("SAARTHI_LLM_MODE"))

    # elevenlabs
    elevenlabs_api_key: Optional[str] = _alias("ELEVENLABS_API_KEY")
    elevenlabs_agent_id: Optional[str] = _alias("ELEVENLABS_AGENT_ID")
    elevenlabs_agent_public: bool = Field(default=False, validation_alias=AliasChoices("ELEVENLABS_AGENT_PUBLIC"))
    elevenlabs_voice_id: Optional[str] = _alias("ELEVENLABS_VOICE_ID")
    elevenlabs_tts_model: str = Field(default="eleven_multilingual_v2",
                                      validation_alias=AliasChoices("ELEVENLABS_TTS_MODEL"))
    elevenlabs_stt_model: str = Field(default="scribe_v1", validation_alias=AliasChoices("ELEVENLABS_STT_MODEL"))

    # mock-vs-real switches
    auth_mode: str = Field(default="mock", validation_alias=AliasChoices("SAARTHI_AUTH"))
    mentors_mode: str = Field(default="mock", validation_alias=AliasChoices("SAARTHI_MENTORS"))
    consent_mode: str = Field(default="mock", validation_alias=AliasChoices("SAARTHI_CONSENT"))
    cohort_mode: str = Field(default="db", validation_alias=AliasChoices("SAARTHI_COHORT"))      # "mock" (a made-up class) exists only for tests and explicit development
    mail_mode: str = Field(default="mock", validation_alias=AliasChoices("SAARTHI_MAIL"))
    smtp_host: Optional[str] = _alias("SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias=AliasChoices("SMTP_PORT"))
    smtp_user: Optional[str] = _alias("SMTP_USER")
    smtp_password: Optional[str] = _alias("SMTP_PASSWORD")
    mail_from: Optional[str] = _alias("MAIL_FROM")
    # used to build the link in the guardian e-mail; the address learners/guardians open in the browser
    public_base_url: str = Field(default="http://localhost:5173", validation_alias=AliasChoices("PUBLIC_BASE_URL"))
    supabase_url: Optional[str] = _alias("SUPABASE_URL")
    supabase_jwt_secret: Optional[str] = _alias("SUPABASE_JWT_SECRET")

    # comma-separated sign-in user ids (Supabase > Authentication > Users > "User UID") allowed to use /api/admin/*
    admins: str = Field(default="", validation_alias=AliasChoices("SAARTHI_ADMINS"))
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173",
                              validation_alias=AliasChoices("CORS_ORIGINS"))

    # Tavily web search: real learning resources (articles, docs, videos) shown for each concept. Empty means the feature is off.
    tavily_api_key: str = Field(default="", validation_alias=AliasChoices("TAVILY_API_KEY"))

    # Vakh challenge & submission layer. Nothing is assumed: with no address and no secret the Vakh features stay off.
    #   VAKH_BASE_URL: the real address of your Vakh site, for example https://<your-vakh-host>
    #   VAKH_WEBHOOK_SECRET: a long random string shared with Vakh; reviews are accepted only with a valid HMAC signature made with it
    vakh_base_url: str = Field(default="", validation_alias=AliasChoices("VAKH_BASE_URL"))
    vakh_webhook_secret: str = Field(default="", validation_alias=AliasChoices("VAKH_WEBHOOK_SECRET"))
    vakh_enabled: bool = Field(default=True, validation_alias=AliasChoices("VAKH_ENABLED"))     # master switch; false turns every Vakh endpoint off

    @property
    def is_prod(self) -> bool:
        return self.env.lower() == "prod"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(DATA_DIR / 'saarthi.db').as_posix()}"

    @property
    def llm_models(self) -> list[str]:
        extra = [m.strip() for m in self.model_fallbacks.split(",") if m.strip()]
        out: list[str] = []
        for m in [self.model, *extra]:
            if m not in out:
                out.append(m)
        return out

    @property
    def admin_ids(self) -> list[str]:
        return [a.strip() for a in self.admins.split(",") if a.strip()]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
