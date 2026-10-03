import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { apiT03, type AdaptationsResponse } from '../api_ext/T03'
import { apiT04 } from '../api_ext/T04'
import { Callout, DemoBadge, SectionTitle } from '../components/ui'
import { useApp } from '../store'

export default function Settings() {
  const { me, health, refreshMe, toast, bump, logout } = useApp()
  const nav = useNavigate()
  const [lang, setLang] = useState(me?.language ?? 'english')
  const [days, setDays] = useState(8)
  const [concept, setConcept] = useState('sql_outer_join')
  const [out, setOut] = useState<string | null>(null)
  const [streakGoal, setStreakGoal] = useState(3)
  const [streakShow, setStreakShow] = useState(true)
  const [streakSaved, setStreakSaved] = useState(false)
  const [adaptations, setAdaptations] = useState<AdaptationsResponse | null>(null)

  useEffect(() => {
    apiT03.adaptations().then(setAdaptations).catch(() => {})
  }, [bump])

  async function resetAdaptations() {
    try {
      const res = await apiT03.reset()
      toast(res.message)
      const fresh = await apiT03.adaptations()
      setAdaptations(fresh)
      bump()
    } catch (e: any) {
      toast(e.message, 'err')
    }
  }

  async function savePrefs() { try { await api.updateMe({ language: lang }); await refreshMe(); toast('Saved.') } catch (e: any) { toast(e.message, 'err') } }
  async function saveStreakSettings() {
    try {
      await apiT04.updateSettings({ daily_goal: streakGoal, show: streakShow })
      setStreakSaved(true)
      setTimeout(() => setStreakSaved(false), 2000)
    } catch (e: any) { toast(e.message, 'err') }
  }
  async function exportData() {
    const data = await api.exportMe()
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a'); a.href = url; a.download = 'saarthi-my-data.json'; a.click(); URL.revokeObjectURL(url)
  }
  async function del() {
    if (!confirm('Delete your profile and all learning data? This cannot be undone.')) return
    await api.deleteMe(); logout(); nav('/login')
  }

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div><div className="eyebrow">Settings & preferences</div><h1 className="h-page">{me?.name}</h1></div>
        <Link to="/profile" className="btn btn-ghost btn-sm">Learner Profile →</Link>
      </div>
      <div className="card p-5 space-y-3">
        <SectionTitle title="Language" />
        <div className="flex gap-2 items-end"><select translate="no" className="input max-w-xs" value={lang} onChange={e => setLang(e.target.value)}><option value="english">English</option><option value="hindi">हिन्दी</option><option value="hinglish">Hinglish</option></select><button className="btn btn-primary" onClick={savePrefs}>Save</button></div>
      </div>
      <div className="card p-5 space-y-3" id="t04-streak-settings">
        <SectionTitle title="Study streak" />
        <div className="flex gap-3 items-center flex-wrap">
          <label className="text-sm font-semibold">Daily goal (activities)
            <input id="t04-goal-input" type="number" min={1} max={10} value={streakGoal} onChange={e => setStreakGoal(+e.target.value)} className="input w-20 ml-2" />
          </label>
          <label className="text-sm font-semibold flex items-center gap-2">
            <input id="t04-show-toggle" type="checkbox" checked={streakShow} onChange={e => setStreakShow(e.target.checked)} />
            Show streak card on dashboard
          </label>
          <button className="btn btn-primary" onClick={saveStreakSettings}>Save</button>
          {streakSaved && <span className="text-xs text-teal font-semibold">Saved ✓</span>}
        </div>
        <p className="text-xs text-muted">Your streak is computed from your real activity — answers, SQL practice, teach-backs, and mentor sessions. You cannot add it manually.</p>
      </div>

      <div className="card p-5 space-y-3" id="t03-adaptations-panel">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <SectionTitle title="What SAARTHI has adapted for you" />
          <button className="btn btn-ghost btn-sm" onClick={resetAdaptations}>Reset to defaults</button>
        </div>
        <p className="text-xs text-muted">
          Based on your "Too easy", "Too hard", and "Helped" feedback, SAARTHI adjusts practice pacing and teaching approaches.
        </p>
        <div className="space-y-3 text-sm">
          <div>
            <b className="text-navy text-xs uppercase tracking-wider block mb-1.5">Practice Pacing by Domain</b>
            {adaptations && Object.keys(adaptations.practice_factors || {}).length > 0 ? (
              <div className="grid sm:grid-cols-2 gap-2">
                {Object.entries(adaptations.practice_factors).map(([dom, factor]) => (
                  <div key={dom} className="rounded-lg border border-line p-2.5 flex justify-between items-center">
                    <span className="font-semibold capitalize">{dom}</span>
                    <span className="chip" style={{ background: '#e8edf3', color: '#16324f' }}>
                      {factor.toFixed(1)}x {factor > 2.0 ? '(extra time)' : factor < 2.0 ? '(accelerated)' : '(default)'}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-muted">Default pacing active ({adaptations?.default_factor ?? 2.0}x practice factor across all domains).</div>
            )}
          </div>

          {adaptations && Object.keys(adaptations.helpful_strategies || {}).length > 0 && (
            <div>
              <b className="text-navy text-xs uppercase tracking-wider block mb-1.5">Preferred Teaching Approaches</b>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(adaptations.helpful_strategies).map(([strat, count]) => (
                  <span key={strat} className="chip" style={{ background: '#e2f4ea', color: '#1f6f45' }}>
                    {strat.replace(/_/g, ' ')} ({count}x helped)
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="card p-5 space-y-2">
        <SectionTitle title="Your data" />
        <p className="text-sm text-muted">Audio is never stored — only text transcripts. You can download everything SAARTHI knows about you, or delete it.</p>
        <div className="flex gap-2"><button className="btn btn-ghost" onClick={exportData}>Download my data</button><button className="btn btn-ghost" style={{ color: '#c62828' }} onClick={del}>Delete my account</button></div>
      </div>
      <div className="card p-5 space-y-2">
        <SectionTitle title="What is mock right now" right={<DemoBadge label="demo" />} />
        <ul className="text-sm space-y-1">
          {['auth', 'mentors', 'consent', 'cohort'].map(k => <li key={k} className="flex items-center gap-2"><b className="w-24 capitalize">{k}</b>{health?.adapters?.[k] === 'mock' ? <span className="chip" style={{ background: '#fdf3e9', color: '#9a4f0a' }}>mock</span> : <span className="chip" style={{ background: '#e2f4ea', color: '#1f6f45' }}>real ({health?.adapters?.[k]})</span>}</li>)}
          <li className="flex items-center gap-2"><b className="w-24">Gemini</b><span className="chip" style={{ background: health?.llm?.available ? '#e2f4ea' : '#fdeaea', color: health?.llm?.available ? '#1f6f45' : '#c62828' }}>{health?.llm?.available ? health.llm.model : 'not configured'}</span></li>
          <li className="flex items-center gap-2"><b className="w-24">ElevenLabs</b><span className="chip" style={{ background: health?.voice?.agent_ready ? '#e2f4ea' : '#fdeaea', color: health?.voice?.agent_ready ? '#1f6f45' : '#c62828' }}>{health?.voice?.agent_ready ? 'agent ready' : 'agent not set up'}</span><span className="chip" style={{ background: health?.voice?.tts_ready ? '#e2f4ea' : '#eceff3', color: health?.voice?.tts_ready ? '#1f6f45' : '#5b6675' }}>TTS</span><span className="chip" style={{ background: health?.voice?.stt_ready ? '#e2f4ea' : '#eceff3', color: health?.voice?.stt_ready ? '#1f6f45' : '#5b6675' }}>STT</span></li>
        </ul>
      </div>
      {health?.env !== 'prod' && (
        <div className="card p-5 space-y-3" style={{ borderStyle: 'dashed', borderColor: '#e07a1f' }}>
          <SectionTitle eyebrow="Demo tools" title="Time travel & scenarios" right={<DemoBadge label="dev only" title="Hidden when SAARTHI_ENV=prod" />} />
          <Callout tone="saffron">These helpers exist so a short demo can show things that normally take days. Everything they write is labelled <i>simulated</i> in the evidence log.</Callout>
          <div className="flex gap-2 items-end flex-wrap"><label className="text-sm font-semibold">Fast-forward (days)<input className="input mt-1 w-28" type="number" min={1} value={days} onChange={e => setDays(+e.target.value)} /></label>
            <button className="btn btn-ghost" onClick={async () => { const r = await api.devAdvance(days); setOut(r.roadmap.reason); bump(); refreshMe() }}>Advance time</button></div>
          <div className="flex gap-2 items-end flex-wrap"><label className="text-sm font-semibold">Simulate a persistent struggle on<input className="input mt-1 w-56" value={concept} onChange={e => setConcept(e.target.value)} /></label>
            <button className="btn btn-ghost" onClick={async () => { const r = await api.devStruggle(concept); setOut(JSON.stringify(r.after.escalation_suggestions.map((s: any) => s.reason))); bump() }}>Simulate</button></div>
          <button className="btn btn-ghost" onClick={async () => { await api.devSeedDemo(); bump(); toast('Demo history loaded (labelled simulated in the evidence log).') }}>Load a demo starting history</button>
          <button className="btn btn-ghost" onClick={async () => { if (confirm('Reset all your learning progress?')) { await api.devReset(); bump(); toast('Progress reset.') } }}>Reset my progress</button>
          {out && <div className="text-xs bg-paper rounded-lg p-2 font-mono break-words">{out}</div>}
        </div>
      )}
    </div>
  )
}
