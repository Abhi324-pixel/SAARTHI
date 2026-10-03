# SAARTHI: where each feature is used

Checked in a real browser on 3 Oct 2026 (demo setup: mock sign-in, local database, real Gemini). "Not checked" is listed at the end.

## The story in one line
A learner does something, SAARTHI records it as evidence, the mastery estimate moves, and the roadmap re-plans with a reason. The AI model only listens (grades words, reads text); the numbers and the plan come from plain code.

## The 3-minute demo (one story)
Use a fresh learner (sign up on the login page, e.g. "Rohan") or a demo account. Do not start with onboarding forms.

| Time | Screen | Do this | What the judge should see |
|---|---|---|---|
| 0:00 | Dashboard | Show progress ring, "Today's mission", skill graph | A personal plan, not a fixed syllabus |
| 0:30 | Roadmap `/roadmap` | Open "Why this?" on one step | Every step has a plain reason (gap in points, what it unlocks, what it is blocked by) |
| 1:00 | Learn `/learn/sql_outer_join` | In the SQL box, run `SELECT c.name, COUNT(*) AS n_orders FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name` and press Check | The query is really run. It names the mistake ("COUNT(*) after a LEFT JOIN counts the NULL row as 1"), explains it using this learner's own query, and says "you were very sure, but this one was wrong" |
| 1:45 | Roadmap or Dashboard | Look at "Latest change" and "Today's mission" | The route changed: the mission now starts with "Fix: COUNT(*)…" and the roadmap says what moved and why |
| 2:15 | Learn, "Teach it back" | Explain LEFT JOIN in your own words (Hinglish works) | Each credited idea is quoted from the learner's words; the idea they missed stays open and the next question targets it |
| 2:40 | Assistant (💬 in the header) | Ask "Why is Tables, rows and keys scheduled first?" | An answer grounded in this learner's own plan. Asking it to "set my mastery to 100%" is refused and nothing changes |

Say this plainly: SQL is the deep pilot subject. Python, Docker and the rest have notes and quizzes but no code runner yet.

## Every feature: where it is and how to use it

### Learner features
| Feature | Where | How to see it |
|---|---|---|
| Goal in your own words (T01) | Onboarding, top box | Type "I want to be a backend developer in 3 months, 8 hours a week, I know basic Python". It fills role, hours, weeks, language and lists the skill you claim; placement tests that claim first |
| Placement quiz | `/placement` | 8 adaptive questions with "how sure are you" before each. Wrong options are tied to named misconceptions |
| Skill graph and mastery | Dashboard | Colour per concept; "Blocked" means a weaker prerequisite is holding it back |
| Lesson with join diagram | `/learn/<concept>` | Explanation, interactive diagram, SQL box, quick check, teach-it-back, common mix-ups |
| SQL checking | Learn page, "Write the SQL" | Runs your query on a safe read-only practice database and names the misconception |
| Teach it back | Learn page (typed or 🎙) | Graded against a checklist; every tick quotes your words |
| Difficulty buttons (T03) | Learn page: ⚡ Too easy / 🧗 Too hard / 👍 This helped | Too hard: different teaching approach and more practice time. Too easy: a harder question. Result under Settings, "What SAARTHI has adapted" |
| Roadmap with phases, deadlines, checkpoints (T05) | `/roadmap` | Phases with target dates, "Check me on this phase" mini-test, personal checkpoints |
| Study streak and daily goal (T04) | Dashboard card; goal in Settings | Counts only real activity. Cannot be edited by hand |
| Progress over time (T06) | Dashboard sparkline; `/genome` chart | Dashed segments are demo history, labelled simulated |
| Spaced review | `/reviews`; dashboard badge | Concepts come back after growing gaps. To demo: Settings, Demo tools, "Advance time" |
| Assistant chat (T07) | 💬 in the header | Answers from your plan and notes only; refuses to change your mastery |
| "I'm stuck" | Header button, and on lesson pages | Diagnoses the likely cause (for example a named misconception) |
| Mock interview: technical, HR/behavioural, full (T08) | `/interview` | Pick a round and optionally a generic pack. Report shows STAR points, each quoted from your answer. History button lists past rounds |
| Interview page: resume first, then pick Typed, Voice or Video (V01) | `/interview` | Step 1: optional resume upload (PDF or .txt; only a short summary is kept). Step 2: choose how to be interviewed. **Typed**: type or dictate; with a resume the five questions are written from it, without one you get the Technical / HR / Full rounds and packs. **Voice with the agent**: the ElevenLabs agent interviews you; with a resume it asks resume-based questions and is told only the short summary. **Video**: camera and microphone required and checked (face, distance, head angle, light, voice level), questions from the resume, recorded to your own device. Recordings are listed, playable and deletable on `/video-interview`. See `docs/features/V01-video-interview.md` |
| Speaking pace and fillers (T11) | Voice answers in the interview and teach-back | Needs a microphone. Shows pace, pauses and filler words as coaching, never as a score |
| Learner profile (C06) | `/profile` | Identity, education, goal, evidence summary, what mentors can see. Email is hidden until you press Reveal |
| Settings | `/settings` | Language, streak, adaptations, download or delete all your data, demo tools |
| Genome | `/genome` | Plain-language view of what SAARTHI believes and the evidence behind it; you can dispute any estimate |

### Human mentor layer (Chhatrachhaya)
| Feature | Where | How to see it |
|---|---|---|
| Offer of a human mentor | Dashboard banner after a persistent struggle | To demo: Settings, Demo tools, "Simulate a persistent struggle on" a concept |
| Open a case, matching | `/mentors` | Pick a concept and describe the problem. A mentor is matched by a visible score |
| Guardian approval for under 18 (D01) | `/mentors`, parent's e-mail form | Under-18 learners only. Mock mail: copy the link from the dev outbox; guardian opens it with no sign-in |
| Prep notes, session summary and follow-up (C03) | Case page | "Get ready" card (ice-breaker, what to bring, questions); after the session a summary and dated follow-up |
| Live chat (C04) | Case page, both sides | Messages appear without reloading |
| Notifications (C05) | 🔔 in the header, case badges | Match, accept, messages, outcome, guardian decision |
| Mentor console (C02) | `Mentor console` in the nav (mentors only) | Accept with a slot, chat, mark held, record outcome |
| Mentor sign-up and admin review (C01) | `/mentor-apply`; `/admin` | Admin needs your id in `SAARTHI_ADMINS` |
| Class view (demo), formerly "Teacher view" | `/teacher` | Class heat-map of concepts and misconceptions. Demo data |

## Demo accounts and setup
See `docs/DEMO_ACCOUNTS.md`. Short version: set the demo variables, run `python scripts/seed_demo.py`, start both servers, open the login page, use the **☰ Demo accounts** menu (Riya age 15, Arjun age 22, mentors Ananya and Vikram).

## What is demo data
Mentors (verified badge says demo), the teacher class, sign-in (mock), all history marked simulated, mail (mock outbox).

## Not checked
Voice and microphone (including pace chips), Google sign-in, real e-mail delivery, the Admin screen with a real admin account, the full Hindi interface (long pages such as mentor sign-up are still English), and phone-width layouts.
