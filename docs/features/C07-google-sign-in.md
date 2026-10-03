# C07 — "Continue with Google" (with a mandatory age step)

> 🚧 **RED ZONE — Abhinav is building this feature. Do not start it.** If you were told to take it over (or Abhinav is busy and says so), he will name it on the `RED ZONES CLEARED FOR ME:` line of your prompt. You may read this spec; building waits for that line. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | Chhatrachhaya — Google sign-in popup, then profile/role onboarding for new users |
| SAARTHI today | **Built 2026-10-02 (age gate tested; Google itself not yet tried with a real account — needs the Google/Supabase configuration in `docs/SWAPPING_MOCK_TO_REAL.md`).** Before that: **Missing.** Sign-in is e-mail + password through Supabase (`pages/Login.tsx`), plus the mock demo login. |
| Priority / size | P1 / S–M (1–1.5 days + 30 min of dashboard configuration) |
| Depends on | nothing. Interacts with C06 (birth year) and D01 (guardian consent). Mentors/admins who use Google rely on C01's `verify_token`. |
| External accounts | A **Google Cloud** OAuth client (free) configured in the **Supabase dashboard**. No Google keys ever go into this repo. |

## 1. What the user gets

A "Continue with Google" button on the sign-in/sign-up screen. First time only, a short **"Tell us a little about you"** step asks for age (or birth year), language and display name — because Google does not
provide age and SAARTHI's safety rules for under-18 learners depend on it. After that they continue to the normal onboarding. Returning users go straight in.

## 2. How it works in Chhatrachhaya (the source idea)

