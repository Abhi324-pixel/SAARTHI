import { useEffect, useState } from 'react'
import { apiC03, type CasePrepData } from '../api_ext/C03'

interface CasePrepProps {
  caseId: string
  status: string
}

export function CasePrep({ caseId, status }: CasePrepProps) {
  const [prep, setPrep] = useState<CasePrepData | null>(null)
  const [lang, setLang] = useState<'english' | 'hinglish' | 'hindi'>('english')
  const [openReport, setOpenReport] = useState(false)
  const [openAnswer, setOpenAnswer] = useState<number | null>(null)

  useEffect(() => {
    if (!['accepted', 'scheduled', 'matched', 'held'].includes(status)) {
      setPrep(null)
      return
    }
    let active = true
    apiC03.getPrep(caseId, lang)
      .then(data => { if (active) setPrep(data) })
      .catch(() => { if (active) setPrep(null) })
    return () => { active = false }
  }, [caseId, status, lang])

  if (!prep || !['accepted', 'scheduled', 'matched', 'held'].includes(status)) {
    return null
  }

  const sourceLabels: Record<string, { label: string; tone: string }> = {
    misconception: { label: 'Misconception doubt', tone: '#fdf2e9' },
    prerequisite: { label: 'Prerequisite check', tone: '#edf7ed' },
    concept: { label: 'Concept model', tone: '#e8f4fd' },
    career: { label: 'Career insight', tone: '#f3e8fd' },
    goal: { label: 'Goal next step', tone: '#fff8e1' },
  }

  return (
    <div className="card p-5 border-l-4 border-l-teal space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="eyebrow text-teal">Get ready for your session</div>
          <h3 className="font-extrabold text-navy text-lg">Personalised Prep Notes</h3>
        </div>
        <div className="flex items-center gap-1 rounded-xl bg-paper p-1 text-xs border border-line">
          {(['english', 'hinglish', 'hindi'] as const).map(l => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`px-2.5 py-1 rounded-lg font-bold capitalize transition ${
                lang === l ? 'bg-[var(--accent-orange)] text-white shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              {l === 'hinglish' ? 'Hinglish' : l === 'hindi' ? 'हिंदी' : 'English'}
            </button>
          ))}
        </div>
      </div>

      {prep.icebreaker && (
        <div className="rounded-xl bg-teal-soft p-3.5 border border-teal/20">
          <div className="text-xs font-bold text-teal mb-1">Your suggested ice-breaker:</div>
          <div className="text-sm text-navy italic">“{prep.icebreaker}”</div>
        </div>
      )}

      {prep.bring && prep.bring.length > 0 && (
        <div>
          <div className="text-xs font-bold text-muted uppercase tracking-wider mb-2">What to bring:</div>
          <ul className="space-y-1.5 text-sm">
            {prep.bring.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-teal font-bold mt-0.5">✓</span>
                <span className="text-navy">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {prep.questions && prep.questions.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-bold text-muted uppercase tracking-wider">
            Questions to ask your mentor ({prep.questions.length}):
          </div>
          <div className="space-y-2">
            {prep.questions.map((q, idx) => {
              const meta = sourceLabels[q.from] ?? { label: q.from, tone: '#eceff3' }
              return (
                <div key={idx} className="rounded-xl border border-line bg-paper/60 p-3 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="chip text-[11px]" style={{ background: meta.tone, color: '#16324f' }}>
                      {meta.label}
                    </span>
                    {q.hidden_answer && (
                      <button
                        onClick={() => setOpenAnswer(openAnswer === idx ? null : idx)}
                        className="text-xs text-teal font-semibold hover:underline"
                      >
                        {openAnswer === idx ? 'Hide clue' : 'Why this matters'}
                      </button>
                    )}
                  </div>
                  <p className="text-sm font-medium text-navy">{q.text}</p>
                  {openAnswer === idx && q.hidden_answer && (
                    <div className="text-xs text-slate-300 bg-black/30 p-2.5 rounded-lg border border-white/10 mt-1">
                      <b className="text-[var(--accent-orange)]">Concept insight:</b> {q.hidden_answer}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="pt-2 border-t border-line">
        <button
          onClick={() => setOpenReport(!openReport)}
          className="text-xs font-semibold text-muted hover:text-navy flex items-center gap-1"
        >
          <span>{openReport ? '▼' : '▶'}</span>
          <span>Privacy transparency: view the exact report your mentor sees</span>
        </button>
        {openReport && (
          <div className="mt-2 p-3 rounded-xl bg-paper text-xs text-muted max-h-48 overflow-auto font-mono">
            <pre>{JSON.stringify(prep.mentor_sees, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
