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
import { MessageSquare, Sparkles, Mic, CheckCircle2, AlertCircle, ArrowRight, RotateCcw, LayoutDashboard, HelpCircle } from 'lucide-react'

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
      <button
        type="button"
        role="radio"
        aria-checked={mode === id}
        onClick={() => setMode(id)}
        className={`text-left rounded-2xl border p-4 transition-all duration-200 cursor-pointer ${
          mode === id
            ? 'border-[rgba(255,138,36,0.5)] bg-[rgba(255,138,36,0.18)] text-white shadow-[0_4px_20px_rgba(255,138,36,0.22),inset_0_1px_0_rgba(255,255,255,0.15)]'
            : 'border-[rgba(210,225,235,0.14)] bg-[rgba(16,28,42,0.50)] hover:bg-[rgba(255,255,255,0.06)] hover:border-[rgba(210,225,235,0.25)] text-slate-300'
        }`}
      >
        <div className="text-2xl">{icon}</div>
        <div className="font-extrabold mt-2 text-white heading-glow text-sm sm:text-base">{title}</div>
        <div className={`text-xs mt-1 leading-relaxed ${mode === id ? 'text-slate-100' : 'text-[var(--text-muted)]'}`}>{sub}</div>
      </button>
    )
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="glass-panel p-6 sm:p-8 space-y-3">
          <div className="eyebrow flex items-center gap-1.5">
            <MessageSquare className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
            Mock Interview
          </div>
          <h1 className="h-page heading-glow">Practise explaining — like a real interview</h1>
          <p className="desc-glow text-[var(--text-secondary)] text-sm sm:text-base leading-relaxed">
            Step 1: add your resume if you like (optional). Step 2: choose how you want to be interviewed.
          </p>
        </div>

        <ResumeCard onChange={r => { setResume(r); setUseResume(r !== null) }} />
        {resume && (
          <label className="text-sm flex items-center gap-2 text-slate-200">
            <input type="checkbox" checked={useResume} onChange={e => setUseResume(e.target.checked)} className="accent-[var(--accent-orange)]" />
            Ask me questions from my resume (typed, voice or video)
          </label>
        )}

        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Choose how to interview</div>
          <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Interview type">
            {modeBtn('typed', '⌨️', 'Typed', 'Type your answers (or dictate with the mic) and read the questions.')}
            {modeBtn('voice', '🎙', 'Voice with the agent', 'Talk with the ElevenLabs interviewer, hands-free.')}
            {modeBtn('video', '🎥', 'Video', 'Camera and microphone required. Recorded to your own device.')}
          </div>
        </div>

        {mode === 'typed' && (
          <div className="card p-6 sm:p-8 space-y-5">
            {withResume ? (
              <>
                <p className="text-sm text-[var(--text-secondary)] desc-glow">
                  Five questions written from your resume and your answers. After each answer you get feedback that quotes your own words. This is practice coaching: it does not change your skill estimates.
                </p>
                <div className="pt-2">
                  <button className="btn btn-orange py-3 px-6 text-sm font-semibold flex items-center gap-2 shadow-[0_6px_20px_rgba(255,120,30,0.25)]" onClick={start} disabled={busy}>
                    {busy ? 'Preparing…' : 'Start the typed interview (from my resume)'}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
                <p className="text-xs text-[var(--text-muted)]">
                  To use the round types and placement packs instead, untick "Ask me questions from my resume" above.
                </p>
              </>
            ) : (
              <>
                <div>
                  <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-2">Interview Round</label>
                  <div className="grid grid-cols-3 gap-2.5">
                    <button
                      type="button"
                      className={`py-2.5 px-3 rounded-xl border text-sm font-semibold transition ${round === 'technical' ? 'bg-[rgba(255,138,36,0.18)] text-white border-[rgba(255,138,36,0.4)] shadow-[0_0_12px_rgba(255,138,36,0.2)] font-bold' : 'glass-panel text-slate-300 border-[var(--border-subtle)] hover:bg-[rgba(255,255,255,0.06)]'}`}
                      onClick={() => setRound('technical')}
                    >
                      Technical
                    </button>
                    <button
                      type="button"
                      className={`py-2.5 px-3 rounded-xl border text-sm font-semibold transition ${round === 'behavioural' ? 'bg-[rgba(255,138,36,0.18)] text-white border-[rgba(255,138,36,0.4)] shadow-[0_0_12px_rgba(255,138,36,0.2)] font-bold' : 'glass-panel text-slate-300 border-[var(--border-subtle)] hover:bg-[rgba(255,255,255,0.06)]'}`}
                      onClick={() => setRound('behavioural')}
                    >
                      HR & Behavioural
                    </button>
                    <button
                      type="button"
                      className={`py-2.5 px-3 rounded-xl border text-sm font-semibold transition ${round === 'full' ? 'bg-[rgba(255,138,36,0.18)] text-white border-[rgba(255,138,36,0.4)] shadow-[0_0_12px_rgba(255,138,36,0.2)] font-bold' : 'glass-panel text-slate-300 border-[var(--border-subtle)] hover:bg-[rgba(255,255,255,0.06)]'}`}
                      onClick={() => setRound('full')}
                    >
                      Full Mock (Both)
                    </button>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mt-2 desc-glow">
                    {round === 'technical' && 'Evaluates system design, queries, and core concepts with verified code explanations.'}
                    {round === 'behavioural' && 'Starts with 90s self-introduction, then probes STAR behavioural stories and project walkthrough.'}
                    {round === 'full' && 'Comprehensive interview starting with self-intro, then situational questions, and deep technical topics.'}
                  </p>
                </div>

                <div>
                  <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-2">Placement & Role Pack (Optional)</label>
                  <div className="flex gap-2 flex-wrap">
                    <button
                      type="button"
                      className={`py-1.5 px-3 rounded-xl border text-xs font-semibold transition ${selectedPackId === '' ? 'bg-[rgba(77,157,255,0.2)] text-white border-[rgba(77,157,255,0.4)] font-bold' : 'glass-panel text-slate-300 border-[var(--border-subtle)] hover:bg-[rgba(255,255,255,0.06)]'}`}
                      onClick={() => setSelectedPackId('')}
                    >
                      Standard (Adaptive)
                    </button>
                    {packs.map(p => (
                      <button
                        key={p.id}
                        type="button"
                        className={`py-1.5 px-3 rounded-xl border text-xs font-semibold transition ${selectedPackId === p.id ? 'bg-[rgba(77,157,255,0.2)] text-white border-[rgba(77,157,255,0.4)] font-bold' : 'glass-panel text-slate-300 border-[var(--border-subtle)] hover:bg-[rgba(255,255,255,0.06)]'}`}
                        onClick={() => setSelectedPackId(p.id)}
                      >
                        {p.title}
                      </button>
                    ))}
                  </div>
                  {activePack && (
                    <div className="mt-2.5 p-3.5 card rounded-xl border border-[var(--border-subtle)] text-xs space-y-1">
                      <div className="font-bold text-white heading-glow">{activePack.title} ({activePack.target_company_type})</div>
                      <div className="text-slate-300 desc-glow">{activePack.description}</div>
                      <div className="text-[11px] text-[var(--text-muted)] italic font-mono">Duration: ~{activePack.duration_minutes}m · Source: {activePack.source}</div>
                    </div>
                  )}
                </div>

                <ul className="text-sm space-y-2 list-disc pl-5 text-[var(--text-secondary)] desc-glow">
                  <li>No hints or feedback during the interview — full audit report comes at the end.</li>
                  <li>Behavioural answers scored with STAR checklists; own actions validated with verbatim quotes.</li>
                  <li>No made-up percentiles: see exactly what you proved and what you missed.</li>
                </ul>

                <div className="flex gap-3 flex-wrap pt-2">
                  <button className="btn btn-orange py-3 px-7 text-sm font-semibold flex items-center gap-2 shadow-[0_6px_20px_rgba(255,120,30,0.25)]" onClick={start} disabled={busy}>
                    {busy ? 'Preparing…' : 'Start the typed interview'}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button className="btn btn-ghost py-3 ml-auto text-xs" onClick={loadHistory}>
                    📜 Past interview history
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {mode === 'voice' && (
          <div className="card p-6 space-y-3">
            <p className="text-sm text-[var(--text-secondary)] desc-glow">
              A spoken interview with the ElevenLabs voice agent. {withResume ? 'The questions are written from your resume, and the agent is told only a short summary of it (skills and project names). Your written feedback appears in your interview list afterwards.' : 'It uses the standard interview topics for your target role, with the same scoring and quotes as the typed interview.'}
            </p>
            <button className="btn btn-orange py-3 px-6 flex items-center gap-2 text-sm font-semibold" onClick={() => openVoice('interview', undefined, { useResume: withResume })}>
              <Mic className="w-4 h-4" />
              Start the voice interview
            </button>
          </div>
        )}

        {mode === 'video' && (
          <div className="card p-6 space-y-3">
            <p className="text-sm text-[var(--text-secondary)] desc-glow">
              Like a real video call: the camera and microphone are required and checked first (face, distance, head angle, lighting, voice level). {withResume ? 'Questions come from your resume.' : 'Questions are general interview questions.'} The video and voice are recorded to this device only, never uploaded, and kept until you delete them.
            </p>
            <button className="btn btn-orange py-3 px-6 flex items-center gap-2 text-sm font-semibold" onClick={() => nav('/video-interview', { state: { fromInterview: true, useResume: withResume } })}>
              🎥 Set up camera and start
            </button>
            <div><Link to="/video-interview" className="text-xs text-[var(--accent-orange)] hover:underline font-semibold">My interview recordings →</Link></div>
          </div>
        )}

        {(mode !== 'typed' || withResume) && (
          <button className="btn btn-ghost btn-sm text-xs" onClick={loadHistory}>
            📜 Past interview history
          </button>
        )}



        {showHistory && (
          <div className="card p-5 space-y-3">
            <div className="flex items-center justify-between">
              <SectionTitle eyebrow="Audit log" title="Your past mock interviews" />
              <button className="text-xs text-[var(--text-muted)] font-bold hover:underline" onClick={() => setShowHistory(false)}>Close</button>
            </div>
            {history.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)] desc-glow">No completed interviews yet.</p>
            ) : (
              <div className="divide-y divide-[var(--border-subtle)]">
                {history.map(h => (
                  <div key={h.session_id} className="py-2.5 flex items-center justify-between text-xs">
                    <div>
                      <span className="font-bold text-white capitalize">{h.round} round</span>
                      {h.pack_id && <span className="chip ml-2" style={{ background: 'rgba(210,225,235,0.08)', color: '#AEBBC5' }}>{h.pack_id.replace(/_/g, ' ')}</span>}
                      <span className="text-[var(--text-muted)] ml-2">{h.created_at ? new Date(h.created_at).toLocaleDateString() : ''}</span>
                    </div>
                    <div className="font-semibold text-slate-200">
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
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="glass-panel p-6 sm:p-8 space-y-2">
          <div className="eyebrow flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#35D07F]" />
            Interview report · {report.round?.toUpperCase()} ROUND
          </div>
          <h1 className="h-page heading-glow">{report.role_title} — What You Covered</h1>
        </div>

        <div className="card p-6 flex items-center gap-8 flex-wrap justify-between">
          <div>
            <div className="text-4xl sm:text-5xl font-extrabold text-white heading-glow tracking-tight">
              {report.checklist_items_covered}
              <span className="text-[var(--text-muted)] text-2xl font-normal"> / {report.checklist_items_total}</span>
            </div>
            <div className="text-xs sm:text-sm text-[var(--text-muted)] mt-1 desc-glow">
              Key evaluation points verified from your explanations
            </div>
          </div>
          <div className="text-sm space-y-2 max-w-md">
            <div className="flex items-start gap-2">
              <span className="chip" style={{ background: 'rgba(53, 208, 127, 0.15)', color: '#35D07F', border: '1px solid rgba(53, 208, 127, 0.3)' }}>
                Strong
              </span>
              <span className="text-white text-sm">{report.strengths.join(', ') || 'No standout areas identified yet'}</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="chip" style={{ background: 'rgba(255, 83, 100, 0.15)', color: '#FF5364', border: '1px solid rgba(255, 83, 100, 0.3)' }}>
                Work on
              </span>
              <span className="text-white text-sm">{report.needs_work.join(', ') || 'Nothing major — solid coverage'}</span>
            </div>
          </div>
        </div>

        {report.behavioural_summary && (
          <div className="card p-5 bg-[rgba(168,85,247,0.08)] border border-[rgba(168,85,247,0.25)] space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-[#C084FC]">STAR Behavioural Assessment</span>
              <span className="text-xs font-semibold text-white">
                {report.behavioural_summary.items_covered} / {report.behavioural_summary.items_total} STAR points verified
              </span>
            </div>
            <p className="text-xs text-slate-300 desc-glow">
              Evaluated across {report.behavioural_summary.topics_assessed} behavioural question{report.behavioural_summary.topics_assessed === 1 ? '' : 's'}. Actions were credited only when personal ownership ("I") was articulated with verifiable evidence.
            </p>
          </div>
        )}

        {behTopics.length > 0 && (
          <div className="space-y-4">
            <SectionTitle eyebrow="Communication" title="HR & Behavioural questions" />
            {behTopics.map((t: any) => (
              <div key={t.concept_id} className="card p-5 sm:p-6 space-y-4">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <Link to={'/learn/' + t.concept_id} className="font-extrabold text-base sm:text-lg text-white hover:text-[#FF8A24] transition">{t.name}</Link>
                  <span className="chip" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#C084FC', border: '1px solid rgba(168, 85, 247, 0.3)' }}>STAR Rubric</span>
                  <LevelChip level={t.level_after} />
                  {t.misconceptions.length > 0 && <FlagChip flag="misconception" />}
                  <span className="text-xs sm:text-sm text-[var(--text-muted)] ml-auto font-mono">{Math.round(t.score * 100)}% · estimate {Math.round(t.p_before * 100)}% → {Math.round(t.p_after * 100)}%</span>
                </div>
                <Bar value={t.score} />
                <div className="grid md:grid-cols-2 gap-3.5 mt-2">
                  <div className="rounded-xl bg-[rgba(53,208,127,0.08)] border border-[rgba(53,208,127,0.22)] p-4 text-sm">
                    <div className="font-bold text-[#35D07F] flex items-center gap-1.5 mb-2">
                      <CheckCircle2 className="w-4 h-4" /> Covered
                    </div>
                    <ul className="space-y-1.5 text-xs sm:text-sm text-slate-100">
                      {t.covered.map((c: any) => (
                        <li key={c.id} className="flex items-start gap-2">
                          <span className="text-[#35D07F] shrink-0 font-bold">✓</span>
                          <span>{c.text}{c.evidence && <i className="text-[var(--text-muted)] block text-xs mt-0.5"> — “{c.evidence}”</i>}</span>
                        </li>
                      ))}
                      {!t.covered.length && <li className="text-[var(--text-muted)] italic">Nothing verifiable.</li>}
                    </ul>
                  </div>
                  <div className="rounded-xl bg-[rgba(255,138,36,0.08)] border border-[rgba(255,138,36,0.22)] p-4 text-sm">
                    <div className="font-bold text-[var(--accent-orange)] flex items-center gap-1.5 mb-2">
                      <AlertCircle className="w-4 h-4" /> Missed
                    </div>
                    <ul className="space-y-1.5 text-xs sm:text-sm text-slate-100">
                      {t.missed.map((c: any) => (
                        <li key={c.id} className="flex items-start gap-2">
                          <span className="text-[var(--accent-orange)] shrink-0 font-bold">○</span>
                          <span>{c.text}</span>
                        </li>
                      ))}
                      {!t.missed.length && <li className="text-[#35D07F] italic font-medium">Nothing missed — great.</li>}
                    </ul>
                  </div>
                </div>
                <details className="text-xs sm:text-sm group">
                  <summary className="cursor-pointer font-bold text-[#4D9DFF] hover:text-[#7bb5ff] transition py-1 flex items-center gap-1">
                    <HelpCircle className="w-3.5 h-3.5" /> Model answer
                  </summary>
                  <p className="mt-2 bg-[rgba(10,20,30,0.40)] border border-[var(--border-subtle)] rounded-xl p-4 text-slate-300 desc-glow leading-relaxed">{t.model_answer}</p>
                </details>
              </div>
            ))}
          </div>
        )}

        {techTopics.length > 0 && (
          <div className="space-y-4">
            <SectionTitle eyebrow="Engineering" title="Technical questions" />
            {techTopics.map((t: any) => (
              <div key={t.concept_id} className="card p-5 sm:p-6 space-y-4">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <Link to={'/learn/' + t.concept_id} className="font-extrabold text-base sm:text-lg text-white hover:text-[#FF8A24] transition">{t.name}</Link>
                  <LevelChip level={t.level_after} />
                  {t.misconceptions.length > 0 && <FlagChip flag="misconception" />}
                  <span className="text-xs sm:text-sm text-[var(--text-muted)] ml-auto font-mono">{Math.round(t.score * 100)}% · estimate {Math.round(t.p_before * 100)}% → {Math.round(t.p_after * 100)}%</span>
                </div>
                <Bar value={t.score} />
                <div className="grid md:grid-cols-2 gap-3.5 mt-2">
                  <div className="rounded-xl bg-[rgba(53,208,127,0.08)] border border-[rgba(53,208,127,0.22)] p-4 text-sm">
                    <div className="font-bold text-[#35D07F] flex items-center gap-1.5 mb-2">
                      <CheckCircle2 className="w-4 h-4" /> Covered
                    </div>
                    <ul className="space-y-1.5 text-xs sm:text-sm text-slate-100">
                      {t.covered.map((c: any) => (
                        <li key={c.id} className="flex items-start gap-2">
                          <span className="text-[#35D07F] shrink-0 font-bold">✓</span>
                          <span>{c.text}{c.evidence && <i className="text-[var(--text-muted)] block text-xs mt-0.5"> — “{c.evidence}”</i>}</span>
                        </li>
                      ))}
                      {!t.covered.length && <li className="text-[var(--text-muted)] italic">Nothing verifiable.</li>}
                    </ul>
                  </div>
                  <div className="rounded-xl bg-[rgba(255,138,36,0.08)] border border-[rgba(255,138,36,0.22)] p-4 text-sm">
                    <div className="font-bold text-[var(--accent-orange)] flex items-center gap-1.5 mb-2">
                      <AlertCircle className="w-4 h-4" /> Missed
                    </div>
                    <ul className="space-y-1.5 text-xs sm:text-sm text-slate-100">
                      {t.missed.map((c: any) => (
                        <li key={c.id} className="flex items-start gap-2">
                          <span className="text-[var(--accent-orange)] shrink-0 font-bold">○</span>
                          <span>{c.text}</span>
                        </li>
                      ))}
                      {!t.missed.length && <li className="text-[#35D07F] italic font-medium">Nothing missed — great.</li>}
                    </ul>
                  </div>
                </div>
                <details className="text-xs sm:text-sm group">
                  <summary className="cursor-pointer font-bold text-[#4D9DFF] hover:text-[#7bb5ff] transition py-1 flex items-center gap-1">
                    <HelpCircle className="w-3.5 h-3.5" /> Model answer
                  </summary>
                  <p className="mt-2 bg-[rgba(10,20,30,0.40)] border border-[var(--border-subtle)] rounded-xl p-4 text-slate-300 desc-glow leading-relaxed">{t.model_answer}</p>
                </details>
              </div>
            ))}
          </div>
        )}

        {report.speech && (
          <div className="card p-5 space-y-3">
            <SectionTitle eyebrow="Voice & delivery" title="How you sounded" />
            <p className="text-xs text-[var(--text-muted)] desc-glow">
              Measured across {report.speech.answers_with_audio} spoken answer{report.speech.answers_with_audio === 1 ? '' : 's'}. This is supportive feedback, not an interview score.
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              {report.speech.median_wpm !== null && (
                <div className="rounded-xl border border-[var(--border-subtle)] p-3.5 card">
                  <div className="text-xs text-[var(--text-muted)] font-bold">Speaking pace</div>
                  <div className="text-xl font-extrabold text-white heading-glow mt-0.5">{report.speech.median_wpm} <span className="text-xs font-normal text-[var(--text-muted)]">WPM median</span></div>
                </div>
              )}
              {report.speech.top_markers?.length > 0 && (
                <div className="rounded-xl border border-[var(--border-subtle)] p-3.5 card">
                  <div className="text-xs text-[var(--text-muted)] font-bold">Top filler markers</div>
                  <div className="flex gap-1.5 flex-wrap mt-1">
                    {report.speech.top_markers.map((m: any) => (
                      <span key={m.marker} className="chip" style={{ background: 'rgba(255,138,36,0.12)', color: '#FF8A24', border: '1px solid rgba(255,138,36,0.3)' }}>
                        “{m.marker}” ×{m.count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {report.speech.tips?.length > 0 && (
              <div className="text-xs text-slate-300 desc-glow">
                <b>Tip:</b> {TIP_LABELS[report.speech.tips[0]]?.desc || 'Natural delivery with clear pauses.'}
              </div>
            )}
          </div>
        )}

        <Callout tone="teal" title="Adaptive Update Processed">
          {report.next_steps.join(' · ') || 'Great round completed.'} Your dynamic curriculum has adjusted automatically to address identified gaps — <Link className="underline font-bold text-[#4D9DFF]" to="/roadmap">view your updated roadmap</Link>.
        </Callout>

        <div className="flex gap-3 flex-wrap pt-2">
          <button className="btn btn-orange flex items-center gap-2" onClick={() => { setSession(null); setReport(null) }}>
            <RotateCcw className="w-4 h-4" />
            Start Another Round
          </button>
          <Link className="btn btn-secondary flex items-center gap-2" to="/">
            <LayoutDashboard className="w-4 h-4" />
            Return to Dashboard
          </Link>
        </div>
      </div>
    )
  }

  const isCurrentBehavioural = session.concept_id?.startsWith('comm_')

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="glass-panel p-5 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div className="eyebrow flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[var(--accent-orange)] animate-pulse" />
            <span>Mock interview · Topic {idx + 1} of {session.total}</span>
            {isCurrentBehavioural && <span className="chip bg-[rgba(168,85,247,0.2)] text-[#C084FC] border border-[rgba(168,85,247,0.4)] text-[10px]">STAR Behavioural</span>}
          </div>
          <h1 className="h-page heading-glow text-xl sm:text-2xl mt-0.5">{session.role_title}</h1>
        </div>
        <SpeakButton text={[...log].reverse().find(l => l.who === 'ai')?.text ?? ''} label="Hear question" />
      </div>

      {isCurrentBehavioural && (
        <div className="p-3 rounded-xl bg-[rgba(168,85,247,0.12)] border border-[rgba(168,85,247,0.3)] text-xs text-purple-200 font-semibold flex items-center gap-2 desc-glow">
          <span>★</span>
          <span>STAR Method: Situation → Task → Action (what YOU did, using "I") → Result → Reflection</span>
        </div>
      )}

      <Bar value={idx / session.total} h={6} />

      <div className="card p-4 sm:p-5 space-y-3 min-h-[300px] flex flex-col justify-end" aria-live="polite">
        <div className="space-y-3 overflow-y-auto max-h-[460px] pr-1">
          {log.map((l, i) => (
            <div
              key={i}
              translate={l.who === 'you' ? 'no' : undefined}
              className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                l.who === 'ai'
                  ? 'bg-[rgba(12,35,51,0.45)] border border-[rgba(77,157,255,0.22)] text-[var(--text-primary)] rounded-tl-sm shadow-[0_4px_16px_rgba(0,0,0,0.2)]'
                  : 'bg-[rgba(25,39,51,0.55)] border border-[rgba(255,138,36,0.3)] text-white ml-auto rounded-tr-sm shadow-[0_4px_20px_rgba(0,0,0,0.25)]'
              }`}
            >
              {l.who === 'ai' && (
                <div className="text-[10px] text-[#4D9DFF] font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#4D9DFF]" />
                  {isCurrentBehavioural ? 'HR / Behavioural Interviewer' : 'Technical Interviewer'}
                </div>
              )}
              {l.who === 'you' && (
                <div className="text-[10px] text-[var(--accent-orange)] font-bold uppercase tracking-wider mb-1 flex items-center gap-1 justify-end">
                  <span>You</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-orange)]" />
                </div>
              )}
              <div className="desc-glow">{l.text}</div>
              {l.who === 'you' && l.speech && <div className="mt-2"><SpeechChips speech={l.speech} /></div>}
            </div>
          ))}
          <div ref={end} />
        </div>
      </div>

      {readback && (
        <Callout tone="violet" title="Quick check — did I hear that right?">
          You stated: <b>“{readback.statement}”</b>. Is this what you intended?
          <div className="mt-3 flex gap-2">
            <button className="btn btn-primary btn-sm" onClick={async () => { await api.confirmMis(readback.instance_id, true); setReadback(null) }}>
              Yes, that's correct
            </button>
            <button className="btn btn-secondary btn-sm" onClick={async () => { await api.confirmMis(readback.instance_id, false); setReadback(null) }}>
              No, I misspoke
            </button>
          </div>
        </Callout>
      )}

      {notice && <Callout tone="saffron" title="Attention">{notice}</Callout>}

      <div className="card p-5 space-y-4">
        <textarea
          className="input min-h-[120px] bg-[rgba(15,25,35,0.40)] border-[var(--border-subtle)] focus:border-[var(--accent-orange)] text-[var(--text-primary)] rounded-xl"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={isCurrentBehavioural ? "Answer using STAR (Situation, Task, your own Action with 'I', Result)..." : "Formulate your response as you would in an engineering interview…"}
          aria-label="Your answer"
          disabled={busy}
        />
        {speech && <SpeechChips speech={speech} />}
        <div className="flex flex-wrap items-end justify-between gap-3 pt-1">
          <ConfidencePicker value={conf} onChange={setConf} />
          <div className="flex gap-2">
            <MicButton
              onText={t => setText(p => (p ? p + ' ' : '') + t)}
              onSpeech={s => setSpeech(s)}
              disabled={busy}
            />
            <button
              className="btn btn-orange py-2 px-6 flex items-center gap-2"
              disabled={busy || !text.trim()}
              onClick={send}
            >
              {busy ? 'Evaluating…' : 'Submit Answer'}
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
        {checklist.length > 0 && (
          <div className="text-xs text-[var(--text-muted)] font-mono">
            Points covered so far on this topic: {checklist.filter(c => c.covered).length}/{checklist.length} (shown to you only after the interview ends)
          </div>
        )}
      </div>
    </div>
  )
}

