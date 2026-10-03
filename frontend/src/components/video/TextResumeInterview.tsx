import { useState } from 'react'
import { apiV01, type InterviewAnswerResult, type InterviewReport, type InterviewStart } from '../../api_ext/V01'
import type { SpeechMetrics } from '../../api_ext/T11'
import { useApp } from '../../store'
import { MicButton, SpeakButton } from '../audio'
import { SpeechChips } from '../SpeechChips'
import { Bar, Callout, ConfidencePicker } from '../ui'

/** The typed interview with questions written from the learner's resume. No camera. Answers can be typed or spoken (ElevenLabs). */
export default function TextResumeInterview({ interview, onDone }: { interview: InterviewStart; onDone: (r: InterviewReport, speech: (SpeechMetrics | null)[]) => void }) {
  const { toast } = useApp()
  const [question, setQuestion] = useState(interview.question ?? '')
  const [answered, setAnswered] = useState(interview.answered)
  const [text, setText] = useState('')
  const [conf, setConf] = useState<number | null>(null)
  const [speech, setSpeech] = useState<SpeechMetrics | null>(null)
  const [speechByTurn, setSpeechByTurn] = useState<(SpeechMetrics | null)[]>([])
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState<InterviewAnswerResult | null>(null)

  async function finish(sp: (SpeechMetrics | null)[]) {
    try { onDone(await apiV01.finish(interview.id, {}), sp) } catch (e: any) { toast(e.message, 'err') }
  }

  async function submit() {
    if (!text.trim() || busy) return
    setBusy(true)
    try {
      const r = await apiV01.answer(interview.id, text.trim())
      const sp = [...speechByTurn, speech]
      setSpeechByTurn(sp); setLast(r); setAnswered(r.answered); setText(''); setSpeech(null); setConf(null)
      if (r.done) await finish(sp)
    } catch (e: any) { toast(e.message, 'err') } finally { setBusy(false) }
  }

  const fb = last?.feedback
  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div><div className="eyebrow">Typed interview · from your resume · question {Math.min(answered + 1, interview.total)} of {interview.total}</div><h1 className="h-page">Your interview</h1></div>
      <Bar value={answered / interview.total} h={6} />
      <div className="card p-4 space-y-3" aria-live="polite">
        <div className="rounded-2xl rounded-tl-sm bg-teal-soft px-4 py-3 text-sm leading-relaxed">
          <b className="block text-[11px] text-teal uppercase tracking-wide">Interviewer</b>{last ? 'Thank you. Here is some feedback, then the next question.' : question}
        </div>
        {!last && <SpeakButton text={question} label="Hear the question" />}
        {fb && last && (
          <div className="space-y-2 text-sm">
            {fb.status === 'unavailable' && <Callout tone="saffron" title="Feedback unavailable right now">The feedback service did not answer, so I will not guess. Your answer was saved and the interview continues.</Callout>}
            {fb.status === 'too_short' && <Callout tone="saffron" title="That answer was short">Try two or three full sentences next time.</Callout>}
            {fb.strengths.length > 0 && <div><b className="text-navy">What you did well</b><ul className="mt-1 space-y-1.5">{fb.strengths.map((s, i) => <li key={i}>✓ {s.point} <span className="text-muted italic">— “{s.quote}”</span></li>)}</ul></div>}
            {fb.gaps.length > 0 && <div><b className="text-navy">To improve</b><ul className="mt-1 list-disc ml-5 space-y-0.5">{fb.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul></div>}
            {!last.done && last.next_question && <button type="button" className="btn btn-saffron" onClick={() => { setQuestion(last.next_question!); setLast(null) }}>Next question →</button>}
          </div>)}
      </div>
      {!last && (
        <div className="card p-4 space-y-2.5">
          <textarea className="input min-h-[120px]" value={text} onChange={e => setText(e.target.value)} disabled={busy} placeholder="Type your answer, or use the microphone…" aria-label="Your answer" />
          {speech && <SpeechChips speech={speech} />}
          <div className="flex flex-wrap items-end justify-between gap-3">
            <ConfidencePicker value={conf} onChange={setConf} />
            <div className="flex gap-2">
              <MicButton onText={t => setText(p => (p ? p + ' ' : '') + t)} onSpeech={s => setSpeech(s)} disabled={busy} />
              <button type="button" className="btn btn-saffron" disabled={busy || !text.trim()} onClick={submit}>{busy ? 'Reading your answer…' : 'Submit answer'}</button>
            </div>
          </div>
          {answered > 0 && <button type="button" className="btn btn-ghost btn-sm" onClick={() => finish(speechByTurn)}>End the interview and see my report</button>}
        </div>)}
      <p className="text-[11px] text-muted">Practice coaching only: it does not change your skill estimates. Feedback quotes your own words.</p>
    </div>
  )
}
