# C01 — Mentor sign-up, verification steps and code-of-conduct pledge

> 🚧 **RED ZONE — Abhinav is building this feature. Do not start it.** If you were told to take it over (or Abhinav is busy and says so), he will name it on the `RED ZONES CLEARED FOR ME:` line of your prompt. You may read this spec; building waits for that line. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | Chhatrachhaya — elder (Margdarshak) onboarding: profile, expertise, "legitimacy" quiz, *Maryada Aur Shapath* pledge |
| SAARTHI today | **Built 2026-10-02 (tested with mock sign-in; not yet tried with real Supabase accounts).** Before that: **Missing.** Mentors exist only as seeded rows (`backend/app/seed/mentors.json`, loaded by `scripts/seed.py`) or as fixtures in mock mode. There is no way for a real mentor to apply, no verification record, no pledge. With `SAARTHI_MENTORS=db` and real learners the directory is whatever someone inserted by hand. |
| Priority / size | P1 for any real pilot / M–L (3–4 days incl. the admin review screen) |
| Depends on | C02 uses the accounts created here; D01 (consent) for minors. Nothing to build first. |
| External accounts | none (Supabase Auth is already used) |

## 1. What a mentor gets

A "Become a mentor" page: sign in (Supabase account), choose **Skill Mentor** (technical) or **Margdarshak** (career/guidance), fill
a profile (headline, bio, years of experience, organisation optional, expertise tags, languages, weekly availability slots),
take a short subject screen, read and accept the **code of conduct**, and submit. Status is visible: *submitted → in review → approved /
needs more information / not accepted*. **Nothing becomes "verified" automatically.** A named human (safeguarding lead) approves, and
the record shows which checks were actually done.

## 2. How it works in Chhatrachhaya (the source idea)

