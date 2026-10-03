import { useEffect, useState } from 'react'
import { apiC03, type CaseSummaryData } from '../api_ext/C03'

interface CaseSummaryProps {
  caseId: string
  status: string
}

export function CaseSummary({ caseId, status }: CaseSummaryProps) {
  const [summary, setSummary] = useState<CaseSummaryData | null>(null)

  useEffect(() => {
    if (!['followup', 'closed'].includes(status)) {
      setSummary(null)
      return
    }
    let active = true
    apiC03.getSummary(caseId)
      .then(data => { if (active) setSummary(data) })
      .catch(() => { if (active) setSummary(null) })
    return () => { active = false }
  }, [caseId, status])

  if (!summary || !['followup', 'closed'].includes(status)) {
    return null
  }

  const pBefore = summary.saarthi_saw.p_before !== null ? Math.round(summary.saarthi_saw.p_before * 100) : null
  const pAfter = summary.saarthi_saw.p_after !== null ? Math.round(summary.saarthi_saw.p_after * 100) : null
  const gain = pBefore !== null && pAfter !== null ? pAfter - pBefore : null

  return (
    <div className="card p-5 border-l-4 border-l-saffron space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="eyebrow text-saffron">After your session</div>
          <h3 className="font-extrabold text-navy text-lg">Session Summary & Follow-up Check</h3>
        </div>
        <span className="chip" style={{ background: '#fff8e1', color: '#8d6e63' }}>
          Due: {summary.followup.due}
        </span>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* Mentor notes */}
        <div className="rounded-xl bg-paper p-4 space-y-2 border border-line">
          <div className="text-xs font-bold text-muted uppercase tracking-wider">
            What your mentor noted (verbatim):
          </div>
          <p className="text-sm text-navy italic">
            "{summary.mentor_said.notes || 'Session completed.'}"
          </p>
          <div className="pt-2 border-t border-line text-xs font-semibold text-teal">
            <b>Agreed next step:</b> {summary.mentor_said.next_step}
          </div>
          <div className="text-[11px] text-muted text-right">
            — {summary.mentor_said.by}
          </div>
        </div>

        {/* SAARTHI evidence change */}
        <div className="rounded-xl bg-paper p-4 space-y-2 border border-line">
          <div className="text-xs font-bold text-muted uppercase tracking-wider">
            What SAARTHI saw change:
          </div>
          <div className="text-sm font-bold text-navy">{summary.saarthi_saw.concept}</div>
          {pBefore !== null && pAfter !== null ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted">Mastery estimate:</span>
              <span className="font-semibold text-navy">{pBefore}%</span>
              <span>→</span>
              <span className="font-bold text-teal">{pAfter}%</span>
              {gain !== null && (
                <span className={`chip text-xs ${gain >= 0 ? 'bg-[#e2f4ea] text-[#1f6f45]' : 'bg-[#fbe9e7] text-[#c62828]'}`}>
                  {gain >= 0 ? `+${gain}` : gain} pts
                </span>
              )}
            </div>
          ) : (
            <div className="text-xs text-muted">Evidence recorded during session discussions.</div>
          )}
          {summary.saarthi_saw.evidence.length > 0 && (
            <div className="pt-2 border-t border-line">
              <div className="text-[11px] font-semibold text-muted mb-1">Recent evidence:</div>
              <div className="flex flex-wrap gap-1">
                {summary.saarthi_saw.evidence.map((ev, i) => (
                  <span key={i} className="chip text-[11px]" style={{ background: '#eceff3', color: '#5b6675' }}>
                    {ev.source.replace('_', ' ')}: {ev.score >= 0.7 ? '✓' : '—'}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Follow-up check task banner: only while the check is still to be done */}
      {status === 'followup' ? (
        <div className="rounded-xl bg-saffron-soft p-3.5 border border-saffron/30 flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs font-bold text-saffron uppercase tracking-wider">Follow-up check scheduled</div>
            <div className="text-sm font-extrabold text-navy mt-0.5">{summary.followup.task}</div>
            <div className="text-xs text-muted mt-0.5">
              Target date: <b>{summary.followup.due}</b>. Completing this check verifies that the session helped and closes the case.
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-xl bg-teal-soft p-3.5 text-sm font-semibold text-navy">Follow-up check completed.</div>
      )}
    </div>
  )
}
