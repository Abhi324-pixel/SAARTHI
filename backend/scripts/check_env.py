"""Checks your keys and configuration with tiny real calls.   Run:  python scripts/check_env.py   (from the backend folder)

Prints a green/red line per check and tells you exactly what to fix. Uses almost no credits.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app import adapters  # noqa: E402
from app.config import BACKEND_DIR, settings  # noqa: E402
from app.llm import gateway  # noqa: E402
from app.voice import elevenlabs  # noqa: E402

OK, BAD, WARN = "\033[32m[ OK ]\033[0m", "\033[31m[FAIL]\033[0m", "\033[33m[WARN]\033[0m"
failures = 0


def line(flag: str, msg: str, fix: str = "") -> None:
    global failures
    if flag == BAD:
        failures += 1
    print(f"{flag} {msg}" + (f"\n         -> {fix}" if fix else ""))


print(f"SAARTHI environment check  (env file: {BACKEND_DIR / '.env'}, exists={ (BACKEND_DIR / '.env').exists() })\n")

# ---- Gemini ---------------------------------------------------------------------------------------------------
if settings.llm_mode == "fake":
    line(WARN, "SAARTHI_LLM_MODE=fake: the offline TEST grader is on. Never use this in the demo.", "Set SAARTHI_LLM_MODE=gemini")
elif not settings.gemini_api_key:
    line(BAD, "GEMINI_API_KEY is missing", "Add GEMINI_API_KEY=... to backend/.env")
else:
    try:
        out = gateway.generate_json("check", "Reply with JSON only.", 'Return {"ok": true}', {"type": "object", "properties": {"ok": {"type": "boolean"}}},
                                    max_tokens=50)
        line(OK, f"Gemini reachable with model '{out.get('_model')}'")
        if out.get("_model") != settings.model:
            line(WARN, f"Primary model '{settings.model}' failed; fell back to '{out.get('_model')}'",
                 "Check the model name in SAARTHI_MODEL (and your key's access).")
    except Exception as e:  # noqa: BLE001
        line(BAD, f"Gemini call failed: {str(e)[:200]}", f"Check GEMINI_API_KEY and that model '{settings.model}' exists for your key")

# ---- ElevenLabs --------------------------------------------------------------------------------------------------
st = elevenlabs.status()
if not st["api_key"]:
    line(BAD, "ELEVENLABS_API_KEY is missing", "Add ELEVENLABS_API_KEY=... to backend/.env (see docs/ELEVENLABS_SETUP.md)")
else:
    try:
        r = httpx.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": settings.elevenlabs_api_key}, timeout=15)
        if r.status_code == 200:
            sub = r.json().get("subscription", {})
            line(OK, f"ElevenLabs key valid (tier: {sub.get('tier', '?')}, characters left: "
                     f"{sub.get('character_limit', 0) - sub.get('character_count', 0)})")
        elif r.status_code == 401:
            # a key restricted to specific endpoints cannot read /v1/user; the real endpoints below decide pass/fail
            line(WARN, "Key cannot read account info (no 'User: read' permission) - only the credit readout is lost; testing the real endpoints instead")
        else:
            # a key restricted to some endpoints may not be allowed to read /user; test the real endpoints below instead
            line(WARN, f"/v1/user returned {r.status_code} (restricted key?) - testing the real endpoints instead")
    except Exception as e:  # noqa: BLE001
        line(BAD, f"Cannot reach ElevenLabs: {e}")

    if not st["agent_id"]:
        line(BAD, "ELEVENLABS_AGENT_ID is missing", "Create the agent (docs/ELEVENLABS_SETUP.md, step 1) and copy its Agent ID")
    else:
        try:
            conn = elevenlabs.agent_connection()
            line(OK, f"Agent reachable ({conn['mode']} connection)")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"Agent connection failed: {str(e)[:200]}",
                 "Check ELEVENLABS_AGENT_ID. If authentication is OFF on the agent, set ELEVENLABS_AGENT_PUBLIC=true")
    if not st["voice_id"]:
        line(BAD, "ELEVENLABS_VOICE_ID is missing (needed for read-aloud)", "Copy a voice id from the Voices page into backend/.env")
    else:
        try:
            audio = elevenlabs.text_to_speech("Namaste. SAARTHI is ready.", "english")
            line(OK, f"Text-to-speech works ({len(audio)} bytes of audio)")
            try:  # round trip: transcribe the audio we just generated
                heard = elevenlabs.speech_to_text(audio, "check.mp3", "audio/mpeg")
                line(OK, f"Speech-to-text works (heard: \"{heard['text'].strip()[:50]}\")")
            except Exception as e:  # noqa: BLE001
                line(BAD, f"Speech-to-text failed: {str(e)[:200]}", "Give the API key 'Speech to Text' permission (the mic button needs it)")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"Text-to-speech failed: {str(e)[:200]}", "Check ELEVENLABS_VOICE_ID and that the key may use Text to Speech")

# ---- database & switches ------------------------------------------------------------------------------------------------
from sqlalchemy import text  # noqa: E402
from app import db as _db  # noqa: E402

url = _db.engine.url
is_pg = url.get_backend_name().startswith("postgres")
try:
    with _db.engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    where = f"{url.host}:{url.port or 5432}/{url.database}" if is_pg else str(url.database)
    line(OK, f"Database connection works ({'Postgres/Supabase' if is_pg else 'local SQLite'}: {where})")
    if not is_pg:
        line(WARN, "Still on the local SQLite file", "Set DATABASE_URL to your Supabase connection string to use the real database")
except Exception as e:  # noqa: BLE001
    import re
    msg = str(e).splitlines()[0]
    msg = re.sub(r"'[^']*@", "'", msg)  # never echo anything that could be part of a password
    hint = "Check DATABASE_URL (user, password, host, port). In Supabase use the 'Session pooler' string if the direct host is IPv6-only"
    if "failed to resolve host" in msg or "could not translate host" in msg:
        hint = ("Two common causes: (1) the PASSWORD contains @ : / # ? and must be URL-encoded (@ -> %40, : -> %3A, / -> %2F, # -> %23, ? -> %3F); "
                "(2) Supabase's direct host db.<ref>.supabase.co is IPv6-only and your network has no IPv6 - use the 'Session pooler' string from "
                "Supabase > Connect instead (host aws-0-<region>.pooler.supabase.com, user postgres.<project-ref>).")
    line(BAD, f"Cannot connect to the database: {msg[:200]}", hint)

# ---- Supabase Auth: JWKS ---------------------------------------------------------------------------------------------
if settings.auth_mode == "supabase" or settings.supabase_url:
    if not settings.supabase_url:
        line(BAD, "SAARTHI_AUTH=supabase but SUPABASE_URL is missing", "Add SUPABASE_URL=https://<project-ref>.supabase.co to backend/.env")
    else:
        jwks_url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
        try:
            r = httpx.get(jwks_url, timeout=10)
            keys = r.json().get("keys", []) if r.status_code == 200 else []
            if keys:
                algs = ", ".join(sorted({f"{k.get('alg', '?')}/{k.get('kid', '?')[:8]}" for k in keys}))
                line(OK, f"Supabase JWKS reachable ({len(keys)} signing key(s): {algs})")
            elif r.status_code == 200:
                line(WARN, "JWKS is reachable but has no public keys - the project is probably still on the legacy HS256 secret",
                     "Migrate to JWT Signing Keys in Supabase, or set SUPABASE_JWT_SECRET as the optional fallback")
            else:
                line(BAD, f"JWKS address returned HTTP {r.status_code}: {jwks_url}", "Check SUPABASE_URL (it is the project URL, not the database URL)")
        except Exception as e:  # noqa: BLE001
            line(BAD, f"Cannot fetch the JWKS: {str(e)[:150]}", "Check SUPABASE_URL and your internet connection")
        if settings.auth_mode != "supabase":
            line(WARN, "SUPABASE_URL is set but SAARTHI_AUTH is still 'mock'", "Set SAARTHI_AUTH=supabase when you want real sign-in")
        if settings.supabase_jwt_secret:
            line(WARN, "Optional HS256 fallback (SUPABASE_JWT_SECRET) is enabled", "Remove it once the project only uses signing keys")

try:
    d = adapters.describe()
    if d["mock_areas"]:
        line(WARN, "Still MOCK: " + ", ".join(d["mock_areas"]) + "  (fine for the hackathon demo; the UI badges them as demo data)")
    else:
        line(OK, "No mock areas - everything is real")
except Exception as e:  # noqa: BLE001
    line(BAD, f"Adapter configuration error: {e}")

if settings.secret.startswith("dev-secret"):
    line(WARN, "SAARTHI_SECRET is the default", "Set SAARTHI_SECRET to a long random string before deploying")

print("\n" + ("Everything needed for the demo is ready." if failures == 0 else f"{failures} thing(s) to fix before the demo."))
sys.exit(1 if failures else 0)
