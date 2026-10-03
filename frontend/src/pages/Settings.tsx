import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { apiT03, type AdaptationsResponse } from '../api_ext/T03'
import { apiT04 } from '../api_ext/T04'
import { Callout, DemoBadge, SectionTitle } from '../components/ui'
import { useApp } from '../store'
import { Settings as SettingsIcon, Globe, Shield, Download, Trash2, Cpu, FastForward, Flame, RotateCcw, Database } from 'lucide-react'

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

  async function savePrefs() {
    try {
      await api.updateMe({ language: lang })
      await refreshMe()
      toast('Preferences saved.')
    } catch (e: any) {
      toast(e.message, 'err')
    }
  }

  async function saveStreakSettings() {
    try {
      await apiT04.updateSettings({ daily_goal: streakGoal, show: streakShow })
      setStreakSaved(true)
      setTimeout(() => setStreakSaved(false), 2000)
    } catch (e: any) {
      toast(e.message, 'err')
    }
  }
  async function exportData() {
    const data = await api.exportMe()
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'saarthi-my-data.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  async function del() {
    if (!confirm('Delete your profile and all learning data? This cannot be undone.')) return
    await api.deleteMe()
    logout()
    nav('/login')
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="glass-panel p-6 sm:p-8 space-y-2 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="eyebrow flex items-center gap-1.5">
            <SettingsIcon className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
            Settings & Privacy
          </div>
          <h1 className="h-page heading-glow">{me?.name || 'Account Settings'}</h1>
          <p className="desc-glow text-[var(--text-secondary)] text-sm">
            Configure preferred instructional language, privacy controls, and inspect system telemetry.
          </p>
        </div>
        <Link to="/profile" className="btn btn-secondary btn-sm flex items-center gap-1.5">
          Learner Profile →
        </Link>
      </div>

      <div className="card p-6 space-y-4">
        <SectionTitle
          title="Instructional Language"
          subtitle="Preferred language for explanations, voice sessions, and dialogue."
        />
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[200px] max-w-xs">
            <select translate="no"
              className="input bg-[rgba(15,25,35,0.40)] border-[var(--border-subtle)] text-[var(--text-primary)] rounded-xl"
              value={lang}
              onChange={e => setLang(e.target.value)}
            >
              <option value="english">English</option>
              <option value="hindi">हिन्दी (Hindi)</option>
              <option value="hinglish">Hinglish (Colloquial)</option>
            </select>
          </div>
          <button className="btn btn-orange py-2.5 px-6 text-sm font-semibold" onClick={savePrefs}>
            Save Preferences
          </button>
        </div>
      </div>

      <div className="card p-6 space-y-4" id="t04-streak-settings">
        <SectionTitle
          title="Study Streak"
          subtitle="Keep your habit going with daily learning targets."
        />
        <div className="flex gap-4 items-center flex-wrap">
          <label className="text-sm font-semibold text-slate-200 desc-glow flex items-center gap-2">
            Daily goal (activities):
            <input
              id="t04-goal-input"
              type="number"
              min={1}
              max={10}
              value={streakGoal}
              onChange={e => setStreakGoal(+e.target.value)}
              className="input w-20 py-1.5 px-3 bg-[rgba(15,25,35,0.40)] border-[var(--border-subtle)] rounded-xl text-center"
            />
          </label>
          <label className="text-sm font-semibold text-slate-200 desc-glow flex items-center gap-2 cursor-pointer">
            <input
              id="t04-show-toggle"
              type="checkbox"
              checked={streakShow}
              onChange={e => setStreakShow(e.target.checked)}
              className="accent-[var(--accent-orange)] w-4 h-4 rounded"
            />
            Show streak card on dashboard
          </label>
          <button className="btn btn-primary text-xs py-2 px-4" onClick={saveStreakSettings}>
            Save
          </button>
          {streakSaved && <span className="text-xs text-[#35D07F] font-semibold">Saved ✓</span>}
        </div>
        <p className="text-xs text-slate-400 desc-glow">
          Your streak is computed from your real activity — answers, SQL practice, teach-backs, and mentor sessions. You cannot add it manually.
        </p>
      </div>

      <div className="card p-6 space-y-4" id="t03-adaptations-panel">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <SectionTitle
            title="What SAARTHI has adapted for you"
            subtitle="Based on your 'Too easy', 'Too hard', and 'Helped' feedback, SAARTHI adjusts practice pacing and teaching approaches."
          />
          <button className="btn btn-secondary btn-sm" onClick={resetAdaptations}>Reset to defaults</button>
        </div>
        <div className="space-y-4 text-sm pt-1">
          <div>
            <b className="text-[#4D9DFF] text-xs uppercase tracking-wider block mb-2">Practice Pacing by Domain</b>
            {adaptations && Object.keys(adaptations.practice_factors || {}).length > 0 ? (
              <div className="grid sm:grid-cols-2 gap-2.5">
                {Object.entries(adaptations.practice_factors).map(([dom, factor]) => (
                  <div key={dom} className="glass-row p-3 flex justify-between items-center">
                    <span className="font-semibold text-white capitalize">{dom}</span>
                    <span className="chip" style={{ background: 'rgba(77, 157, 255, 0.15)', color: '#4D9DFF', border: '1px solid rgba(77, 157, 255, 0.3)' }}>
                      {factor.toFixed(1)}x {factor > 2.0 ? '(extra time)' : factor < 2.0 ? '(accelerated)' : '(default)'}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-slate-400 desc-glow">Default pacing active ({adaptations?.default_factor ?? 2.0}x practice factor across all domains).</div>
            )}
          </div>

          {adaptations && Object.keys(adaptations.helpful_strategies || {}).length > 0 && (
            <div>
              <b className="text-[#35D07F] text-xs uppercase tracking-wider block mb-2">Preferred Teaching Approaches</b>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(adaptations.helpful_strategies).map(([strat, count]) => (
                  <span key={strat} className="chip" style={{ background: 'rgba(53, 208, 127, 0.15)', color: '#35D07F', border: '1px solid rgba(53, 208, 127, 0.3)' }}>
                    {strat.replace(/_/g, ' ')} ({count}x helped)
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card p-6 space-y-4">
        <SectionTitle
          title="Data & Privacy Controls"
          subtitle="Audio streams are processed in-flight and never stored; only verified text transcripts persist."
        />
        <div className="flex gap-3 flex-wrap pt-1">
          <button className="btn btn-secondary text-sm flex items-center gap-2" onClick={exportData}>
            <Download className="w-4 h-4 text-[#4D9DFF]" />
            Export My Data (JSON)
          </button>
          <button
            className="btn btn-secondary text-sm flex items-center gap-2 text-[#FF5364] hover:bg-[rgba(255,83,100,0.15)] border-[rgba(255,83,100,0.3)]"
            onClick={del}
          >
            <Trash2 className="w-4 h-4 text-[#FF5364]" />
            Delete Account & History
          </button>
        </div>
      </div>

      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <SectionTitle
            title="Service Adapters & Telemetry"
            subtitle="Current architecture subsystem health and model backends."
          />
          <DemoBadge label="system" />
        </div>
        <ul className="text-sm space-y-2 pt-1">
          {['auth', 'mentors', 'consent', 'cohort'].map(k => (
            <li key={k} className="flex items-center justify-between p-2.5 rounded-lg bg-[rgba(15,25,35,0.30)] border border-[var(--border-subtle)]">
              <span className="capitalize font-medium text-[var(--text-primary)] flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                {k} Adapter
              </span>
              {health?.adapters?.[k] === 'mock' ? (
                <span className="chip" style={{ background: 'rgba(255, 138, 36, 0.15)', color: 'var(--accent-orange)', border: '1px solid rgba(255, 138, 36, 0.3)' }}>
                  mock
                </span>
              ) : (
                <span className="chip" style={{ background: 'rgba(53, 208, 127, 0.15)', color: '#35D07F', border: '1px solid rgba(53, 208, 127, 0.3)' }}>
                  live ({health?.adapters?.[k]})
                </span>
              )}
            </li>
          ))}
          <li className="flex items-center justify-between p-2.5 rounded-lg bg-[rgba(15,25,35,0.30)] border border-[var(--border-subtle)]">
            <span className="font-medium text-[var(--text-primary)] flex items-center gap-2">
              <Cpu className="w-3.5 h-3.5 text-[#4D9DFF]" />
              Gemini LLM
            </span>
            <span
              className="chip"
              style={{
                background: health?.llm?.available ? 'rgba(53, 208, 127, 0.15)' : 'rgba(255, 83, 100, 0.15)',
                color: health?.llm?.available ? '#35D07F' : '#FF5364',
                border: `1px solid ${health?.llm?.available ? 'rgba(53, 208, 127, 0.3)' : 'rgba(255, 83, 100, 0.3)'}`
              }}
            >
              {health?.llm?.available ? health.llm.model : 'not configured'}
            </span>
          </li>
          <li className="flex items-center justify-between p-2.5 rounded-lg bg-[rgba(15,25,35,0.30)] border border-[var(--border-subtle)]">
            <span className="font-medium text-[var(--text-primary)] flex items-center gap-2">
              <Globe className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
              ElevenLabs Voice Suite
            </span>
            <div className="flex gap-1.5 flex-wrap">
              <span
                className="chip"
                style={{
                  background: health?.voice?.agent_ready ? 'rgba(53, 208, 127, 0.15)' : 'rgba(255, 83, 100, 0.15)',
                  color: health?.voice?.agent_ready ? '#35D07F' : '#FF5364',
                  border: `1px solid ${health?.voice?.agent_ready ? 'rgba(53, 208, 127, 0.3)' : 'rgba(255, 83, 100, 0.3)'}`
                }}
              >
                {health?.voice?.agent_ready ? 'agent online' : 'agent offline'}
              </span>
              <span className="chip" style={{ background: health?.voice?.tts_ready ? 'rgba(53, 208, 127, 0.15)' : 'rgba(255,255,255,0.05)', color: health?.voice?.tts_ready ? '#35D07F' : 'var(--text-muted)' }}>
                TTS
              </span>
              <span className="chip" style={{ background: health?.voice?.stt_ready ? 'rgba(53, 208, 127, 0.15)' : 'rgba(255,255,255,0.05)', color: health?.voice?.stt_ready ? '#35D07F' : 'var(--text-muted)' }}>
                STT
              </span>
            </div>
          </li>
        </ul>
      </div>

      {health?.env !== 'prod' && (
        <div className="card p-6 space-y-4 border-dashed border-[rgba(255,138,36,0.35)] bg-[rgba(20,32,44,0.30)]">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <SectionTitle eyebrow="Developer Tools" title="Time-Travel & Scenario Simulation" />
            <DemoBadge label="dev only" title="Hidden when SAARTHI_ENV=prod" />
          </div>
          <Callout tone="saffron">
            These scenario controls allow demonstration of multi-day retention decay and struggle escalations instantaneously. All mutations are tagged as <i>simulated</i> in your learner genome.
          </Callout>

          <div className="grid sm:grid-cols-2 gap-4 pt-1">
            <div className="space-y-2 p-3.5 rounded-xl bg-[rgba(15,25,35,0.30)] border border-[var(--border-subtle)]">
              <label className="text-xs font-semibold text-[var(--text-secondary)] block">Fast-forward timeline</label>
              <div className="flex gap-2">
                <input
                  className="input w-24 bg-[rgba(10,20,30,0.40)] text-[var(--text-primary)]"
                  type="number"
                  min={1}
                  value={days}
                  onChange={e => setDays(+e.target.value)}
                />
                <button
                  className="btn btn-secondary text-xs flex-1 flex items-center justify-center gap-1.5"
                  onClick={async () => {
                    const r = await api.devAdvance(days)
                    setOut(r.roadmap.reason)
                    bump()
                    refreshMe()
                  }}
                >
                  <FastForward className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
                  Advance {days}d
                </button>
              </div>
            </div>

            <div className="space-y-2 p-3.5 rounded-xl bg-[rgba(15,25,35,0.30)] border border-[var(--border-subtle)]">
              <label className="text-xs font-semibold text-[var(--text-secondary)] block">Simulate persistent struggle</label>
              <div className="flex gap-2">
                <input
                  className="input flex-1 bg-[rgba(10,20,30,0.40)] text-xs text-[var(--text-primary)]"
                  value={concept}
                  onChange={e => setConcept(e.target.value)}
                />
                <button
                  className="btn btn-secondary text-xs flex items-center gap-1.5"
                  onClick={async () => {
                    const r = await api.devStruggle(concept)
                    setOut(JSON.stringify(r.after.escalation_suggestions.map((s: any) => s.reason)))
                    bump()
                  }}
                >
                  <Flame className="w-3.5 h-3.5 text-[#FF5364]" />
                  Simulate
                </button>
              </div>
            </div>
          </div>

          <div className="flex gap-3 flex-wrap pt-2 border-t border-[var(--border-subtle)]">
            <button
              className="btn btn-secondary text-xs flex items-center gap-1.5"
              onClick={async () => {
                await api.devSeedDemo()
                bump()
                toast('Demo baseline seeded.')
              }}
            >
              <Database className="w-3.5 h-3.5 text-[#4D9DFF]" />
              Seed Demo State
            </button>
            <button
              className="btn btn-secondary text-xs flex items-center gap-1.5 text-[#FF5364] border-[rgba(255,83,100,0.3)] hover:bg-[rgba(255,83,100,0.1)]"
              onClick={async () => {
                if (confirm('Reset all your learning progress?')) {
                  await api.devReset()
                  bump()
                  toast('Progress reset.')
                }
              }}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset All Progress
            </button>
          </div>

          {out && (
            <div className="text-xs bg-[rgba(10,20,30,0.55)] border border-[var(--border-subtle)] rounded-lg p-3 font-mono text-[var(--accent-orange)] break-words">
              {out}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

