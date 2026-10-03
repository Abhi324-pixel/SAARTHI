# Demo & submission guide (3 Oct finale · ElevenLabs track on Craftora)

The track asks for: **a working app that uses ElevenLabs in a live demo**, a **clear demonstration of how ElevenLabs is used**,
submission through the **Craftora portal** and a **short demo video**. Judged on innovation & creativity · use of ElevenLabs technology ·
technical implementation · real-world impact · overall UX.

## Before you go on stage (10 minutes)
1. `python backend/scripts/check_env.py` → everything green (Gemini, ElevenLabs key, agent, voice).
2. Redeem the Creator coupon (Discord `#coupon-codes`) so you do not run out of credits.
3. Start with `run-dev.bat` (or `build-and-serve.bat` for the single-port build). Open the app in Chrome, allow the microphone.
4. Sign in as **Priya Sharma**, age 20, Hinglish → onboarding → *Settings → Demo tools → Load a demo starting history*.
   (This gives a believable starting state, labelled `simulated`. Say so if asked.)
5. Do one dry run of the voice conversation so the browser has already granted mic access and the agent is warm.
6. `SAARTHI_LLM_MODE` must be `gemini` — there must be **no red TEST LLM banner**.

## The 5-minute story
*"Most learning apps tell you your score. SAARTHI tells you what you have wrong — and changes your plan around it."*

| Time | You do | They see | Judges' criterion |
|---|---|---|---|
| 0:00 | Dashboard: point at the skill graph and "Aaj ka mission" | A learner model, not a course list. Every concept coloured by evidence | Innovation |
| 0:30 | Click **🎙 Talk to SAARTHI** → *Teach it back* → concept *LEFT and other outer joins* → **Start talking** | The ElevenLabs agent greets Priya **in Hinglish by name**; "Under the hood" panel lights up | Use of ElevenLabs |
| 0:50 | Say (confidently): *"Left join basically sirf matching rows return karta hai, jaise inner join."* | Agent calls `record_response` (visible in the tool log) → asks to confirm: *"You said …, is that right?"* | Tech implementation |
| 1:30 | Say *"Haan, sahi hai."* | `confirm_statement` → misconception **confirmed**; the **join diagram** appears; agent explains with contrasting cases | Innovation / UX |
| 2:10 | Click **End**. Open **Practice SQL** → LEFT JOIN task. Run an INNER JOIN query → **Check my answer** | Executed query is missing 2 customers → *objective* proof of the same misconception. Confidence 'Certain' → *"You were very sure, but wrong"* calibration note | Real-world impact |
| 3:00 | Click **Load it in the editor** (counter-example), fix the query → Check | ✓ correct; misconception moves to *correcting*; mastery number moves with evidence | Tech implementation |
| 3:30 | Open **Roadmap** | Banner *"Your roadmap just changed"*: LEFT JOIN item now starts with a targeted fix, ordered after INNER JOIN / NULL; every row has **Why this?** | Innovation / UX |
| 4:00 | **Settings → Demo tools → Simulate persistent struggle**, then **Chhatrachhaya** → open the suggested case | Routed to a Skill Mentor (a Margdarshak for career topics), matched with visible reasons, full case report — flagged *demo mentor* | Real-world impact |
| 4:40 | Switch language to हिन्दी in Settings; click **🔊 Read aloud** on a concept | Read-aloud via ElevenLabs Text-to-Speech | Use of ElevenLabs |
| 4:55 | Close: *"Voice by ElevenLabs, judgement by evidence. The agent can't change your mastery — only proof can."* | | |

**Say out loud what is mock** (builds trust): mentors and their verification, guardian consent and the teacher cohort are demo data and badged as such;
everything else — Gemini, ElevenLabs, the evidence engine, SQL execution — is live.

## If something breaks
- **Voice fails / no network** → click *Close* and use *Learn → Teach it back* (typed). Same engine, same scoring. Say: "text mode is the built-in fallback".
- **Gemini is slow** → the fallback model list (`SAARTHI_MODEL_FALLBACKS`) takes over automatically; explanations are cached on disk after the first run, so rehearse once.
- **Agent says something odd** → it only speaks; scores come from the tools. Point at the tool log.
- Keep the **backup video** ready in a tab.

## Demo video (required by the track) — 90 seconds
1. (0–10 s) Title card + one-line problem: "Learners don't know *why* they're stuck."
2. (10–40 s) Voice teach-back with the agent (screen + audio, show the tool log). Highlight the read-back and the join diagram.
3. (40–60 s) SQL check detects the same misconception from the executed query; calibration note.
4. (60–75 s) Roadmap changing live with "Why this?".
5. (75–90 s) Mentor case with the generated report; end card: "Voice by ElevenLabs · Gemini · evidence-based".
Record at 1080p, mic on, close other tabs/notifications. Upload as the portal requires and submit through **Craftora**.

## Optional: ElevenLabs showcase (swag)
Fork the showcase repo, add a project MDX file from their template (name, description, links, demo video), open a pull request, and fill the form from the Hacker Guide.

## Honest limits to mention if asked
- Curriculum content (concept graph, questions, misconceptions) is AI-drafted and pending expert review; the SQL tasks are verified by executing them.
- Mentor verification, guardian consent and the cohort view are mocked; real safeguarding (ID checks, legal review) is required before real minors use it.
- Effectiveness is not claimed: the plan is a randomised comparison of adaptive vs fixed order with delayed tests (see report §Success Metrics).