| What | File and place (repo root = <https://github.com/mrgraciz123/chhatrachhayaa>) |
|---|---|
| Google sign-in with a popup; closing the popup is silent; other errors show the Firebase error code | `src/App.tsx` `handleGoogleSignIn()` (l.63–74) — `new GoogleAuthProvider()` + `signInWithPopup(auth, provider)` |
| After any sign-in, look up the user's profile document; **no document ⇒ new user ⇒ role selection → onboarding**; a 5-second timeout so the app never hangs if the database is unreachable | `src/App.tsx` `onAuthStateChanged` effect (l.319–370; new-user branch l.345–349, timeout l.324–330) |
| E-mail/password sign-up and sign-in in the same screen | `src/App.tsx` l.1–62 (imports `createUserWithEmailAndPassword`, `signInWithEmailAndPassword`) |
| Local-only "no signup" demo auth (not Firebase) | `src/pages/AuthPage.tsx` — an older prototype screen; ignore it |

Tech there: Firebase Authentication (Google provider), React state machine (`auth → role → onboarding → done`).

### Do not copy
- Letting the client decide the user's role (see C01) or write the profile document itself.
- Welcome e-mails with embedded EmailJS keys (`src/emailService.ts`).
- Silently continuing when the profile lookup times out (`l.350–359` falls back to a `localStorage` flag). SAARTHI must **fail safe**: if the profile cannot be loaded, show an error — never assume "adult, onboarding done".

## 3. What SAARTHI already has

- `frontend/src/supabase.ts` (client with `detectSessionInUrl: true`) and `store.tsx` (mirrors the Supabase access token to `localStorage['saarthi.token']`, `onAuthStateChange`, `signOut`). Redirect-based OAuth therefore works with the existing plumbing.
- `SupabaseAuth.authenticate()` (`adapters/impl.py` l.108–123) creates the `Learner` on first sight from `user_metadata` (`name`, `age`, `language`).

### ⚠ The safety gap this feature must close
For a Google user `user_metadata` has **no `age`**, so `authenticate()` falls back to `age = 20` (l.115–117) and the person is treated as an **adult** everywhere: consent (`impl.py` l.199, 215, 231),
the case report's `age_band` (`escalation.py` l.93), `_me().is_minor` (`routes/core.py` l.72), `consent_status` and `self_grant` (`routes/mentor.py` l.125, 167). A 15-year-old who clicks "Continue with Google" would skip guardian approval.
Age is self-declared and cannot be verified by SAARTHI, so the rule is: **until the learner has told us, treat them as a minor.**

## 4. How to adapt it

### 4.1 Backend
1. **Central helper** `backend/app/engines/safeguarding.py`: `is_minor(learner) -> bool: return learner.age < 18 or not learner.settings.get("age_confirmed", True)` (default `True` so existing rows and e-mail sign-ups, which supply an age, keep working).
   Replace **all seven** direct `learner.age …18` checks listed above with `safeguarding.is_minor(learner)`. Add a test that greps the code base for `age < 18`/`age >= 18` outside this helper and fails if it finds one.
2. `SupabaseAuth.authenticate()`: when `user_metadata.age` is missing, create the learner with `settings={"age_confirmed": False, "provider": claims.get("app_metadata", {}).get("provider")}`; use `user_metadata.full_name`/`name` for the display name; language default `english`.
   With a supplied age (e-mail sign-up) set `age_confirmed: True`.
3. `POST /api/me/complete-profile` (new, `routes/profile_complete.py`): `{name?, age (10–100) or birth_year, language}`; sets `age`, `age_confirmed=True`, language (and `birth_year` if C06/C07 adopt it). **Idempotent but not re-editable**: once confirmed, changing age is a support action (admin endpoint with an audit row) — otherwise a minor can flip to "adult" to bypass guardians.
4. `_me()` returns `age_confirmed` and `needs_profile` (`not age_confirmed`).
5. Until `age_confirmed`, mentor features are blocked: `POST /api/cases` and `POST /api/consent/*` return `409 {"code": "AGE_REQUIRED"}`; learning features still work.

### 4.2 Frontend
- `Login.tsx` (real mode): "Continue with Google" button calling `supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } })`; disabled with a hint when `supabaseConfigured` is false; show Supabase's error text if the provider is not enabled. Keep e-mail/password as is.
- `App.tsx` `Guard`: if `me.needs_profile` → `<Navigate to="/complete-profile">` **before** the onboarding redirect. New `pages/CompleteProfile.tsx` (name, age or birth year, language, one sentence on why age is asked). Show the existing under-18 note.
- After the Google redirect the page loads at `/`; `store.tsx` already picks up the session and calls `/api/me`. Add handling for `409 AGE_REQUIRED` in `Mentors.tsx` (link to the profile completion).
- Strings through `DICT` (EN/Hindi/Hinglish).

### 4.3 Supabase and Google configuration (document in `docs/SWAPPING_MOCK_TO_REAL.md`, the owner does it)
1. Google Cloud Console → *APIs & Services → OAuth consent screen* (External; app name SAARTHI; support e-mail; add test users while in "Testing") → *Credentials → Create OAuth client ID → Web application*.
   Authorised redirect URI: `https://<project-ref>.supabase.co/auth/v1/callback`.
2. Supabase dashboard → *Authentication → Providers → Google*: enable, paste **Client ID** and **Client Secret** (these live only in Supabase).
3. Supabase → *Authentication → URL Configuration*: Site URL = the deployed URL (or `http://localhost:5173` for now); Redirect URLs include `http://localhost:5173`, `http://127.0.0.1:5173` and the deployed origin.
4. Nothing to add to `backend/.env` or `frontend/.env.local` (the existing `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` are enough).

## 5. Files to create / touch
`engines/safeguarding.py` (new), `adapters/impl.py` (3 usages + `authenticate`), `engines/escalation.py` (1), `routes/core.py` (2), `routes/mentor.py` (2 + `409 AGE_REQUIRED`), `routes/profile_complete.py` (new),
`frontend/src/pages/Login.tsx`, `pages/CompleteProfile.tsx` (new), `App.tsx`, `store.tsx`, `pages/Mentors.tsx`, `frontend/src/api_ext/C07.ts`, `docs/SWAPPING_MOCK_TO_REAL.md`, tests `test_age_gate.py`, additions to `test_adapter_contracts.py`.

## 6. Tests (minimum)
1. A token with `app_metadata.provider="google"` and **no** age creates a learner with `age_confirmed=False`; `GET /api/me` ⇒ `is_minor: true`, `needs_profile: true`.
2. For that learner `POST /api/cases` and `POST /api/consent/request` ⇒ 409 `AGE_REQUIRED`; learning endpoints (`/api/probe/next`, `/api/dashboard`) still work.
3. `POST /api/me/complete-profile` with age 25 ⇒ adult; with age 15 ⇒ minor (guardian flow applies, D01); a second call cannot change the age (409).
4. An e-mail sign-up token **with** `user_metadata.age = 15` ⇒ `age_confirmed=True`, minor.
5. The repo-wide check: no `age < 18` / `age >= 18` outside `safeguarding.py`.
6. Age bounds: 9 and 101 ⇒ 422.
7. **Manual (cannot be automated offline):** with Google configured, sign in on a fresh account → complete-profile appears → onboarding → dashboard; sign out/in → no second prompt. Record the result in the hand-off note and say plainly it was verified manually.

## 7. Done when
- [ ] Google sign-in works end to end on localhost and the deployed URL; new Google users must complete the age step before any mentor feature.
- [ ] No code path treats an unconfirmed age as adult; all age checks go through `safeguarding.is_minor`.
- [ ] Configuration steps are documented; no secrets in the repo.

## 8. Risks and traps
- Age is self-declared. State it in the UI copy and in the safeguarding docs; do not claim verification.
- Supabase `user_metadata` is user-editable — never trust it for anything except initial display defaults.
- The OAuth redirect drops query parameters; if you add "invite" links later, store them before redirecting.
- Test with an account that has **no** display name set in Google (metadata fields differ).