Everything below is in the root `src/` of the repo (<https://github.com/mrgraciz123/chhatrachhayaa>). Paths are relative to the repo root.

| What | File and place |
|---|---|
| Role choice at sign-up (elder vs student) | `src/App.tsx` role-selection screen (`handleSelect('ELDER')`, ~l.160–230) and `handleOnboardingComplete()` (l.382–) which writes `role` and the profile to Firestore `users/{uid}` |
| 6-step onboarding wizard: photo+name+city → role-specific details → interests → quiz → pledge → review | `src/OnboardingScreen.tsx` (`totalSteps = 6`, l.15; steps `renderStep1…6`, l.131–293) |
| Elder fields: `organization`, `designation`, `yearsOfService`, `bio` (≤ 200 chars), interests | `OnboardingScreen.tsx` `renderStep2()` (l.165–193); data model in `README.md` ("Data Models → User") |
| "Legitimacy Check": 3 random questions from the interests, 30-second timer, pass at ≥ 2 | `OnboardingScreen.tsx` `prepareQuiz()` (l.69–86), `handleQuizAnswer()` (l.88–98), timer effect (l.57–67), `src/quizData.ts` (2 questions per topic) |
| **Pledge** ("Maryada Aur Shapath"): four promises + a checkbox gate | `OnboardingScreen.tsx` `renderStep5Shapath()` (l.252–275) |
| Verified badge | `src/ProfileScreen.tsx` (l.45–52, 63–65) |

Tech there: React, Firebase Auth + Firestore (`setDoc(users/{uid})`), Firebase Storage for the photo, EmailJS welcome mail.

### Do not copy
- **The quiz is not verification.** It asks general-knowledge questions ("CPU ka full form?", "Bharat ka Central Bank?"), picks new random
  questions on retry (`prepareQuiz` is called again at l.244), and anyone can retry forever. It proves nothing about a person.
- **Self-declared role + automatic "Verified Margdarshak".** The client writes `role` itself and `ProfileScreen` prints "Verified
  Margdarshak" for every elder and a gold ✓ for every profile (l.45–52, 64). SAARTHI's role comes from a **server-side** record and the badge
  comes from `Mentor.verification_status == "verified"` set by a human.
- Photo upload to a public bucket (privacy/safety for minors). Use an initials avatar in v1.
- `gyaanScore` (README "Data Models") — invented points. None.
- Hard-coded EmailJS ids in `src/emailService.ts` — never copy keys.
- Welcome e-mails — out of scope.

## 3. What SAARTHI already has

- `models.Mentor` (`tier`, `headline`, `bio`, `expertise`, `languages`, `availability`, `verification_status`, `active_case_cap`, `is_mock`) and
  `DbMentorDirectory` / `MockMentorDirectory` (`adapters/impl.py`); `escalation.match_mentor()` only matches `verification_status == "verified"` mentors (`engines/escalation.py` l.150–182).
- `SupabaseAuth` verifies tokens (`adapters/impl.py` l.64–123) — **but** `authenticate()` auto-creates a *Learner* row for any new user (l.108–123). Mentors must not become learners — see 4.1.
- The curated content (63 MCQs, 22 SQL tasks, rubrics) — reuse it for the subject screen.
- `Mentors.tsx` shows the public profile fields (`MentorRecord.public()` in `adapters/base.py`).

## 4. How to adapt it

### 4.1 Identity first: a mentor is an auth user with a `Mentor` row — never a Learner
1. Add `verify_token(token) -> Principal` to the `AuthProvider` port (`adapters/base.py`): verifies the JWT (reuse `SupabaseAuth._verify`)
   **without** creating a learner. `authenticate()` keeps its current behaviour for learners. `MockAuth.verify_token` accepts the same mock token.
2. New dependency `current_account` in `deps.py` using `verify_token`; `current_mentor` (in C02) = `current_account` + a verified `Mentor` row with `Mentor.id == principal.id`.
3. A person can be a learner **and** a mentor with the same login (different roles in different screens); the mentor role is always looked up on the server.
4. Roles are **never** read from `user_metadata` (users can edit it).

### 4.2 Tables (new, `models_ext/C01.py`)
```
mentor_applications(id, user_id, email, tier_requested, name, headline, bio, years_experience, organisation,
                    expertise JSON, languages JSON, availability JSON, screen_result JSON,
                    pledge_version, pledge_accepted_at, status, reviewer_id, reviewer_note, created_at, updated_at)
mentor_checks(id, mentor_id, kind, done_at, done_by, note)       # kind: identity | reference | interview | police_verification
```
`status ∈ {draft, submitted, in_review, needs_info, approved, rejected}`. On `approved`, create the `Mentor` row (id = `user_id`, `verification_status="verified"`,
`is_mock=False`) copying only reviewer-approved text. `mentor_checks` records *what* was verified and by whom, so "verified" is auditable.
**Policy (team + legal advice, not code):** decide which checks are required before a mentor can take **under-18** learners (e.g. identity +
references + police verification). Enforce it in `match_mentor` with a `mentor_checks` lookup; default = no minors until the checks exist.

### 4.3 Pledge — `content/mentor_pledge.json`
Versioned list of promises (EN + Hindi), e.g.: respect and patience; keep everything inside SAARTHI (no phone/e-mail/social handles, no off-platform
meetings); no money, gifts or favours; treat every learner as a possible minor; report any concern or disclosure to the safeguarding lead immediately;
never ask for personal photos/details; confidentiality of what learners share; you may be removed if you break these. Store `pledge_version` and
`pledge_accepted_at` on the application; require re-acceptance when the version changes (check on every mentor-console load, C02). Have the safeguarding
lead sign off the wording; it is AI-drafted until then.

### 4.4 Subject screen (replaces the legitimacy quiz)
For **Skill Mentors**: 5 questions drawn from SAARTHI's own `items.json` for the tags they claim (`diagnostic.next_probe`-style selection, but the answers are
**not** written to any learner's Twin) + 1 explain-back prompt scored with the existing grader against `rubrics.json`. Store `screen_result` (counts and covered
items) for the reviewer. It is an *input to a human decision*, never a pass/fail gate. For **Margdarshaks**: 3 short open questions
("How would you advise a student choosing between a job and a master's?") read by the reviewer — no auto-grading of career advice.

