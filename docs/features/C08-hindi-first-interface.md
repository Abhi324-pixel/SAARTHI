# C08 — Fully Hindi / Hinglish interface

> 🚧 **RED ZONE — Abhinav is building this feature. Do not start it.** If you were told to take it over (or Abhinav is busy and says so), he will name it on the `RED ZONES CLEARED FOR ME:` line of your prompt. You may read this spec; building waits for that line. See [TEAM-SPLIT.md](TEAM-SPLIT.md).

| | |
|---|---|
| Source | Chhatrachhaya — "Hindi-first" tone, Hinglish naming conventions |
| SAARTHI today | **Partial.** The learner's language (`english / hindi / hinglish`) is stored and used by: the voice agent, text-to-speech, explain-back prompts (`prompt_hi`), explanations (LLM re-voicing + `summary_hi`), roadmap "Why this?" lines (`planner.why_text`) and concept names (`name_hi`). But the **interface itself is English**: `store.tsx` `DICT` holds 13 keys (nav labels, a few headlines) and a rough scan finds ~290+ plain-text strings still hard-coded in the pages (Mentors 47, VoiceDrawer 22, Settings 22, Interview 21, Dashboard 19, Genome 19, Login 19, …), plus strings assembled in code and English-only server messages. |
| Priority / size | P2 / L (4–6 days for the UI and server messages; **content translation is a separate human task**) |
| Depends on | nothing; do it **after** other features land (or add new strings as keys from now on — playbook §5f.7). C05 and C07 are designed around translation keys. |
| External accounts | none. Needs a **native Hindi speaker for review**. |

## 1. What the learner gets

If they choose Hindi (Devanagari) or Hinglish (romanised), **every screen, button, error, notification and server-written sentence** appears in that language, with technical terms
(SQL, JOIN, WHERE, API, query) left in English where that is how learners and teachers say them. Switching language in Settings changes the whole app immediately, without reloading.
Where a question or note has no translation yet, it falls back to English and says so.

## 2. How it works in Chhatrachhaya (the source idea)

| What | File and place (repo root = <https://github.com/mrgraciz123/chhatrachhayaa>) |
|---|---|
| Brand voice and a table of Hinglish names for actions (Save post → *Gyaan Bachao*, Connect → *Dost Banao*, Skip → *Aage Badhein*, Sign in → *Andar Aaiye*, …) | `README.md` "Naming Conventions" |
| "All new user-facing text in Hindi or Hinglish" as a contribution rule | `README.md` "Contribution Guidelines" |
| In practice: **strings are hard-coded inline in each component, in romanised Hinglish** (`"Aage Badhein"`, `"Shehar (City) Chuniye"`, `"Maryada Aur Shapath"`) — no i18n library, no catalogue | `src/OnboardingScreen.tsx`, `src/MatchmakingScreen.tsx`, `src/BaatcheetScreen.tsx` |
| **Zero Devanagari characters** in `src/` (a scan finds none), although the README says "Hindi/Devanagari script supported throughout" | whole repo |

So the transferable idea is **tone and vocabulary** (warm, simple, respectful), not code. The structure below is SAARTHI's own.

### Do not copy
- Inline strings per component (impossible to review, test or switch). Use a catalogue.
- Romanised-only "Hindi". SAARTHI offers *both* Devanagari Hindi and Hinglish, because learners differ.
- Names that need explaining (*Gyaan Bachao*). Keep UI words obvious: "Save", "Next".

## 3. What SAARTHI already has

- `language_pref` on the learner, `useApp().lang` and `t(key)` in `store.tsx` (falls back to English when a key or language is missing); `DICT` has 13 keys.
- `frontend/index.html` already loads **Noto Sans Devanagari**, and `--font-sans` includes it (`src/index.css`).
- Server pieces already bilingual: `planner.why_text(item, lang)` (Hinglish lines), `Concept.name_hi`, `rubrics[...]["prompt_hi"]`, `notes[...]["summary_hi"]`, `tasks.LANG_NAMES`, TTS/STT language mapping (`voice/elevenlabs.py` `LANG_CODES`), the voice agent's language dynamic variable.
- Pages already show `Namaste` greetings when the language is not English (`Dashboard.tsx`).

## 4. How to adapt it

### 4.1 Catalogue and `t()` (frontend)
- `frontend/src/i18n/en.json`, `hi.json`, `hinglish.json` — flat keys, dotted by screen: `dashboard.welcome`, `mentors.case.accept`, `notif.case_accepted`. Interpolation `{name}`; a tiny plural helper (`{count, one|other}`) only where needed (Hindi plural rules are simple: 0 and 1 are singular).
- Rewrite `store.tsx`'s `t(key, params?)` to read these files (keep the current signature working so existing calls don't break). Fallback chain `selected → english`; in dev, a missing key logs a warning and shows the key; in prod show English.
- Set `document.documentElement.lang` to `hi` / `en` (Hinglish is English-script, use `hi-Latn`) when the language changes — it fixes screen-reader pronunciation and font selection.
- A custom 40-line `t()` is enough; `react-i18next` is an acceptable alternative if the team prefers a library. Either way keep keys in JSON so non-programmers can review.

