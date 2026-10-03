# D01 — Real guardian consent for under-18 learners (and a security fix)

> 🚧 **RED ZONE — Abhinav is building this feature. Do not start it.** If you were told to take it over (or Abhinav is busy and says so), he will name it on the `RED ZONES CLEARED FOR ME:` line of your prompt. You may read this spec; building waits for that line. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | Not from TESSA or Chhatrachhaya (Chhatrachhaya targets 16–24 and has no guardian flow). This is a gap in SAARTHI's own safeguarding design (report v3.0 promises guardian approval before a minor can talk to a mentor). |
| SAARTHI today | **Built (2026-10-02), not yet verified with a real mailbox.** Before that: mock worked and real was safe but unfinished. With `SAARTHI_CONSENT=mock` a clearly labelled "Demo: approve as guardian" button grants consent. With `SAARTHI_CONSENT=db` the code can *verify* a signed guardian token but there is **no way for a guardian to receive or use it**, so a minor simply stays `pending` and cannot reach a mentor. **Step 0 (the self-approval hole) is fixed** — see below; everything else in this spec is still to build. |
| Priority / size | **P0 (safety) before any real under-18 learner touches the mentor feature** / M (2–3 days; Step 0 alone is ~30 minutes) |
| Depends on | C07 (`safeguarding.is_minor`) is strongly recommended; C05 (notifications) optional. Independent otherwise. |
| External accounts | An outgoing e-mail account for real delivery (SMTP, e.g. a provider's free tier) — a **mock mailer** is built first. |

> Not legal advice. India's Digital Personal Data Protection Act, 2023 (Section 9) requires **verifiable parental consent** before processing a child's personal data. Before real minors are onboarded,
> get qualified advice on what "verifiable" must mean for SAARTHI (e-mail confirmation is the weakest form). Decide that first; this spec builds the mechanism, not the legal conclusion.

## Step 0 — the self-approval hole: ✅ FIXED (commit "Close the guardian-consent self-approval hole")

**What was wrong (line numbers describe the code *before* the fix):**
1. `POST /api/consent/request` (`routes/mentor.py` l.133–136) returns the raw result of `adapters.consent().request(...)`.
2. For a minor, `_ConsentBase.request()` (`adapters/impl.py` l.213–218) put the **signed guardian token into that result** (`out["guardian_token"] = …`) — for the *real* adapter too.
3. `POST /api/consent/guardian` (`routes/mentor.py` l.154–161) accepts that token from the **same signed-in learner** and calls `DbConsent.grant`, which only checks that the token's `learner` and `scope` match (l.230–239).
   ⇒ A minor can call request → copy the token → call guardian, and "guardian approval" is granted with no guardian involved.
**Reproduced by running the API** with `SAARTHI_CONSENT=db`: a 15-year-old's `mentor_sessions` consent went from `pending` to `granted` (`granted_by: "guardian"`) using only their own token.
(`create_case` hides the token unless the adapter is mock — `escalation.open_case`, `"guardian_token": … if adapters.consent().is_mock else None` — but `/consent/request` does not.)

**What the fix does (implemented):** `_ConsentBase.request()` returns the token **only when `self.is_mock`**; `DbConsent.request` returns just `{scope, status, needs_guardian}`. Token creation moved to an internal
`impl.mint_guardian_token(learner, scope)` whose docstring says it may only be given to the code that *delivers* the link to the guardian — that is the hook the e-mail flow below plugs into.
Regression tests: `tests/test_api.py::test_a_minor_cannot_approve_their_own_guardian_consent` (fails on the old code), `::test_a_real_guardian_token_still_works_and_only_for_that_learner`,
and the tightened contract tests in `tests/test_adapter_contracts.py` (real adapter returns exactly `{scope, status, needs_guardian}`; tokens are bound to one learner **and one scope**).
**Consequence until the rest of this spec ships:** with `SAARTHI_CONSENT=db` a minor cannot be approved by anyone (no delivery path yet) — that is the safe failure. Keep `SAARTHI_CONSENT=mock` for demos and keep the "Demo data" badges.
The old learner-authenticated route `POST /api/consent/guardian` still exists but is now unreachable in practice (nobody holds a valid token); replace it with the public guardian endpoints (section 3.4) and delete it.

## 1. What the people get

- **The learner (under 18)** who asks for a mentor sees "We need your parent or guardian's OK first": they enter the guardian's e-mail, see exactly what will be sent and what the guardian is agreeing to, and then a status ("Waiting for guardian — sent to g***@gmail.com · resend · change e-mail").
- **The guardian** receives a short e-mail (Hindi or English) with a link. The page — **no account, no login** — explains in plain words: who asked (first name only), what SAARTHI is, what a mentor can see (the case report fields) and cannot do (no contact outside SAARTHI, all messages logged and screened, sessions are text inside the app), and offers **Approve** or **Do not approve**. After approving they get a "withdraw approval" link they can keep.
- **After approval** the waiting case is matched automatically (`escalation.resume_after_consent` already exists). After withdrawal active cases pause and the learner is told gently.

## 2. What SAARTHI already has

- `Consent(learner_id, scope, status, granted_by, is_mock, updated_at)`; scopes `mentor_sessions`, `transcript_share`; `ConsentProvider` port with `MockConsent` / `DbConsent` (`adapters/base.py`, `adapters/impl.py` l.192–249); contract tests in `tests/test_adapter_contracts.py`.
- Signed tokens via `itsdangerous` (`_guardian_serializer`, salt `saarthi-guardian-consent`, 7-day expiry) using `SAARTHI_SECRET`.
- Case state `awaiting_consent` and `escalation.resume_after_consent()` (`engines/escalation.py` l.250–254); the learner UI callouts in `Mentors.tsx`.
- The learner-side flags (`is_minor`) — currently `learner.age < 18` in 7 places (see C07 for the central helper).

## 3. How to build it

### 3.1 Principles
1. The guardian token goes **only** to the guardian (by e-mail), **never** to the learner's browser (except in mock mode, labelled demo).
2. Tokens are **single-use** and expire (default 7 days); a replayed link shows "already used".
3. The guardian page and its two endpoints need **no authentication** — so they must be tiny, rate-limited, and reveal almost nothing (first name, purpose, scope).
4. Everything is recorded in the audit log (`audit_log`, shared with C01/C02): request sent, viewed, approved, declined, withdrawn.
5. Minimise personal data: store the guardian e-mail only while needed; show it masked to the learner; delete on withdrawal, on account deletion, and after the case closes (decision recorded in the commit message).

### 3.2 Tables (new, `models_ext/D01.py`)
```
guardian_requests(id, learner_id (FK CASCADE), scope, guardian_email, lang, token_id, status, created_at, expires_at, decided_at)
                    # status: sent | approved | declined | withdrawn | expired
consent_tokens(token_id PK, purpose ('approve'|'withdraw'), used_at)       # single-use bookkeeping
```
`Consent.status` already has room for `requested` and `declined` (free-form `String(16)`; **no column change**). Include `guardian_requests` in the export (without the raw e-mail — masked) and in the delete cascade.

### 3.3 Mail adapter (so it can be mocked and swapped like everything else)
- Port `MailSender.send(to, subject, text, html=None)` in `adapters/base.py`; `MockMailer` (appends to an `outbox` list and logs the link — visible in dev through `GET /api/dev/outbox`, disabled in prod) and `SmtpMailer` (stdlib `smtplib` + TLS; settings `SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM`).
- Switch `SAARTHI_MAIL=mock|smtp` in `config.py` and `backend/.env.example` (placeholders); `smtp` with missing settings ⇒ refuse to start. Add `PUBLIC_BASE_URL` (used to build the link; e.g. `https://saarthi.example` or `http://localhost:5173`).
- Add a row to `docs/SWAPPING_MOCK_TO_REAL.md` and contract tests (both mailers accept the same call and return a message id/None; `SmtpMailer` tested with a patched `smtplib.SMTP`).
- E-mail text: short, in the learner's chosen language (EN or Hindi), no marketing, no tracking pixels, includes who/why, what is approved, expiry, a "this wasn't me / I don't know this person" line, and a support contact. Draft it for the safeguarding lead to approve.

### 3.3b Provider interface change
`ConsentProvider.request(db, learner, scope, guardian_email=None) -> {status, needs_guardian, guardian_hint}`; for `DbConsent` it creates the `guardian_requests` row, mints a single-use token, and calls the mailer. `MockConsent.request` may still return `guardian_token` (demo). Remove the route `POST /api/consent/guardian` (the learner-authenticated one); replace with the public endpoints below. Keep `POST /api/consent/grant-demo` (mock only).

### 3.4 Routes — new `backend/app/routes/guardian.py` (public) and edits to `routes/mentor.py`
| Method + path | Auth | Notes |
|---|---|---|
| `POST /api/consent/request` `{scope, guardian_email, lang}` | learner | validates e-mail, max 3 requests per learner per day, per-address cooldown; response contains **no token** |
| `GET /api/guardian/preview?token=` | none | returns `{learner_first_name, scope_text, tier, what_mentors_see[], expires_at}`; token invalid/used/expired ⇒ a generic 404-style response (don't reveal which) |
| `POST /api/guardian/decision` `{token, decision: "approve"|"decline"}` | none (token) | marks the token used, sets `Consent` to `granted`/`declined` (`granted_by = "guardian"`), writes audit, runs `resume_after_consent` on approve, notifies the learner (C05 `consent_granted` / `consent_declined`) |
| `POST /api/guardian/withdraw` `{token}` | none (long-lived withdraw token) | `Consent → revoked`; active cases → `awaiting_consent`; audit + notify |
| `GET /api/consent` | learner | now includes `request: {status, masked_email, sent_at, can_resend_at}` |
Rate-limit the public endpoints per IP (e.g. 20/min) and add a generic delay on invalid tokens. Never put the token in logs (log `token_id`).

### 3.5 Frontend
- `pages/Mentors.tsx`: replace the demo-only callout in real mode with a small form (guardian e-mail + language) and status states (not requested / waiting / approved / declined / withdrawn) with resend/change.
- New public route `/guardian/:token` → `pages/GuardianConsent.tsx`, **outside** `<Guard>` (no login, minimal layout, no navigation, no learner data except first name). Strings via `DICT` (EN/Hindi; this is the most important page to have reviewed by a native speaker).
- Keep the mock "Demo: approve as guardian" button, visible only when `consent.mock`.

## 4. Files to create / touch
`adapters/base.py` (`MailSender`, `ConsentProvider.request` signature), `adapters/impl.py` (`_ConsentBase.request`, `DbConsent`, `MockMailer`, `SmtpMailer`), `adapters/__init__.py`, `config.py`, `.env.example`,
`models_ext/D01.py` (new), `routes/guardian.py` (new), `routes/mentor.py` (`consent_request`; remove `consent_guardian`), `engines/escalation.py` (resume/pause on withdrawal),
`frontend/src/pages/GuardianConsent.tsx` (new), `Mentors.tsx`, `App.tsx` (public route), `frontend/src/api_ext/D01.ts`, `docs/SWAPPING_MOCK_TO_REAL.md`, tests `test_guardian_consent.py` + contract-test additions.

## 5. Policy decisions to record (in this spec and the commit message; the team decides, the code follows)
- What level of "verifiable" is required for the pilot (e-mail link only? institution consent through a teacher? ID/payment-based verification later?).
- Which checks a mentor must have to take minors (see C01 §4.2).
- Retention: guardian e-mail deleted when consent is withdrawn / account deleted / N days after case closure.
- Whether learners aged 16–17 may self-consent to anything (current rule: no — `mentor_sessions` always needs a guardian under 18).

## 6. Tests (minimum)
1. **Regression for Step 0 (already in the repo, keep it green):** in `DbConsent` mode `POST /api/consent/request` for a minor returns **no** `guardian_token`. When the full flow adds `guardian_hint`, update the exact-keys assertion in `tests/test_adapter_contracts.py` to `{scope, status, needs_guardian, guardian_hint}`.
2. A minor cannot obtain consent by any authenticated call (the old `POST /api/consent/guardian` route is gone ⇒ 404/405).
3. Happy path: request → mail outbox has exactly one message to the guardian with a link → `preview` shows first name only → `decision approve` ⇒ `Consent.granted`, waiting case matched, audit rows written.
4. Token single-use (second approve ⇒ generic invalid), expired (patch time) ⇒ invalid, wrong purpose (withdraw token on approve) ⇒ invalid, tampered ⇒ invalid; all responses identical in shape.
5. Decline ⇒ `declined`; learner sees it; no mentor ever matched; a new request later is allowed.
6. Withdraw ⇒ `revoked`; active cases ⇒ `awaiting_consent`; mentors cannot message in those cases (409 as today).
7. Rate limits: 4th request/day ⇒ 429; the same address within cooldown ⇒ 429; public endpoints throttle by IP.
8. Privacy: `preview` contains no e-mail, no last name, no ids; logs contain `token_id`, never the token; export masks the e-mail; delete removes rows.
9. Mock mode unchanged: `grant-demo` works, labelled demo; `consent.mock == true`.
10. `SAARTHI_MAIL=smtp` without settings refuses to start.

## 7. Done when
- [ ] The self-approval hole is closed and covered by a regression test (Step 0 can ship alone).
- [ ] A real guardian can approve/decline/withdraw from an e-mailed link with no account; the learner sees status; waiting cases resume.
- [ ] Mail sending is an adapter (mock + SMTP) with contract tests and env documentation.
- [ ] Policy decisions above are written down; legal advice obtained before real minors are onboarded.

## 8. Risks and traps
- E-mail alone cannot prove the recipient is the guardian (a minor can enter their own second address). Be honest in the UI/docs; use stronger verification if advice says so.
- Don't send anything to the learner's own e-mail by mistake: if the guardian address equals the learner's account e-mail, reject it.
- Spam/abuse: the request endpoint could be used to send unsolicited e-mails to arbitrary people — keep the daily caps, include an "I don't know this person" report link, and use a neutral template.
- Test the e-mail in Hindi on real clients (Gmail mobile) — Devanagari in subject lines needs UTF-8 headers (`email.message.EmailMessage` handles this; don't hand-build headers).
