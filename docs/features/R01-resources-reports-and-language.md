# R01 / I18N: real web resources, model-written challenges, interview report, class view, full-language interface (3 Oct 2026)

## 1. Real web resources (Tavily)
- **Where:** Learn page ("Learn from real sources") and the map's node details. API: `GET /api/resources/{concept_id}`.
- **How:** `engines/resources.py` searches Tavily with the concept name only (never anything about the learner), keeps only https pages on well-known learning sites (official docs first, then articles, then YouTube), and caches the result for 14 days (`web_resource_cache`). A page view never waits on a search. No key or a failed search shows "not reachable" and nothing invented.
- **Setup:** `TAVILY_API_KEY` in `backend/.env` (never commit it). Fill the cache once with `python scripts/prewarm_resources.py` (about 62 searches: 31 concepts in English and Hindi).
- Labelled on screen: found on the web with Tavily, not reviewed by SAARTHI.

## 2. Model-written practical challenges
`engines/challenge_generator.py`: curated challenges stay (their SQL now runs on the real practice database; a test proves it). For every other concept Gemini writes a concept-specific challenge from the lesson notes, validated by code (3+ concrete requirements, weighted criteria, no links) with a plain honest fallback if the model is down. The challenge is stored once for everyone; a learner's own misconception focus is added to the copy they see and never saved.

## 3. Interview report and the plan that follows it
Resume-based interviews (typed and video): overview counts, a short written summary (checked by code: it may not add a number or a link that is not in the facts), measured browser stats, per-answer feedback with word-for-word quotes, "Next steps", and Save as PDF. Each real technical gap is tagged by the model with a curriculum concept id (invalid ids are dropped). "Move these topics up my plan" adds an `INTERVIEW_FOCUS` boost for 30 days while the gap exists. It changes the plan, never the skill estimate (no evidence is created).

## 4. Class view without a made-up class
`/teacher` is now "Class view": opt-in, anonymous, real learners only, and nothing about the group is shown until **5** have joined. Learners are shown only as pseudonyms. `SAARTHI_COHORT=mock` (the old made-up class) exists only for tests and explicit development. People (mentors, mock sign-in) remain clearly labelled demo; nothing about people is generated.

## 5. Whole interface in Hindi or Hinglish
`frontend/src/lib/autoTranslate.ts` + `POST /api/i18n/translate`. The page's visible text and labels are translated in place and restored on English.
- The server translates with Gemini in small batches and checks every result (same numbers, Devanagari for Hindi, Roman letters for Hinglish, not copied back unchanged, sensible length), retries strings the model slipped on, and caches **permanently for everyone** (`ui_translations`). Nothing is stored that looks like personal data.
- Never translated: code, SQL keywords (INNER JOIN), names, text in “curly quotes” (the learner's own words), chat messages, interview answers, SQL result tables, text boxes, language names.
- All-caps headings are sent in normal case and shown in capitals again.
- **First view of a page takes about 20-40 seconds to finish translating**; after that it is instant for everyone. Visit the pages once in each language before a demo to warm the cache.
- It is machine translation: good for the interface, not reviewed by a human. Mentor bios and curated lesson text that mix in code can stay partly English.

## Not verified
Hindi and Hinglish read well on the pages checked (dashboard, roadmap, learn, interview, practice, genome, mentors, class view, settings, profile), but not every state of every page. The spoken ElevenLabs agent was not tested in these languages. Tavily result quality varies by topic. The class view shows an empty state until 5 real learners opt in.
