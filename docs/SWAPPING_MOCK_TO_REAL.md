# Swapping mock data for real data

Everything that is mock today sits behind an **adapter** (`backend/app/adapters/`). Routes and engines never know which one they talk to.
Each area has its own switch in `backend/.env`, so you can go live one area at a time and roll back by flipping the switch.

| Area | Switch | Mock | Real |
|---|---|---|---|
| Database | `DATABASE_URL` | local SQLite file | Supabase Postgres connection string |
| Sign-in | `SAARTHI_AUTH` | `mock` (dev login) | `supabase` (verifies Supabase access tokens against the project's JWKS) |
| Mentors | `SAARTHI_MENTORS` | `mock` (`app/seed/mentors.json`) | `db` (the `mentors` table) |
| Guardian consent | `SAARTHI_CONSENT` | `mock` (demo approve button) | `db` (the guardian gets a signed single-use link by e-mail and approves on a public page; needs the mail adapter below) |
| E-mail (guardian consent only) | `SAARTHI_MAIL` | `mock` (nothing sent; dev outbox at `GET /api/dev/outbox`) | `smtp` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`; plus `PUBLIC_BASE_URL` for the link) |
| Teacher cohort | `SAARTHI_COHORT` | `mock` (synthetic class of 24) | `db` (aggregates real learners via `cohort_members`) |

Safety rules built in: mock rows have ids that start with `mock_` and `is_mock = true`; the UI badges them **Demo data**;
a "real" switch with missing configuration **raises at start-up** (no silent fallback to mock); mock mentor replies are produced only while `SAARTHI_MENTORS=mock`.

## Turning on Supabase (database + sign-in)

Your project uses **JWT Signing Keys** (asymmetric), so there is **no shared secret to copy**. The API reads the public keys from
`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, picks the key by the token's `kid`, accepts only **ES256 / RS256**, and checks
audience `authenticated` and issuer `{SUPABASE_URL}/auth/v1`. Keys are cached (10 minutes) and re-fetched when an unknown `kid` appears.

1. **`backend/.env`**
   ```
   SUPABASE_URL=https://<project-ref>.supabase.co          # REQUIRED for SAARTHI_AUTH=supabase
   DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   SAARTHI_AUTH=supabase
   # SUPABASE_JWT_SECRET=...   optional: only if a project is still on the legacy HS256 secret; leave empty otherwise
   ```
   - URL-encode special characters in the database password (`@`→`%40`, `:`→`%3A`, `/`→`%2F`, `#`→`%23`, `?`→`%3F`).
   - If the direct host `db.<ref>.supabase.co` does not resolve (it is IPv6-only), use the **Session pooler** string from Supabase → Connect.
   - `postgresql://` and `postgres://` are accepted; SAARTHI switches them to the psycopg driver itself.
   - With `SAARTHI_AUTH=supabase` and no `SUPABASE_URL`, **the API refuses to start** (no silent fallback to mock).
2. **`frontend/.env.local`** (public values only; restart `npm run dev` afterwards)
   ```
   VITE_SUPABASE_URL=https://<project-ref>.supabase.co
   VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
   ```
3. **Supabase dashboard → Authentication → Providers → Email**: for a hackathon demo you can switch "Confirm email" off so sign-up returns a session
   immediately; if it stays on, the sign-up screen tells the user to confirm by email first.
4. `python backend/scripts/check_env.py` must show: *Database connection works (Postgres/Supabase)* and *Supabase JWKS reachable (… signing key(s))*.
   Start the API once; it creates the tables.
5. Sign-in screen: **Create account / Sign in** (supabase-js). Name, age and language are sent as user metadata at sign-up and create the learner
   row the first time the API sees the token. The access token is stored in `localStorage['saarthi.token']` and kept fresh on every refresh.
6. Then flip the other areas one at a time (they only need the database):
   ```
   python scripts/seed.py            # mentors + demo cohort -> tables
   SAARTHI_MENTORS=db                # restart, verify /mentors shows the same people
   SAARTHI_COHORT=db
   SAARTHI_CONSENT=db
   ```
7. **Row-level security**: the API connects with a privileged database role and enforces access in code (every query is scoped to the signed-in learner;
   tests cover cross-user access). Browsers talk to Supabase only for sign-in. Do not give the publishable key access to these tables
   (leave RLS **on** with no policies, or use a role the browser key cannot reach).
8. Replace the seeded mentors with real, **verified** ones before any real learner, especially minors, uses the mentor feature. Real mentors now come in through
   **Become a mentor** (Chhatrachhaya page, only with `SAARTHI_MENTORS=db`): profile → short screen → code of conduct → submit. A safeguarding lead approves it on the
   **Admin** page (visible only to the sign-in user ids listed in `SAARTHI_ADMINS`; find an id in Supabase → Authentication → Users → *User UID*; e-mail addresses are never trusted).
   An approval records which checks were really done (identity, reference, interview, police verification). Learners under 18 are only matched with real mentors who have
   identity + reference + police verification recorded (demo mentors are exempt). The pledge wording in `app/content/mentor_pledge.json` is AI-drafted: have the safeguarding lead sign it off first.

### Google sign-in ("Continue with Google")
The code is built; switching it on is configuration only. Nothing goes into this repo, `backend/.env` or `frontend/.env.local`.
1. Google Cloud Console → *APIs & Services → OAuth consent screen* (External; app name SAARTHI; support e-mail; while in "Testing" add your test users) →
   *Credentials → Create OAuth client ID → Web application*. Authorised redirect URI: `https://<project-ref>.supabase.co/auth/v1/callback`.
2. Supabase dashboard → *Authentication → Providers → Google*: enable it and paste the **Client ID** and **Client Secret** there (they live only in Supabase).
3. Supabase → *Authentication → URL Configuration*: Site URL = your deployed URL (or `http://localhost:5173` for now); Redirect URLs include
   `http://localhost:5173`, `http://127.0.0.1:5173` and the deployed origin.
4. Google does not provide an age, so a new Google user is treated as a **minor until they complete the profile screen** (age is asked once and cannot be
   changed afterwards in the app). Until then, learning works but mentor features answer `409 AGE_REQUIRED` (help for someone in distress is never blocked).
   All age decisions go through `engines/safeguarding.is_minor`.
5. Check by hand: sign in with a fresh Google account → "Tell us a little about you" → onboarding → dashboard; sign out and in → no second prompt.

Failure behaviour worth knowing: a bad or expired token gives HTTP **401**; if the JWKS address cannot be reached the API answers **503** (not 401), so the
browser does not throw away a valid session during a brief outage.

## How the swap is proven safe
`backend/tests/test_adapter_contracts.py` runs the *same* assertions against the mock and the real implementation of every adapter, and asserts that the mock
and DB mentor directories (and cohort summaries) return **identical data**. Run it after any change:

```bash
cd backend && python -m pytest tests/test_adapter_contracts.py -q
```

Real mentors now have their own side of every case: the **Mentor console** (nav entry "Mentor console" for verified mentors, only with `SAARTHI_MENTORS=db`).
They see the case report, accept (with a first slot) or decline (re-matched to someone else; a match nobody answers within 24 hours is re-matched on the next read), chat inside the app
(contact details are blocked and audited), mark the session held and record the outcome ("how well did the learner show they understand this?", 1-5), which becomes `mentor`
evidence; the learner's follow-up check closes the case. Mentors can also flag a concern, which lands in the safeguarding lead's queue on the Admin page.
Case chat has live updates (spec C04): the case sync hook polls state every 3 seconds while active, only fetching newer messages when changed, with visibility detection and optimistic sending.
**Notifications (in-app, all accounts):** a bell in the header and a badge on the Chhatrachhaya / Mentor console entry. The server creates them when a case is matched to a mentor,
accepted, answered, has an outcome recorded, when a guardian decides, when reviews are due (at most once a day), and for admins when a mentor applies or a report is filed.
They carry only first names, topic names and counts; the browser writes the sentence from its translation dictionary (`notif.<kind>` in `store.tsx`). The app polls one small
endpoint every 30 seconds while the tab is visible. Demo (mock) mentors are not accounts, so nobody is notified on their behalf. No e-mail or push is sent.
For demos without real people (mock sign-in + `SAARTHI_MENTORS=db` + `python scripts/seed.py`): `POST /api/dev/mentor-login {"mentor_id": "mock_sm_ananya"}` returns a token for a
seeded demo mentor (never in prod); use it as the bearer token to drive the console by hand.