### 4.5 Routes
Applicant side — new `backend/app/routes/mentor_apply.py` (only when `mentors_mode == "db"`; else 404 "mentor sign-up is only available with real mentors"):

| Method + path | Notes |
|---|---|
| `GET /api/mentor/apply` | my application (or `null`) + the pledge text |
| `PUT /api/mentor/apply` | save draft (validate lengths: headline ≤ 120, bio ≤ 600, ≤ 10 expertise tags from `concepts.json` ids + `career`, languages ⊂ {english, hindi, hinglish}, ≤ 14 availability slots in a fixed format) |
| `POST /api/mentor/apply/screen` | returns/records the subject screen |
| `POST /api/mentor/apply/submit` | requires pledge accepted (current version) and a complete profile |

Reviewer side — `backend/app/routes/admin.py`, guarded by `current_admin` (server-side list `SAARTHI_ADMINS=<auth uids or e-mails>` in `.env`; `.env.example` placeholder only):
`GET /api/admin/mentor-applications`, `POST /api/admin/mentor-applications/{id}/decision` `{decision, note, checks:[{kind,note}]}`, `POST /api/admin/mentors/{id}/suspend`.
Every decision writes a `case_events`-style audit row (shared audit table with C02: `audit_log(id, at, actor_id, action, subject, detail JSON)`).

### 4.6 Frontend
`pages/MentorApply.tsx` (stepper: profile → availability → screen → pledge → review/submit; status page afterwards), `pages/Admin.tsx` (minimal: applications table,
open one, approve/needs-info/reject with note and check boxes; mentor suspend). Link "Become a mentor" from `Mentors.tsx` and the Login screen. Show `DemoBadge` when mentors are mock.
EN/Hindi/Hinglish strings (pledge text especially).

## 5. Files to create / touch
`adapters/base.py` + `impl.py` (`verify_token`), `deps.py` (`current_account`, `current_admin`), `config.py` (`SAARTHI_ADMINS`), `.env.example`,
`models_ext/C01.py` (new), `content/mentor_pledge.json` (new) + `content.py`, `routes/mentor_apply.py` (new), `routes/admin.py` (new),
`engines/escalation.py` (`match_mentor` check for minors), `frontend/src/pages/MentorApply.tsx`, `Admin.tsx` (new), `App.tsx`, `frontend/src/api_ext/C01.ts`,
`docs/SWAPPING_MOCK_TO_REAL.md` (replace "Replace the seeded mentors with real, verified ones" step 8 with this flow), tests `test_mentor_apply.py`.

## 6. Tests (minimum)
1. `verify_token` on a valid Supabase token does **not** create a `Learner` row (assert count unchanged); `authenticate` still does.
2. Application cannot be approved by a non-admin (403); decisions require a note; approving creates a `Mentor` row with `verification_status="verified"` and the audit row.
3. Role is never taken from token metadata (token with `user_metadata.role="mentor"` ⇒ still 403 on mentor routes).
4. Submit without current pledge version ⇒ 422; pledge version bump ⇒ re-acceptance required.
5. Field validation (lengths, tag whitelist, availability format); another user cannot read/edit my application.
6. `match_mentor` never returns an unverified or suspended mentor, and skips mentors lacking the required checks when the learner is a minor.
7. Mock mode: apply routes return 404 and the UI hides the entry points.

## 7. Done when
- [ ] A real person can apply, accept the pledge, and see their status; an admin can approve with recorded checks; the mentor appears in the directory.
- [ ] No automatic verification anywhere; the "✓ verified" badge comes only from a human decision.
- [ ] Mentors are not created as learners; roles are server-side.
- [ ] Policy for minors is decided and enforced, or minors are blocked from real mentors.

## 8. Risks and traps
- This is a **safeguarding** feature. Do not ship real mentors to real minors on code alone; the human process (checks, review, removal) must exist first.
- Application text becomes public after approval — the reviewer edits it; don't render raw applicant HTML (React escapes by default; keep it that way).
- Rate-limit submissions and keep applications private to the applicant and admins.
- `SAARTHI_ADMINS` is an access list: placeholders only in `.env.example`; never commit real ids.
