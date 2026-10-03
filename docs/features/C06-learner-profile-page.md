# C06 — Learner profile page ("Parichay")

| | |
|---|---|
| Source | Chhatrachhaya — Parichay profile screen and the student onboarding fields |
| SAARTHI today | **Partial.** `pages/Settings.tsx` has language, data export/delete, a "what is mock" panel and the dev tools. A learner cannot see or edit who SAARTHI thinks they are (name, education, institution, goal) or see a simple summary of what they have actually done. The header name links to Settings. |
| Priority / size | P2 / S (1 day) |
| Depends on | nothing. Uses T04 (streak) and C07 (age handling) if they exist. |
| External accounts | none |

## 1. What the learner gets

A **Profile** page: name, avatar (initials), education level, institution/college, a one-sentence goal, language; real activity numbers ("12 concepts at proficient or better",
"41 checks answered", "3 teach-backs finished", "member since Oct 2026", streak if T04 exists); a **Privacy** panel (what mentors can see, guardian status for under-18, transcript-sharing
switch, download my data, delete my account). Editing is simple and every field is optional except the name. No photo upload, no points.

## 2. How it works in Chhatrachhaya (the source idea)

| What | File and place (repo root = <https://github.com/mrgraciz123/chhatrachhayaa>) |
|---|---|
| Profile screen: initials avatar, role label, city, bio, three stat tiles, interest/expertise chips, availability, settings list, sign-out | `src/ProfileScreen.tsx` (l.6–157; stats l.75–86; chips l.89–98; availability l.100–108; settings rows l.110–126) |
| Student fields collected at onboarding: `educationLevel`, `institution`, `careerGoal`, `interests`, `bio` (≤ 200), `city`, photo | `src/OnboardingScreen.tsx` `renderStep1/2/3` (l.131–211); data model in `README.md` ("Data Models → User") |
| Profile document stored under `users/{uid}` and read back with `getDoc` | `src/App.tsx` l.319–370 (`onAuthStateChanged`), `src/ProfileScreen.tsx` l.10–20 |

Tech there: React, Firebase Firestore/Storage.

### Do not copy
- **"Verified Margdarshak" and a gold ✓ for everyone** (`ProfileScreen.tsx` l.45–52, 64) — verification is a human decision (C01), not a label.
- **`Gyaan Score` default `'100'`** (l.79) and the "sessions / helped" tiles read from an optional `stats` object nobody writes — invented. SAARTHI shows only counts computed from stored evidence.
- **Photo upload to Firebase Storage** with a public download URL (`OnboardingScreen.tsx` l.106–129) — a child-safety and privacy risk; v1 uses initials.
- **The "Push Mock Data to Firebase (Dev)" button inside the profile** (l.138–150). SAARTHI's demo tools stay in Settings and disappear when `SAARTHI_ENV=prod`.
- Settings rows that do nothing (notifications, language, privacy, help are inert placeholders, l.114–126). Every control must work or not exist.
- City as a mandatory field. Location is sensitive for minors; collect only if a feature needs it (none does today).

## 3. What SAARTHI already has

- `Learner` columns: `name, email, age, language_pref, role_id, weekly_hours, horizon_weeks, onboarded, settings (JSON), created_at`. `GET /api/me`, `PATCH /api/me` (language, hours, weeks),
  `GET /api/me/export`, `DELETE /api/me` (`routes/core.py`).
- Consent status via `adapters.consent()` (`_me()` already returns it) and the transcript-sharing switch inside `Mentors.tsx` (`api.consentSelf('transcript_share')`).
- `CohortMember.display_name` (teacher cohort view) — an institution field can later link a learner to a cohort (out of scope here).
- `ui.tsx` components; `Genome.tsx` already shows the evidence-based picture — the profile page should link to it rather than duplicate it.

## 4. How to adapt it

### 4.1 Data (no new columns — use `Learner.settings`)
`settings["profile"] = {"education": "ug", "institution": "...", "goal_text": "...", }` with allowed values for `education`:
`school_9_12, diploma, undergraduate, postgraduate, working, other` (a gentler list than the source's "Dropout"). Lengths: institution ≤ 80, goal ≤ 200. `goal_text` is the same field T01 fills — keep one source of truth.
**Name** is `Learner.name` (1–80). **Age is not editable here** (it drives safeguarding). See the note on birth year below.

> **Age vs birth year (cross-cutting — decide with C07 and D01).** SAARTHI stores `Learner.age` as a static integer entered once. A learner who signs up at 17 is treated as a minor for ever,
> and an OAuth sign-up defaults to 20 (see C07). The robust fix is to store **birth year** in `settings["birth_year"]` and compute age, refreshing `Learner.age` on each sign-in. If the team agrees, build it as part of C07 and make this page read it.

### 4.2 Stats — computed, labelled, honest (`engines/profile_stats.py`)
```
stats(db, learner) -> {
  "concepts_proficient_or_better": 12, "concepts_assessed": 19, "checks_answered": 41,
  "work_products_run": 17, "explain_backs_finished": 3, "interviews_finished": 1,
  "mentor_cases_closed": 1, "member_since": "2026-10-01", "streak": {...} | null }
```
Sources: `mastery.concept_views()`, counts of `EvidenceEvent` by `source_type` **excluding `grader == "simulated"`** (the demo helpers), `LearningSession(mode, status="done")`, `MentorCase(status="closed")`.
No totals that can't be reproduced from rows; no "level"/XP/score.

### 4.3 Routes — new `backend/app/routes/profile.py`
| Method + path | Notes |
|---|---|
| `GET /api/profile` | profile fields + `stats` + consent summary + "what mentors see" (the exact keys of `escalation.build_report`'s `learner` block) |
| `PATCH /api/profile` | `{name?, education?, institution?, goal_text?}`; validates enums/lengths; strips control characters; never accepts `age`, `email`, `role_id` here |
Keep `PATCH /api/me` as is for language/hours/weeks. The export includes the profile block (register it with `privacy.register_export` — don't edit `export_me`).

### 4.3b Privacy panel content
- Plain list of what a mentor sees in a case (first name, age band, language, goal, concept evidence…) and what they never see (full name, e-mail, anything outside the case).
- Guardian status (minors): `granted/pending` with a link to the D01 guardian-approval explanation.
- Transcript sharing switch (move the one from `Mentors.tsx` here and link back).
- Download my data / Delete my account (reuse the existing handlers from `Settings.tsx`).

### 4.4 Frontend
`pages/Profile.tsx` (+ route `/profile` in `App.tsx`; header name link → `/profile`; `Settings.tsx` keeps language, "what is mock", dev tools). Cards: Identity (edit form), Activity (stats), Privacy.
Avatar: initials on a deterministic colour from a hash of the learner id (no network call). Strings through `DICT` (EN/Hindi/Hinglish). Mobile-first layout.

## 5. Files to create / touch
`engines/profile_stats.py` (new), `routes/profile.py` (new), `models_ext/C06.py` or `engines/profile_stats.py` (`privacy.register_export("profile", ...)`), `frontend/src/pages/Profile.tsx` (new), `Settings.tsx` (trim), `App.tsx`, `store.tsx`,
`frontend/src/api_ext/C06.ts`, tests `test_profile.py`.

## 6. Tests (minimum)
1. `PATCH` validates: unknown `education` ⇒ 422; institution > 80 ⇒ 422; sending `age`/`email`/`role_id` is ignored or 422 (assert the stored values are unchanged).
2. Stats equal counts recomputed directly from rows; `grader="simulated"` events are excluded; a learner with no history gets zeros, not errors.
3. Another learner's data never appears; `GET /api/profile` without a token ⇒ 401.
4. Name change does not alter older case reports (they are snapshots) but new cases use the new first name.
5. The "what mentors see" list matches the keys produced by `build_report` (test fails if someone adds a key to the report without updating the page).
6. Export contains the profile block; delete removes it.

## 7. Done when
- [ ] Profile page shows editable identity, real activity numbers, and a privacy panel that matches what mentors actually receive.
- [ ] No photo, no points, no fake verification badge; every control works.
- [ ] Age cannot be edited here; the birth-year decision has been made (done in C07 or explicitly deferred).

## 8. Risks and traps
- Free-text fields can contain personal data; they are shown only to the learner and (goal text) in case reports — remind the learner next to the field.
- Don't show `email` on the page by default (screen-sharing in a demo!).
- Keep the page fast: stats are a handful of indexed counts; don't load full evidence lists.
