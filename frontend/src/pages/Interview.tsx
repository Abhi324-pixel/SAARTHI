import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { apiV01, type InterviewReport as ResumeReport, type InterviewStart, type ResumeSummary } from '../api_ext/V01'
import InterviewReport from '../components/video/InterviewReport'
import ResumeCard from '../components/video/ResumeCard'
import TextResumeInterview from '../components/video/TextResumeInterview'
import { MicButton, SpeakButton } from '../components/audio'
import { SpeechChips } from '../components/SpeechChips'
import { SpeechMetrics, TIP_LABELS } from '../api_ext/T11'
import { fetchInterviewHistory, fetchInterviewPacks, InterviewHistoryItem, InterviewPack } from '../api_ext/T08'
import { Bar, Callout, ConfidencePicker, FlagChip, LevelChip, SectionTitle } from '../components/ui'
import { useApp } from '../store'

export default function Interview() {
  const { toast, bump, setRoadmapNote, openVoice } = useApp()
  const [session, setSession] = useState<any | null>(null)
  const [log, setLog] = useState<{ who: 'ai' | 'you'; text: string; speech?: SpeechMetrics | null }[]>([])
  const [text, setText] = useState('')
  const [conf, setConf] = useState<number | null>(null)
  const [speech, setSpeech] = useState<SpeechMetrics | null>(null)
  const [busy, setBusy] = useState(false)
  const [idx, setIdx] = useState(0)
  const [readback, setReadback] = useState<any | null>(null)
  const [report, setReport] = useState<any | null>(null)
  const [checklist, setChecklist] = useState<any[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const [round, setRound] = useState<'technical' | 'behavioural' | 'full'>('technical')
  const [selectedPackId, setSelectedPackId] = useState<string>('')
  const [packs, setPacks] = useState<InterviewPack[]>([])
  const [history, setHistory] = useState<InterviewHistoryItem[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const nav = useNavigate()
  const [mode, setMode] = useState<'typed' | 'voice' | 'video'>('typed')
  const [resume, setResume] = useState<ResumeSummary | null>(null)
  const [useResume, setUseResume] = useState(true)
  const [resumeStart, setResumeStart] = useState<InterviewStart | null>(null)
  const [resumeReport, setResumeReport] = useState<{ r: ResumeReport; speech: any[] } | null>(null)
  const withResume = useResume && !!resume

  useEffect(() => {
    fetchInterviewPacks().then(setPacks).catch(() => {})
  }, [])

  async function loadHistory() {
    try {
      const h = await fetchInterviewHistory()
      setHistory(h)
      setShowHistory(true)
    } catch (e: any) {
      toast(e.message, 'err')
    }
  }

  async function startFromResume() {
    setBusy(true)
    try { setResumeStart(await apiV01.start(true)) } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  async function start() {
    if (withResume) { await startFromResume(); return }
    setBusy(true)
    try {
      const nTopics = selectedPackId ? 4 : round === 'behavioural' ? 3 : round === 'full' ? 5 : 4
      const s = await api.interviewStart(nTopics, 'text', round, selectedPackId || undefined)
      setSession(s)
      setLog([{ who: 'ai', text: s.question }])
      setIdx(0)
      setReport(null)
      setSpeech(null)
    } catch (e: any) {
      toast(e.message, 'err')
    } finally {
      setBusy(false)
    }
  }

  async function send() {
    if (!text.trim()) return
    setBusy(true)
    setNotice(null)
    const mine = text
    const curSpeech = speech
    try {
      const r = await api.interviewAnswer({
        session_id: session.session_id,
        text: mine,
        stated_confidence: conf,
        channel: curSpeech ? 'audio' : 'text',
        audio_seconds: curSpeech?.speaking_seconds,
        speech: curSpeech ?? undefined,
      })
      if (r.unavailable || r.insufficient) {
        setNotice(r.message)
        return
      }
      setLog(l => [
        ...l,
        { who: 'you', text: mine, speech: curSpeech },
        ...(r.followup ? [{ who: 'ai' as const, text: r.followup }] : []),
        ...(r.next_question ? [{ who: 'ai' as const, text: r.next_question }] : []),
      ])
      setText('')
      setSpeech(null)
      setChecklist(r.checklist ?? [])
      if (r.index !== undefined) setIdx(r.index)
      if (r.readback) setReadback(r.readback)
      if (r.done && r.report) {
        setReport(r.report)
        bump()
      }
      if (r.after?.roadmap?.changed) setRoadmapNote(r.after.roadmap.change_reason)
      setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth' }), 100)
    } catch (e: any) {
      toast(e.message, 'err')
    } finally {
      setBusy(false)
    }
  }

  if (resumeReport) return <InterviewReport r={resumeReport.r} speech={resumeReport.speech} onAgain={() => { setResumeReport(null); setResumeStart(null) }} />
  if (resumeStart) return <TextResumeInterview interview={resumeStart} onDone={(r, speech) => { setResumeReport({ r, speech }); bump() }} />

  if (!session) {
    const activePack = packs.find(p => p.id === selectedPackId)
    const modeBtn = (id: 'typed' | 'voice' | 'video', icon: string, title: string, sub: string) => (
      <button type="button" role="radio" aria-checked={mode === id} onClick={() => setMode(id)}
        className={`text-left rounded-2xl border p-4 transition ${mode === id ? 'border-navy bg-navy text-white shadow' : 'border-line bg-white hover:bg-paper'}`}>
        <div className="text-xl">{icon}</div><div className="font-extrabold mt-1">{title}</div><div className={`text-xs mt-0.5 ${mode === id ? 'text-white/80' : 'text-muted'}`}>{sub}</div>
      </button>
    )
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div>
          <div className="eyebrow">Mock interview</div>
          <h1 className="h-page">Practise explaining — like a real interview</h1>
          <p className="text-muted mt-1">Step 1: add your resume if you like (optional). Step 2: choose how you want to be interviewed.</p>
        </div>

        <ResumeCard onChange={r => { setResume(r); setUseResume(r !== null) }} />
        {resume && <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={useResume} onChange={e => setUseResume(e.target.checked)} /> Ask me questions from my resume (typed, voice or video)</label>}

        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-muted mb-1.5">Choose how to interview</div>
          <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Interview type">
            {modeBtn('typed', '⌨️', 'Typed', 'Type your answers (or dictate with the mic) and read the questions.')}
            {modeBtn('voice', '🎙', 'Voice with the agent', 'Talk with the ElevenLabs interviewer, hands-free.')}
            {modeBtn('video', '🎥', 'Video', 'Camera and microphone required. Recorded to your own device.')}
          </div>
        </div>

        {mode === 'typed' && (
        <div className="card p-6 space-y-4">
          {withResume ? (
            <>
              <p className="text-sm text-muted">Five questions written from your resume and your answers. After each answer you get feedback that quotes your own words. This is practice coaching: it does not change your skill estimates.</p>
              <button className="btn btn-saffron py-3 px-6" onClick={start} disabled={busy}>{busy ? 'Preparing…' : 'Start the typed interview (from my resume)'}</button>
              <p className="text-xs text-muted">To use the round types and placement packs instead, untick "Ask me questions from my resume" above.</p>
            </>
          ) : (
            <>
          <div>
            <label className="text-xs font-bold uppercase tracking-wider text-muted block mb-1.5">Interview Round</label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                className={`py-2 px-3 rounded-xl border text-sm font-semibold transition ${round === 'technical' ? 'bg-navy text-white border-navy' : 'bg-paper border-line text-navy hover:bg-white'}`}
                onClick={() => setRound('technical')}
              >
                Technical
              </button>
              <button
                type="button"
                className={`py-2 px-3 rounded-xl border text-sm font-semibold transition ${round === 'behavioural' ? 'bg-navy text-white border-navy' : 'bg-paper border-line text-navy hover:bg-white'}`}
                onClick={() => setRound('behavioural')}
              >
                HR & Behavioural
              </button>
              <button
                type="button"
                className={`py-2 px-3 rounded-xl border text-sm font-semibold transition ${round === 'full' ? 'bg-navy text-white border-navy' : 'bg-paper border-line text-navy hover:bg-white'}`}
                onClick={() => setRound('full')}
              >
                Full Mock (Both)
              </button>
            </div>
            <p className="text-xs text-muted mt-1.5">
              {round === 'technical' && 'Evaluates system design, queries, and core concepts with verified code explanations.'}
              {round === 'behavioural' && 'Starts with 90s self-introduction, then probes STAR behavioural stories and project walkthrough.'}
              {round === 'full' && 'Comprehensive interview starting with self-intro, then situational questions, and deep technical topics.'}
            </p>
          </div>

          <div>
            <label className="text-xs font-bold uppercase tracking-wider text-muted block mb-1.5">Placement & Role Pack (Optional)</label>
            <div className="flex gap-2 flex-wrap">
              <button
                type="button"
                className={`py-1.5 px-3 rounded-xl border text-xs font-semibold ${selectedPackId === '' ? 'bg-teal text-white border-teal' : 'bg-paper border-line hover:bg-white'}`}
                onClick={() => setSelectedPackId('')}
              >
                Standard (Adaptive)
              </button>
              {packs.map(p => (
                <button
                  key={p.id}
                  type="button"
                  className={`py-1.5 px-3 rounded-xl border text-xs font-semibold ${selectedPackId === p.id ? 'bg-teal text-white border-teal' : 'bg-paper border-line hover:bg-white'}`}
                  onClick={() => setSelectedPackId(p.id)}
                >
                  {p.title}
                </button>
              ))}
            </div>
            {activePack && (
              <div className="mt-2 p-3 bg-paper rounded-xl border border-line text-xs space-y-1">
                <div className="font-bold text-navy">{activePack.title} ({activePack.target_company_type})</div>
                <div className="text-muted">{activePack.description}</div>
                <div className="text-[11px] text-muted italic">Duration: ~{activePack.duration_minutes}m · Source: {activePack.source}</div>
              </div>
            )}
          </div>

          <ul className="text-sm space-y-1.5 list-disc pl-5 text-muted">
            <li>No hints or feedback during the interview — full audit report comes at the end.</li>
            <li>Behavioural answers scored with STAR checklists; own actions validated with verbatim quotes.</li>
            <li>No made-up percentiles: see exactly what you proved and what you missed.</li>
          </ul>

              <div className="flex gap-2 flex-wrap pt-2">
                <button className="btn btn-saffron py-3 px-6" onClick={start} disabled={busy}>
                  {busy ? 'Preparing…' : 'Start the typed interview'}
                </button>
                <button className="btn btn-ghost py-3 ml-auto text-xs" onClick={loadHistory}>
                  📜 Past interview history
                </button>
              </div>
            </>
          )}
        </div>)}

        {mode === 'voice' && (
        <div className="card p-6 space-y-3">
          <p className="text-sm text-muted">A spoken interview with the ElevenLabs voice agent. {withResume ? 'The questions are written from your resume, and the agent is told only a short summary of it (skills and project names). Your written feedback appears in your interview list afterwards.' : 'It uses the standard interview topics for your target role, with the same scoring and quotes as the typed interview.'}</p>
          <button className="btn btn-saffron py-3 px-6" onClick={() => openVoice('interview', undefined, { useResume: withResume })}>🎙 Start the voice interview</button>
        </div>)}

        {mode === 'video' && (
        <div className="card p-6 space-y-3">
          <p className="text-sm text-muted">Like a real video call: the camera and microphone are required and checked first (face, distance, head angle, lighting, voice level). {withResume ? 'Questions come from your resume.' : 'Questions are general interview questions.'} The video and voice are recorded to this device only, never uploaded, and kept until you delete them.</p>
          <button className="btn btn-saffron py-3 px-6" onClick={() => nav('/video-interview', { state: { fromInterview: true, useResume: withResume } })}>🎥 Set up camera and start</button>
          <div><Link to="/video-interview" className="text-xs underline text-muted">My interview recordings</Link></div>
        </div>)}

        {(mode !== 'typed' || withResume) && <button className="btn btn-ghost btn-sm text-xs" onClick={loadHistory}>📜 Past interview history</button>}

        {showHistory && (
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <SectionTitle eyebrow="Audit log" title="Your past mock interviews" />
              <button className="text-xs text-muted font-bold hover:underline" onClick={() => setShowHistory(false)}>Close</button>
            </div>
            {history.length === 0 ? (
              <p className="text-xs text-muted">No completed interviews yet.</p>
            ) : (
              <div className="divide-y divide-line">
                {history.map(h => (
                  <div key={h.session_id} className="py-2.5 flex items-center justify-between text-xs">
                    <div>
                      <span className="font-bold text-navy capitalize">{h.round} round</span>
                      {h.pack_id && <span className="chip ml-2 bg-paper">{h.pack_id.replace(/_/g, ' ')}</span>}
                      <span className="text-muted ml-2">{h.created_at ? new Date(h.created_at).toLocaleDateString() : ''}</span>
                    </div>
                    <div className="font-semibold">
                      {h.checklist_items_covered} / {h.checklist_items_total} points covered
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  if (report) {
    const isBehaviouralTopic = (t: any) => t.kind === 'behavioural' || t.concept_id.startsWith('comm_')
    const behTopics = report.topics.filter(isBehaviouralTopic)
    const techTopics = report.topics.filter((t: any) => !isBehaviouralTopic(t))

    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <div>
          <div className="eyebrow">Interview report · {report.round?.toUpperCase()} ROUND</div>
          <h1 className="h-page">{report.role_title} — what you covered</h1>
        </div>

        <div className="card p-5 flex items-center gap-6 flex-wrap">
          <div>
            <div className="text-4xl font-extrabold text-navy">
              {report.checklist_items_covered}
              <span className="text-muted text-2xl"> / {report.checklist_items_total}</span>
            </div>
            <div className="text-sm text-muted">key points covered (each backed by your own words)</div>
          </div>
          <div className="text-sm space-y-1">
            <div><b className="text-lvl-proficient">Strong:</b> {report.strengths.join(', ') || 'nothing yet'}</div>
            <div><b className="text-lvl-unknown">Work on:</b> {report.needs_work.join(', ') || 'nothing major'}</div>
          </div>
        </div>

        {report.behavioural_summary && (
          <div className="card p-4 bg-[#fbfbfe] border border-[#d9dcf7] space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-violet">STAR Behavioural Assessment</span>
              <span className="text-xs font-semibold text-navy">
                {report.behavioural_summary.items_covered} / {report.behavioural_summary.items_total} STAR points verified
              </span>
            </div>
            <p className="text-xs text-muted">
              Evaluated across {report.behavioural_summary.topics_assessed} behavioural question{report.behavioural_summary.topics_assessed === 1 ? '' : 's'}. Actions were credited only when personal ownership ("I") was articulated with verifiable evidence.
            </p>
          </div>
        )}

        {behTopics.length > 0 && (
          <div className="space-y-3">
            <SectionTitle eyebrow="Communication" title="HR & Behavioural questions" />
            {behTopics.map((t: any) => (
              <div key={t.concept_id} className="card p-5">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link to={'/learn/' + t.concept_id} className="font-extrabold text-navy hover:underline">{t.name}</Link>
                  <span className="chip" style={{ background: '#ede7f6', color: '#512da8' }}>STAR Rubric</span>
                  <LevelChip level={t.level_after} />
                  {t.misconceptions.length > 0 && <FlagChip flag="misconception" />}
                  <span className="text-sm text-muted ml-auto">{Math.round(t.score * 100)}% · estimate {Math.round(t.p_before * 100)}% → {Math.round(t.p_after * 100)}%</span>
                </div>
                <Bar value={t.score} />
                <div className="grid md:grid-cols-2 gap-3 mt-3">
                  <div className="rounded-xl bg-[#e8f6ee] p-3 text-sm">
                    <b className="text-lvl-proficient">Covered</b>
                    <ul className="mt-1 space-y-0.5">
                      {t.covered.map((c: any) => <li key={c.id}>✓ {c.text}{c.evidence && <i className="text-muted"> — “{c.evidence}”</i>}</li>)}
                      {!t.covered.length && <li className="text-muted">Nothing verifiable.</li>}
                    </ul>
                  </div>
                  <div className="rounded-xl bg-saffron-soft p-3 text-sm">
                    <b className="text-saffron">Missed</b>
                    <ul className="mt-1 space-y-0.5">
                      {t.missed.map((c: any) => <li key={c.id}>○ {c.text}</li>)}
                      {!t.missed.length && <li className="text-muted">Nothing — great.</li>}
                    </ul>
                  </div>
                </div>
                <details className="mt-2 text-sm"><summary className="cursor-pointer font-bold text-teal">Model answer</summary><p className="mt-1 bg-paper rounded-xl p-3">{t.model_answer}</p></details>
              </div>
            ))}
          </div>
        )}

        {techTopics.length > 0 && (
          <div className="space-y-3">
            <SectionTitle eyebrow="Engineering" title="Technical questions" />
            {techTopics.map((t: any) => (
              <div key={t.concept_id} className="card p-5">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link to={'/learn/' + t.concept_id} className="font-extrabold text-navy hover:underline">{t.name}</Link>
                  <LevelChip level={t.level_after} />
                  {t.misconceptions.length > 0 && <FlagChip flag="misconception" />}
                  <span className="text-sm text-muted ml-auto">{Math.round(t.score * 100)}% · estimate {Math.round(t.p_before * 100)}% → {Math.round(t.p_after * 100)}%</span>
                </div>
                <Bar value={t.score} />
                <div className="grid md:grid-cols-2 gap-3 mt-3">
                  <div className="rounded-xl bg-[#e8f6ee] p-3 text-sm">
                    <b className="text-lvl-proficient">Covered</b>
                    <ul className="mt-1 space-y-0.5">
                      {t.covered.map((c: any) => <li key={c.id}>✓ {c.text}{c.evidence && <i className="text-muted"> — “{c.evidence}”</i>}</li>)}
                      {!t.covered.length && <li className="text-muted">Nothing verifiable.</li>}
                    </ul>
                  </div>
                  <div className="rounded-xl bg-saffron-soft p-3 text-sm">
                    <b className="text-saffron">Missed</b>
                    <ul className="mt-1 space-y-0.5">
                      {t.missed.map((c: any) => <li key={c.id}>○ {c.text}</li>)}
                      {!t.missed.length && <li className="text-muted">Nothing — great.</li>}
                    </ul>
                  </div>
                </div>
                <details className="mt-2 text-sm"><summary className="cursor-pointer font-bold text-teal">Model answer</summary><p className="mt-1 bg-paper rounded-xl p-3">{t.model_answer}</p></details>
              </div>
            ))}
          </div>
        )}

        {report.speech && (
          <div className="card p-5 space-y-3">
            <SectionTitle eyebrow="Voice & delivery" title="How you sounded" />
            <p className="text-xs text-muted">
              Measured across {report.speech.answers_with_audio} spoken answer{report.speech.answers_with_audio === 1 ? '' : 's'}. This is supportive feedback, not an interview score.
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              {report.speech.median_wpm !== null && (
                <div className="rounded-xl border border-line p-3 bg-paper">
                  <div className="text-xs text-muted font-bold">Speaking pace</div>
                  <div className="text-xl font-extrabold text-navy mt-0.5">{report.speech.median_wpm} <span className="text-xs font-normal text-muted">WPM median</span></div>
                </div>
              )}
              {report.speech.top_markers?.length > 0 && (
                <div className="rounded-xl border border-line p-3 bg-paper">
                  <div className="text-xs text-muted font-bold">Top filler markers</div>
                  <div className="flex gap-1 flex-wrap mt-1">
                    {report.speech.top_markers.map((m: any) => (
                      <span key={m.marker} className="chip" style={{ background: '#fdf3e9', color: '#9a4f0a' }}>
                        “{m.marker}” ×{m.count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {report.speech.tips?.length > 0 && (
              <div className="text-xs text-muted">
                <b>Tip:</b> {TIP_LABELS[report.speech.tips[0]]?.desc || 'Natural delivery with clear pauses.'}
              </div>
            )}
          </div>
        )}

        <Callout tone="navy" title="What happens next">
          {report.next_steps.join(' · ') || 'Great round.'} Your roadmap has already been updated with these results — <Link className="underline font-bold" to="/roadmap">see what changed</Link>.
        </Callout>
        <div className="flex gap-2">
          <button className="btn btn-saffron" onClick={() => { setSession(null); setReport(null) }}>Another round</button>
          <Link className="btn btn-ghost" to="/">Dashboard</Link>
        </div>
      </div>
    )
  }

  const isCurrentBehavioural = session.concept_id?.startsWith('comm_')

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="eyebrow flex items-center gap-2">
            <span>Mock interview · topic {idx + 1} of {session.total}</span>
            {isCurrentBehavioural && <span className="chip bg-violet text-white text-[10px]">STAR Behavioural</span>}
          </div>
          <h1 className="h-page">{session.role_title}</h1>
        </div>
        <SpeakButton text={[...log].reverse().find(l => l.who === 'ai')?.text ?? ''} label="Hear the question" />
      </div>

      {isCurrentBehavioural && (
        <div className="p-2.5 rounded-xl bg-violet/10 border border-violet/20 text-xs text-violet font-semibold flex items-center gap-2">
          <span>★</span>
          <span>STAR Method: Situation → Task → Action (what YOU did, using "I") → Result → Reflection</span>
        </div>
      )}

      <Bar value={idx / session.total} h={6} />
      <div className="card p-4 space-y-2.5 min-h-[260px]" aria-live="polite">
        {log.map((l, i) => (
          <div key={i} className={`max-w-[92%] ${l.who === 'ai' ? '' : 'ml-auto'}`}>
            <div translate={l.who === 'you' ? 'no' : undefined} className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${l.who === 'ai' ? 'bg-teal-soft rounded-tl-sm' : 'bg-navy text-white rounded-tr-sm'}`}>
              {l.who === 'ai' && <b className="block text-[11px] text-teal uppercase tracking-wide">Interviewer</b>}
              {l.text}
            </div>
            {l.who === 'you' && l.speech && <SpeechChips speech={l.speech} />}
          </div>
        ))}
        <div ref={end} />
      </div>

      {readback && (
        <Callout tone="violet" title="Quick check — did I hear that right?">
          You said <b>“{readback.statement}”</b>. Is that what you meant?
          <div className="mt-2 flex gap-2">
            <button className="btn btn-primary btn-sm" onClick={async () => { await api.confirmMis(readback.instance_id, true); setReadback(null) }}>Yes</button>
            <button className="btn btn-ghost btn-sm" onClick={async () => { await api.confirmMis(readback.instance_id, false); setReadback(null) }}>No, I misspoke</button>
          </div>
        </Callout>
      )}

      {notice && <Callout tone="saffron" title="Heads up">{notice}</Callout>}

      <div className="card p-4 space-y-2.5">
        <textarea
          className="input min-h-[110px]"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={isCurrentBehavioural ? "Answer using STAR (Situation, Task, your own Action with 'I', Result)..." : "Answer as you would in a real interview…"}
          aria-label="Your answer"
          disabled={busy}
        />
        {speech && <SpeechChips speech={speech} />}
        <div className="flex flex-wrap items-end justify-between gap-3">
          <ConfidencePicker value={conf} onChange={setConf} />
          <div className="flex gap-2">
            <MicButton
              onText={t => setText(p => (p ? p + ' ' : '') + t)}
              onSpeech={s => setSpeech(s)}
              disabled={busy}
            />
            <button className="btn btn-saffron" disabled={busy || !text.trim()} onClick={send}>
              {busy ? 'Scoring…' : 'Answer'}
            </button>
          </div>
        </div>
        {checklist.length > 0 && (
          <div className="text-xs text-muted">
            Points covered so far on this topic: {checklist.filter(c => c.covered).length}/{checklist.length} (shown to you only after the interview ends)
          </div>
        )}
      </div>
    </div>
  )
}
