import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Tests must NEVER read backend/.env: it holds real keys and a real database URL. Environment variables beat the .env file,
# so pin everything the tests depend on (and blank every credential) before the app is imported.
for k, v in {
    "SAARTHI_ENV": "dev", "SAARTHI_LLM_MODE": "gemini", "SAARTHI_AUTH": "mock", "SAARTHI_MENTORS": "mock",
    "SAARTHI_CONSENT": "mock", "SAARTHI_COHORT": "mock", "SAARTHI_SECRET": "test-secret-test-secret-test-secret-123",
    "DATABASE_URL": "sqlite://", "SUPABASE_URL": "", "SUPABASE_JWT_SECRET": "", "GEMINI_API_KEY": "",
    "SAARTHI_MODEL_FALLBACKS": "", "ELEVENLABS_API_KEY": "", "ELEVENLABS_AGENT_ID": "", "ELEVENLABS_VOICE_ID": "",
    "ELEVENLABS_AGENT_PUBLIC": "false",
}.items():
    os.environ[k] = v