### 4.2 Extraction order (one push per group)
1. Login, Onboarding, Placement/Quiz, Dashboard 2. Learn, Practice (SQL workbench), Reviews 3. Roadmap, Genome 4. Mentors, Settings, Interview, Teacher 5. VoiceDrawer, StuckModal, ExplainBack, errors/toasts.
Rule for every push: **no new hard-coded English in touched files**; strings built from pieces ("You have " + n + " reviews") become one key with parameters (word order differs in Hindi).

### 4.3 Quality gate — `frontend/scripts/check-i18n.mjs` + `npm run check:i18n`
Fails when: a key exists in `en` but not in `hi`/`hinglish` (unless the value is the explicit marker `"@todo"`); a key is unused (search the source); placeholders differ between languages; a value contains raw HTML. Wire it into the PR checklist.

### 4.4 Server-written prose → codes + translations
English sentences produced by the API (e.g. `planner.change_text`, `planner.why_not`, `escalation` messages such as "I'm glad you told us…", consent messages, `_calibration_note`, the "grading model is not reachable" notice) cannot be translated by the browser.
- Add `backend/app/i18n.py` with `msg(code, lang, **params)` backed by `backend/app/content/messages.json` (`{code: {en, hi, hinglish}}`).
- Convert the learner-visible messages **progressively**: return both `code` and rendered `message`; the front end prefers `code` rendering when it has the key.
- Test: every code has all three languages and the same placeholders; unit test each converted function with `lang` in {english, hindi, hinglish}.
- Safety messages (wellbeing/helpline text) must be translated and **reviewed first**; the helpline number stays unchanged (14416).

### 4.5 Curated content
Questions (63 MCQs), SQL task statements, misconception descriptions, rubrics and notes need `*_hi` fields where missing. Pattern: optional `stem_hi`, `description_hi`, … with fallback to English; extend `content.py` `validate()` to print **coverage per language** and `scripts/export_review_sheet.py` to list untranslated items. AI-drafted translations are allowed **only** with a visible "translation: draft" chip until a person signs off (same honesty rule as the curriculum, `docs/CONTENT_REVIEW.md`). Do not translate code, SQL keywords, table/column names.

### 4.6 Glossary and style (`docs/features/C08-glossary.md`, create with the first push)
Agree and write down: SQL/JOIN/WHERE/API/query/table/row/column stay English; "misconception" → *galat dharna* / गलत धारणा (already used in `planner.why_text`); "roadmap" stays Roadmap; "teach it back" → *Samjhakar batayein* / समझाकर बताइए (already in `DICT`); formal-but-friendly "aap" form throughout; Latin digits; date format `DD Mon YYYY`.

### 4.7 Layout and fonts
Hindi strings run 20–40 % longer: no fixed-width buttons, allow wrapping, test at 360 px. Keep Noto Sans Devanagari at ≥ 14 px body size (conjuncts get unreadable below). The skill-graph node labels (`SkillGraph.tsx` l.72) are cut at 24 characters and always use the English `n.name` although `/api/graph` already returns `name_hi`; its `aria-label` (l.68) is built from English words too ("percent") — fix both.

### 4.8 Voice
No new work: the agent and TTS already follow `language_pref`; verify the agent prompt in the ElevenLabs dashboard speaks Devanagari Hindi vs Hinglish consistently (`docs/ELEVENLABS_SETUP.md`).

## 5. Files to create / touch
`frontend/src/i18n/{en,hi,hinglish}.json` (new), `frontend/scripts/check-i18n.mjs` (new), `frontend/package.json` (script), `store.tsx` (`t`), every page/component in the extraction order,
`backend/app/i18n.py` + `content/messages.json` (new), the server functions listed in 4.4, `content/*.json` (`*_hi` fields), `content.py`, `scripts/export_review_sheet.py`, `docs/features/C08-glossary.md` (new),
tests `test_i18n.py`.

## 6. Tests (minimum)
1. `npm run check:i18n` passes (no missing/unused keys, placeholders match).
2. Backend: every message code has `en`, `hi`, `hinglish` with identical placeholder sets; converted functions return the right language for each `lang`.
3. A unit test that `t()` falls back to English for a missing key and never throws.
4. Snapshot-style manual checklist in the hand-off note: each converted screen visited in all three languages at 360 px and desktop; no overflow, no `undefined`/key text visible.
5. Content validation prints coverage (e.g. `hi: 41/63 questions`) and does not fail on missing optional translations.

## 7. Done when
- [ ] Switching language in Settings changes all visible text on every page, including toasts, errors and notifications.
- [ ] Server-written messages are localised through codes; safety messages are reviewed by a native speaker.
- [ ] Untranslated curated items fall back to English and are labelled; translation status is visible in `docs/CONTENT_REVIEW.md`.
- [ ] A native Hindi speaker has reviewed `hi.json`/`hinglish.json` (name recorded in the file's `_meta`).

## 8. Risks and traps
- Machine translation of educational and **safeguarding** text can be wrong in subtle ways; review before showing it to real minors.
- Don't translate user input or LLM output labels that the code compares against (ids, enums) — translate only display strings.
- Hinglish has no standard spelling; pick one spelling per word in the glossary and stick to it.
- Date/number formatting differences (`toLocaleDateString`) can break layout; keep formats centralised.
