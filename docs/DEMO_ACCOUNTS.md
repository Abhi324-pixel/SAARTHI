# Demo accounts (local only)

Fake accounts so you can click through the mentor, guardian and notification screens on one machine. They exist only in the local SQLite file
(`backend/data/saarthi.db`, not committed). The seed script refuses to run against a real sign-in, a production setting or a hosted database.

## 1. Start the backend in demo mode

PowerShell, from `backend/` (these variables override `backend/.env` for this window only, so your real `.env` is untouched):

```powershell
$env:SAARTHI_AUTH="mock"; $env:SAARTHI_MENTORS="db"; $env:SAARTHI_CONSENT="db"; $env:SAARTHI_COHORT="db"; $env:SAARTHI_MAIL="mock"; $env:DATABASE_URL="sqlite:///D:/SAARTHI/backend/data/saarthi.db"
python scripts/seed_demo.py
python -m uvicorn app.main:app --port 8000
```

The seed prints one `localStorage.setItem(...)` line per account. Start the frontend as usual (`npm run dev` in `frontend/`).

## 2. Switch accounts

On the login page, open **☰ Demo accounts** (top right) and click a name. The menu only appears when the backend runs in mock sign-in and not in production, and
only lists the four fixed fake accounts. To switch, sign out and use the menu again. (Fallback: the seed script also prints `localStorage.setItem(...)` lines for the browser Console.)

| Account | What to look at |
|---|---|
| **Riya (age 15)** | Chhatrachhaya: the guardian e-mail form (D01). Case needs consent first. The bell fills as the mentor acts (C05). |
| **Arjun (age 22)** | Adult path: Chhatrachhaya works without guardian consent. |
| **Mentor Ananya Rao / Vikram Singh** | "Mentor console" in the nav (C02): accept, chat, record outcome. The bell shows new cases. |

## 3. Walk-through (about 3 minutes)

1. As **Riya**: Chhatrachhaya, enter a guardian e-mail. In mock mail mode no e-mail is sent; the message is kept in a dev outbox. While signed in as Riya, open `http://localhost:8000/api/dev/outbox` in the same browser's console via `fetch` (it needs her token), or use the outbox viewer the Chhatrachhaya page offers in dev mode, and copy the link from the message text. Open it in another tab as the guardian and approve.
2. Riya asks for a mentor on a concept. The bell shows the match.
3. Switch to **Mentor Ananya**: Mentor console, open the case, accept, send a message. Riya's bell and badge update within 30 seconds.
4. Mentor records an outcome. Riya's case shows it and the mastery evidence moves.

Admin screen: put your own account id in `SAARTHI_ADMINS` (find it under Profile or `GET /api/me`) before starting the backend.

Reset everything: stop the backend and delete `backend/data/saarthi.db`.
