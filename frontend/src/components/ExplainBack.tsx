import { useEffect, useState } from 'react'
import { api } from '../api'
import { useApp } from '../store'
import { MicButton, SpeakButton } from './audio'
import { SpeechChips } from './SpeechChips'
import { SpeechMetrics } from '../api_ext/T11'
import { Bar, Callout, Collapsible, ConfidencePicker, FlagChip, LevelChip, Spinner } from './ui'
import { MessageSquareQuote, CheckCircle2, AlertCircle, Sparkles, Send, RotateCcw } from 'lucide-react'

/** "Don't answer me — teach it back to me." Type or speak; scored against a checklist with verified quotes. */
export default function ExplainBack({ conceptId, onDone }: { conceptId: string; onDone?: (final: any) => void }) {
  const { toast, bump, setRoadmapNote, lang } = useApp()
  const [session, setSession] = useState<any | null>(null)
  const [text, setText] = useState('')
  const [conf, setConf] = useState<number | null>(null)
  const [speech, setSpeech] = useState<SpeechMetrics | null>(null)
  const [turns, setTurns] = useState<{ who: 'ai' | 'you'; text: string; speech?: SpeechMetrics | null }[]>([])
  const [checklist, setChecklist] = useState<any[]>([])
  const [readback, setReadback] = useState<any | null>(null)
  const [final, setFinal] = useState<any | null>(null)
  const [busy, setBusy] = useState(false)
  const [starting, setStarting] = useState(true)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setStarting(true)
    setSession(null)
    setFinal(null)
    setTurns([])
    setChecklist([])
    setReadback(null)
    setNotice(null)
    setText('')
    api.ebStart(conceptId).then(s => {
      if (!live) return
      setSession(s)
      setTurns([{ who: 'ai', text: s.prompt }])
      setChecklist([])
      setStarting(false)
    }).catch(e => {
      toast(e.message, 'err')
      setStarting(false)
    })
    return () => { live = false }
    // eslint-disable-next-line
  }, [conceptId])

  async function submit() {
    if (!text.trim() || !session) return
    setBusy(true)
    setNotice(null)
    const mine = text
    const curSpeech = speech
    try {
      const r = await api.ebAnswer({
        session_id: session.session_id,
        text: mine,
        stated_confidence: conf,
        channel: curSpeech ? 'audio' : 'text',
        audio_seconds: curSpeech?.speaking_seconds,
        speech: curSpeech ?? undefined,
      })
      if (r.unavailable) { setNotice(r.message); return }
      if (r.insufficient) { setNotice(r.message); return }
      setTurns(t => [
        ...t,
        { who: 'you', text: mine, speech: curSpeech },
        ...(r.followup ? [{ who: 'ai' as const, text: r.followup }] : []),
      ])
      setText('')
      setSpeech(null)
      setChecklist(r.checklist)
      if (r.readback) setReadback(r.readback)
      if (r.final) finish(r.final, r)
    } catch (e: any) {
      toast(e.message, 'err')
    } finally {
      setBusy(false)
    }
  }

  function finish(f: any, r: any) {
    setFinal(f)
    onDone?.(f)
    if (r?.after?.roadmap?.changed) setRoadmapNote(r.after.roadmap.change_reason)
    bump()
  }

  async function scoreNow() {
    if (!session) return
    setBusy(true)
    try {
      const r = await api.ebFinish(session.session_id)
      setChecklist(c => c)
      finish(r.final, r)
    } catch (e: any) {
      toast(e.message, 'warn')
    } finally {
      setBusy(false)
    }
  }

  async function answerReadback(yes: boolean) {
    if (!readback) return
    try {
      await api.confirmMis(readback.instance_id, yes)
      toast(yes ? 'Thanks — noted. Your plan will include a targeted fix.' : "Okay, I won't count that.", 'ok')
      bump()
    } catch (e: any) {
      toast(e.message, 'err')
    }
    setReadback(null)
  }

  if (starting) return (
    <div className="card p-6 flex justify-center">
      <Spinner label="Preparing diagnostic teach-back probe…" />
    </div>
  )

  if (!session) return (
    <div className="card p-6 text-sm text-[var(--text-muted)] text-center desc-glow">
      Teach-back is not available for this concept yet.
    </div>
  )

  const done = !!final

  return (
    <div className="card p-5 sm:p-6 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2 pb-1 border-b border-[var(--border-subtle)]">
        <div>
          <div className="eyebrow flex items-center gap-1.5">
            <MessageSquareQuote className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
            Active Retrieval · Teach-Back
          </div>
          <div className="font-extrabold text-[var(--text-primary)] text-base sm:text-lg">
            Don't answer me — teach it back to me.
          </div>
        </div>
        <SpeakButton text={turns[turns.length - 1]?.who === 'ai' ? turns[turns.length - 1].text : session.prompt} label="Hear question" />
      </div>

      <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
        {turns.map((t, i) => (
          <div
            key={i}
            className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              t.who === 'ai'
                ? 'bg-[rgba(12,35,51,0.45)] border border-[rgba(77,157,255,0.22)] text-[var(--text-primary)] rounded-tl-sm shadow-[0_4px_16px_rgba(0,0,0,0.2)]'
                : 'bg-[rgba(25,39,51,0.55)] border border-[rgba(255,138,36,0.3)] text-white ml-auto rounded-tr-sm shadow-[0_4px_20px_rgba(0,0,0,0.25)]'
            }`}
          >
            {t.who === 'ai' && (
              <div className="text-[10px] text-[#4D9DFF] font-bold uppercase tracking-wider mb-1 flex items-center gap-1">
                <span>Evaluator</span>
              </div>
            )}
            <div translate={t.who === 'you' ? 'no' : undefined} className="desc-glow">{t.text}</div>
            {t.who === 'you' && t.speech && (
              <div className="mt-2 pt-2 border-t border-[rgba(255,255,255,0.1)]">
                <SpeechChips speech={t.speech} />
              </div>
            )}
          </div>
        ))}
      </div>

      {readback && (
        <Callout tone="violet" title="Did I hear you right?">
          You said: <b>“{readback.statement}”</b> — is that what you meant?
          <div className="mt-3 flex gap-2">
            <button className="btn btn-primary btn-sm" onClick={() => answerReadback(true)}>
              Yes, that's what I think
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => answerReadback(false)}>
              No, I misspoke
            </button>
          </div>
        </Callout>
      )}

      {notice && <Callout tone="saffron" title="Heads up">{notice}</Callout>}

      {checklist.length > 0 && (
        <div className="rounded-xl border border-[var(--border-subtle)] p-3.5 bg-[rgba(15,25,35,0.30)]">
          <div className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider mb-2">
            Checklist points covered so far (backed by your quotes):
          </div>
          <ul className="space-y-1.5 text-xs sm:text-sm">
            {checklist.map(c => (
              <li key={c.id} className="flex items-start gap-2">
                <span className={c.covered ? 'text-[#35D07F] font-bold' : 'text-[var(--text-muted)]'}>
                  {c.covered ? '✓' : '○'}
                </span>
                <span className="text-[var(--text-primary)]">
                  {c.text}
                  {c.covered && c.evidence && <span className="text-[var(--text-muted)] italic block text-xs mt-0.5"> — “{c.evidence}”</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!done && (
        <div className="space-y-3 pt-1">
          <textarea
            className="input min-h-[110px] bg-[rgba(15,25,35,0.40)] border-[var(--border-subtle)] text-[var(--text-primary)] rounded-xl"
            value={text}
            onChange={e => setText(e.target.value)}
            disabled={busy}
            placeholder={
              lang === 'english'
                ? 'Explain it in your own words… (English, Hindi or Hinglish all work)'
                : 'Apne shabdon mein samjhaiye… (Hindi, English ya Hinglish)'
            }
            aria-label="Your explanation"
          />
          {speech && (
            <div className="p-2 rounded-lg bg-[rgba(12,24,36,0.4)] border border-[var(--border-subtle)]">
              <SpeechChips speech={speech} />
            </div>
          )}
          <div className="flex flex-wrap items-end justify-between gap-3">
            <ConfidencePicker value={conf} onChange={setConf} label="How confident are you in your explanation?" />
            <div className="flex gap-2 flex-wrap items-center">
              <MicButton
                onText={t => setText(prev => (prev ? prev + ' ' : '') + t)}
                onSpeech={s => setSpeech(s)}
                disabled={busy}
              />
              {turns.length > 2 && (
                <button className="btn btn-secondary text-xs py-2 px-3" onClick={scoreNow} disabled={busy}>
                  Score what I've said
                </button>
              )}
              <button
                className="btn btn-orange py-2 px-6 text-sm font-semibold flex items-center gap-2"
                onClick={submit}
                disabled={busy || !text.trim()}
              >
                {busy ? 'Evaluating…' : 'Send'}
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {done && (
        <div className="space-y-4 pt-2">
          <div className="flex items-center gap-5 flex-wrap">
            <div className="text-4xl sm:text-5xl font-extrabold text-[var(--text-primary)] heading-glow tracking-tight">
              {Math.round(final.score * 100)}%
            </div>
            <div>
              <div className="font-bold text-[var(--text-primary)] text-sm sm:text-base">
                of key points verified from your explanations
              </div>
              <div className="text-xs text-[var(--text-muted)] desc-glow mt-0.5">
                Grader confidence {Math.round(final.grader_confidence * 100)}%
                {final.low_confidence ? ' — too low to alter twin mastery estimate' : ''}
              </div>
              <div className="flex items-center gap-2 mt-1.5 text-xs sm:text-sm">
                <span className="font-mono text-[var(--text-muted)]">
                  {Math.round(final.mastery.p_before * 100)}% → <b className="text-[var(--text-primary)]">{Math.round(final.mastery.p_after * 100)}%</b>
                </span>
                <LevelChip level={final.mastery.level_after} />
              </div>
            </div>
          </div>

          <Bar value={final.score} />

          {final.note && (
            <Callout tone="violet" title="Score Capped">
              <FlagChip flag="misconception" /> {final.note}
            </Callout>
          )}

          <div className="grid md:grid-cols-2 gap-3.5">
            <div className="rounded-xl bg-[rgba(53,208,127,0.08)] border border-[rgba(53,208,127,0.22)] p-4 text-sm">
              <div className="font-bold text-[#35D07F] flex items-center gap-1.5 mb-2">
                <CheckCircle2 className="w-4 h-4" /> You Covered
              </div>
              <ul className="space-y-1.5 text-xs sm:text-sm text-[var(--text-primary)]">
                {final.covered.map((c: any) => (
                  <li key={c.id} className="flex items-start gap-1.5">
                    <span className="text-[#35D07F] font-bold">✓</span>
                    <span>{c.text}</span>
                  </li>
                ))}
                {!final.covered.length && <li className="text-[var(--text-muted)] italic">Nothing verifiable yet.</li>}
              </ul>
            </div>

            <div className="rounded-xl bg-[rgba(255,138,36,0.08)] border border-[rgba(255,138,36,0.22)] p-4 text-sm">
              <div className="font-bold text-[var(--accent-orange)] flex items-center gap-1.5 mb-2">
                <AlertCircle className="w-4 h-4" /> Still Missing
              </div>
              <ul className="space-y-1.5 text-xs sm:text-sm text-[var(--text-primary)]">
                {final.missed.map((c: any) => (
                  <li key={c.id} className="flex items-start gap-1.5">
                    <span className="text-[var(--accent-orange)] font-bold">○</span>
                    <span>{c.text}</span>
                  </li>
                ))}
                {!final.missed.length && <li className="text-[#35D07F] italic font-medium">Nothing — thorough explanation!</li>}
              </ul>
            </div>
          </div>

          <Collapsible title="Inspect Reference Model Explanation">
            <p className="text-xs sm:text-sm bg-[rgba(10,20,30,0.40)] border border-[var(--border-subtle)] rounded-xl p-4 text-[var(--text-secondary)] leading-relaxed desc-glow">
              {final.model_answer}
            </p>
          </Collapsible>

          <button
            className="btn btn-secondary text-xs flex items-center gap-1.5 py-2 px-4"
            onClick={() => {
              setFinal(null)
              setSession(null)
              setStarting(true)
              api.ebStart(conceptId).then(s => {
                setSession(s)
                setTurns([{ who: 'ai', text: s.prompt }])
                setChecklist([])
                setStarting(false)
              })
            }}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Try again with a fresh question
          </button>
        </div>
      )}
    </div>
  )
}

