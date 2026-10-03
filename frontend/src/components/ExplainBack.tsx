import { useEffect, useState } from 'react'
import { api } from '../api'
import { useApp } from '../store'
import { MicButton, SpeakButton } from './audio'
import { SpeechChips } from './SpeechChips'
import { SpeechMetrics } from '../api_ext/T11'
import { Bar, Callout, Collapsible, ConfidencePicker, FlagChip, LevelChip, Spinner } from './ui'

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
    setStarting(true); setSession(null); setFinal(null); setTurns([]); setChecklist([]); setReadback(null); setNotice(null); setText('')
    api.ebStart(conceptId).then(s => {
      if (!live) return
      setSession(s); setTurns([{ who: 'ai', text: s.prompt }])
      setChecklist([]); setStarting(false)
    }).catch(e => { toast(e.message, 'err'); setStarting(false) })
    return () => { live = false }
    // eslint-disable-next-line
  }, [conceptId])

  async function submit() {
    if (!text.trim() || !session) return
    setBusy(true); setNotice(null)
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
      setText(''); setSpeech(null); setChecklist(r.checklist)
      if (r.readback) setReadback(r.readback)
      if (r.final) finish(r.final, r)
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }
  function finish(f: any, r: any) {
    setFinal(f); onDone?.(f)
    if (r?.after?.roadmap?.changed) setRoadmapNote(r.after.roadmap.change_reason)
    bump()
  }
  async function scoreNow() {
    if (!session) return
    setBusy(true)
    try { const r = await api.ebFinish(session.session_id); setChecklist(c => c); finish(r.final, r) }
    catch (e: any) { toast(e.message, 'warn') } finally { setBusy(false) }
  }
  async function answerReadback(yes: boolean) {
    if (!readback) return
    try {
      await api.confirmMis(readback.instance_id, yes)
      toast(yes ? 'Thanks — noted. Your plan will include a targeted fix.' : "Okay, I won't count that.", 'ok')
      bump()
    } catch (e: any) { toast(e.message, 'err') }
    setReadback(null)
  }

  if (starting) return <div className="card p-5"><Spinner label="Preparing your question…" /></div>
  if (!session) return <div className="card p-5 text-sm text-muted">Teach-back is not available for this concept yet.</div>

  const done = !!final
  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="eyebrow">Teach it back</div>
          <div className="font-extrabold text-navy">Don't answer me — teach it back to me.</div>
        </div>
        <SpeakButton text={turns[turns.length - 1]?.who === 'ai' ? turns[turns.length - 1].text : session.prompt} label="Hear the question" />
      </div>

      <div className="space-y-2">
        {turns.map((t, i) => (
          <div key={i} className={`max-w-[92%] ${t.who === 'ai' ? '' : 'ml-auto'}`}>
            <div translate={t.who === 'you' ? 'no' : undefined} className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${t.who === 'ai' ? 'bg-teal-soft text-ink rounded-tl-sm' : 'bg-navy text-white rounded-tr-sm'}`}>
              {t.text}
            </div>
            {t.who === 'you' && t.speech && <SpeechChips speech={t.speech} />}
          </div>
        ))}
      </div>

      {readback && (
        <Callout tone="violet" title="Did I hear you right?">
          You said: <b>“{readback.statement}”</b> — is that what you meant?
          <div className="mt-2 flex gap-2"><button className="btn btn-primary btn-sm" onClick={() => answerReadback(true)}>Yes, that's what I think</button><button className="btn btn-ghost btn-sm" onClick={() => answerReadback(false)}>No, I misspoke</button></div>
        </Callout>
      )}
      {notice && <Callout tone="saffron" title="Heads up">{notice}</Callout>}

      {checklist.length > 0 && (
        <div className="rounded-xl border border-line p-3 bg-paper/60">
          <div className="text-xs font-bold text-muted mb-1.5">What you've covered so far (each tick is backed by your own words)</div>
          <ul className="space-y-1">
            {checklist.map(c => (
              <li key={c.id} className="text-sm flex gap-2"><span className={c.covered ? 'text-lvl-proficient font-bold' : 'text-muted'}>{c.covered ? '✓' : '○'}</span>
                <span>{c.text}{c.covered && c.evidence && <span className="text-muted italic"> — “{c.evidence}”</span>}</span></li>
            ))}
          </ul>
        </div>
      )}

      {!done && (
        <div className="space-y-2.5">
          <textarea className="input min-h-[110px]" value={text} onChange={e => setText(e.target.value)} disabled={busy}
            placeholder={lang === 'english' ? 'Explain it in your own words… (English, Hindi or Hinglish all work)' : 'Apne shabdon mein samjhaiye… (Hindi, English ya Hinglish)'} aria-label="Your explanation" />
          {speech && <SpeechChips speech={speech} />}
          <div className="flex flex-wrap items-end justify-between gap-3">
            <ConfidencePicker value={conf} onChange={setConf} label="How confident are you in your explanation?" />
            <div className="flex gap-2 flex-wrap">
              <MicButton
                onText={t => setText(prev => (prev ? prev + ' ' : '') + t)}
                onSpeech={s => setSpeech(s)}
                disabled={busy}
              />
              {turns.length > 2 && <button className="btn btn-ghost" onClick={scoreNow} disabled={busy}>Score what I've said</button>}
              <button className="btn btn-saffron" onClick={submit} disabled={busy || !text.trim()}>{busy ? 'Listening…' : 'Send'}</button>
            </div>
          </div>
        </div>
      )}

      {done && (
        <div className="space-y-3 pop">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="text-4xl font-extrabold text-navy">{Math.round(final.score * 100)}%</div>
            <div>
              <div className="font-bold">of the key points, backed by your own words</div>
              <div className="text-xs text-muted">Grader confidence {Math.round(final.grader_confidence * 100)}%{final.low_confidence ? ' — too low to change your mastery' : ''}</div>
              <div className="flex items-center gap-2 mt-1 text-sm">{Math.round(final.mastery.p_before * 100)}% → <b>{Math.round(final.mastery.p_after * 100)}%</b> <LevelChip level={final.mastery.level_after} /></div>
            </div>
          </div>
          <Bar value={final.score} />
          {final.note && <Callout tone="violet" title="Score capped"><FlagChip flag="misconception" /> {final.note}</Callout>}
          <div className="grid md:grid-cols-2 gap-3">
            <div className="rounded-xl bg-[#e8f6ee] p-3"><div className="font-bold text-sm text-lvl-proficient mb-1">You covered</div>
              <ul className="text-sm space-y-1">{final.covered.map((c: any) => <li key={c.id}>✓ {c.text}</li>)}{!final.covered.length && <li className="text-muted">Nothing verifiable yet.</li>}</ul></div>
            <div className="rounded-xl bg-saffron-soft p-3"><div className="font-bold text-sm text-saffron mb-1">Still missing</div>
              <ul className="text-sm space-y-1">{final.missed.map((c: any) => <li key={c.id}>○ {c.text}</li>)}{!final.missed.length && <li className="text-muted">Nothing — great explanation.</li>}</ul></div>
          </div>
          <Collapsible title="See a model answer"><p className="text-sm bg-paper rounded-xl p-3">{final.model_answer}</p></Collapsible>
          <button className="btn btn-ghost btn-sm" onClick={() => { setFinal(null); setSession(null); setStarting(true); api.ebStart(conceptId).then(s => { setSession(s); setTurns([{ who: 'ai', text: s.prompt }]); setChecklist([]); setStarting(false) }) }}>Try again with a fresh question</button>
        </div>
      )}
    </div>
  )
}
