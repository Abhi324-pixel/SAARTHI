import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { apiT01, IntakeTurnResponse } from '../api_ext/T01'
import { MicButton } from '../components/audio'
import { Callout } from '../components/ui'
import { useApp } from '../store'
import { Compass, Sparkles, ArrowRight, Clock, Calendar, Check, Bot } from 'lucide-react'

export default function Onboarding() {
  const { me, refreshMe, toast, t } = useApp()
  const nav = useNavigate()
  const [roles, setRoles] = useState<any[]>([])
  const [role, setRole] = useState('backend_developer')
  const [hours, setHours] = useState(6)
  const [weeks, setWeeks] = useState(12)
  const [lang, setLang] = useState(me?.language ?? 'hinglish')
  const [busy, setBusy] = useState(false)

  // T01 Intake states
  const [goalText, setGoalText] = useState('')
  const [intakeBusy, setIntakeBusy] = useState(false)
  const [intakeData, setIntakeData] = useState<IntakeTurnResponse | null>(null)
  const [followUpReply, setFollowUpReply] = useState('')

  useEffect(() => {
    api.roles().then(setRoles).catch(() => {})
  }, [])

  useEffect(() => {
    if (me?.language) setLang(me.language)
  }, [me?.language])

  async function handleIntakeSubmit(messageToSend?: string) {
    const msg = (messageToSend ?? goalText).trim()
    if (!msg) return
    setIntakeBusy(true)
    try {
      const res = await apiT01.turn(msg)
      setIntakeData(res)

      if (res.unavailable) {
        toast(res.message || t('T01.intake.fallback'), 'warn')
        return
      }

      // Sync extracted constraints into form state
      if (res.understood?.role_id) {
        setRole(res.understood.role_id)
      }
      if (res.understood?.weekly_hours) {
        setHours(Math.round(res.understood.weekly_hours))
      }
      if (res.understood?.horizon_weeks) {
        setWeeks(Math.round(res.understood.horizon_weeks))
      }
      if (res.understood?.language) {
        setLang(res.understood.language)
      }

      if (res.unavailable_role) {
        toast(`${res.unavailable_role} is not available yet. We selected Backend Developer!`, 'warn')
      } else {
        toast('Goal understood! Review the details below.', 'ok')
      }
    } catch (e: any) {
      toast(e.message || 'Could not parse goal', 'err')
    } finally {
      setIntakeBusy(false)
    }
  }

  async function handleConfirmIntake() {
    setBusy(true)
    try {
      await apiT01.confirm({
        role_id: role,
        weekly_hours: hours,
        horizon_weeks: weeks,
        language: lang,
        goal_text: intakeData?.understood?.goal_text || goalText || undefined,
        known_skills: intakeData?.understood?.known_skills || [],
      })
      await refreshMe()
      nav('/placement')
    } catch (e: any) {
      toast(e.message, 'err')
    } finally {
      setBusy(false)
    }
  }

  async function go() {
    setBusy(true)
    try {
      await api.onboard({ role_id: role, weekly_hours: hours, horizon_weeks: weeks, language: lang })
      await refreshMe()
      nav('/placement')
    } catch (e: any) {
      toast(e.message, 'err')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-full flex items-center justify-center p-4 sm:p-6 my-auto">
      <div className="card p-6 sm:p-10 w-full max-w-3xl space-y-7 shadow-[0_16px_48px_rgba(0,0,0,0.4)]">
        <div className="space-y-2">
          <div className="eyebrow flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
            Step 1 of 2 · Goal Definition
          </div>
          <h1 className="h-page heading-glow text-2xl sm:text-3xl">
            Namaste{me?.name ? `, ${me.name.split(' ')[0]}` : ''}! What is your target role?
          </h1>
          <p className="desc-glow text-[var(--text-secondary)] text-sm sm:text-base leading-relaxed">
            SAARTHI constructs a tailored skill graph for your objective, then runs diagnostic probes to map what you actually know — distinguishing solid mental models from fragile memorization.
          </p>
        </div>

        {/* T01: Free-text Conversational Intake Card */}
        <div className="p-5 rounded-2xl bg-[rgba(15,25,35,0.45)] border border-[rgba(210,225,235,0.16)] space-y-3.5 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#4D9DFF] uppercase tracking-wide flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5" />
              {t('T01.intake.title')}
            </span>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-slate-400 desc-glow hidden sm:inline">Voice or text</span>
              <MicButton onText={txt => { setGoalText(prev => prev ? `${prev} ${txt}` : txt) }} />
            </div>
          </div>

          <textarea
            className="input w-full text-sm min-h-[85px] resize-y bg-[rgba(10,20,30,0.45)] border-[var(--border-subtle)] focus:border-[var(--accent-orange)] text-[var(--text-primary)] rounded-xl"
            placeholder="e.g. I want to become a backend developer in 4 months, 8 hours a week, I know basic Python and some SQL, explain in Hinglish..."
            value={goalText}
            onChange={e => setGoalText(e.target.value)}
          />

          <div className="flex items-center justify-between gap-2 flex-wrap">
            <button
              type="button"
              disabled={intakeBusy || !goalText.trim()}
              onClick={() => handleIntakeSubmit()}
              className="btn btn-secondary text-xs py-2 px-4 flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 text-[var(--accent-orange)]" />
              {intakeBusy ? 'Understanding…' : '✨ Parse my goal'}
            </button>
            <span className="text-[11px] text-slate-400 desc-glow">Or configure directly below</span>
          </div>

          {/* Fallback alert if LLM is unavailable */}
          {intakeData?.unavailable && (
            <Callout tone="saffron" title="Offline mode">
              {intakeData.message || t('T01.intake.fallback')}
            </Callout>
          )}

          {/* Understood Chips & Confirmation */}
          {intakeData && !intakeData.unavailable && intakeData.understood && (
            <div className="p-4 bg-[rgba(20,32,44,0.7)] rounded-xl border border-[rgba(210,225,235,0.14)] space-y-3 mt-2">
              <div className="flex items-center justify-between">
                <span className="font-extrabold text-white text-xs heading-glow">{t('T01.intake.understood')}</span>
                <span className="text-[10px] text-slate-400 font-mono">Confidence: {Math.round(intakeData.understood.confidence * 100)}%</span>
              </div>

              {intakeData.understood.goal_text && (
                <div className="text-xs italic text-slate-300 desc-glow">
                  "{intakeData.understood.goal_text}"
                </div>
              )}

              {intakeData.unavailable_role && (
                <div className="p-2.5 rounded-lg bg-[rgba(255,181,46,0.12)] border border-[rgba(255,181,46,0.3)] text-xs text-[#FFB52E]">
                  <b>{intakeData.unavailable_role}</b> is not available yet. The closest role we have is <b>Backend Developer</b> (SQL is shared), so we've selected that for you!
                </div>
              )}

              {/* Extracted constraint chips */}
              <div className="flex flex-wrap gap-1.5 text-xs">
                {intakeData.understood.role_title && (
                  <span className="chip" style={{ background: 'rgba(77, 157, 255, 0.15)', color: '#4D9DFF', border: '1px solid rgba(77, 157, 255, 0.3)' }}>
                    🎯 Role: {intakeData.understood.role_title}
                  </span>
                )}
                {intakeData.understood.weekly_hours && (
                  <span className="chip" style={{ background: 'rgba(255, 138, 36, 0.15)', color: '#FF8A24', border: '1px solid rgba(255, 138, 36, 0.3)' }}>
                    ⏱ {intakeData.understood.weekly_hours} hrs/wk
                  </span>
                )}
                {intakeData.understood.horizon_weeks && (
                  <span className="chip" style={{ background: 'rgba(53, 208, 127, 0.15)', color: '#35D07F', border: '1px solid rgba(53, 208, 127, 0.3)' }}>
                    📅 {intakeData.understood.horizon_weeks} weeks
                  </span>
                )}
                {intakeData.understood.language && (
                  <span className="chip" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#C084FC', border: '1px solid rgba(168, 85, 247, 0.3)' }}>
                    🌐 {intakeData.understood.language}
                  </span>
                )}
              </div>

              {/* Claimed skills */}
              {intakeData.understood.known_skills && intakeData.understood.known_skills.length > 0 && (
                <div className="space-y-1 text-xs pt-1 border-t border-[rgba(210,225,235,0.12)]">
                  <div className="text-[11px] text-slate-400 font-semibold desc-glow">Prior experience claims (tested first in placement):</div>
                  <div className="flex flex-wrap gap-1">
                    {intakeData.understood.known_skills.map((s, i) => (
                      <span key={i} className="chip text-[11px]" style={{ background: 'rgba(53, 208, 127, 0.12)', color: '#35D07F' }}>
                        ✓ {s.concept_name} ({s.phrase})
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Follow-up question if any */}
              {intakeData.follow_up && (
                <div className="p-3 bg-[rgba(10,20,30,0.5)] rounded-lg border border-[rgba(77,157,255,0.25)] space-y-2 mt-2">
                  <div className="text-xs font-semibold text-[#4D9DFF] flex items-center gap-1">
                    <span>💬</span>
                    <span>{typeof intakeData.follow_up === 'string' ? intakeData.follow_up : (intakeData.follow_up as any)?.question}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      className="input text-xs py-1.5 flex-1 bg-[rgba(15,25,35,0.40)] border-[var(--border-subtle)]"
                      placeholder="Answer to refine your plan..."
                      value={followUpReply}
                      onChange={e => setFollowUpReply(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && followUpReply.trim()) {
                          handleIntakeSubmit(followUpReply)
                          setFollowUpReply('')
                        }
                      }}
                    />
                    <button
                      type="button"
                      disabled={intakeBusy || !followUpReply.trim()}
                      onClick={() => {
                        handleIntakeSubmit(followUpReply)
                        setFollowUpReply('')
                      }}
                      className="btn btn-secondary text-xs py-1 px-3"
                    >
                      Reply
                    </button>
                  </div>
                </div>
              )}

              {/* Direct confirm with parsed intake button */}
              <div className="pt-2 border-t border-[rgba(210,225,235,0.12)]">
                <button
                  type="button"
                  onClick={handleConfirmIntake}
                  disabled={busy}
                  className="btn btn-orange text-xs w-full py-2.5 font-semibold flex items-center justify-center gap-2"
                >
                  {busy ? 'Setting up…' : t('T01.intake.confirm')}
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Standard Manual Configuration Controls */}
        <div className="space-y-4 pt-2 border-t border-[rgba(210,225,235,0.12)]">
          <label className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">
            Select Track
          </label>
          <div className="grid sm:grid-cols-3 gap-3" role="radiogroup" aria-label="Target role">
            {roles.map(r => {
              const selected = role === r.id
              return (
                <button
                  key={r.id}
                  role="radio"
                  aria-checked={selected}
                  disabled={!r.available}
                  onClick={() => setRole(r.id)}
                  className={`text-left rounded-2xl border p-4.5 transition-all relative ${
                    selected
                      ? 'border-[var(--accent-orange)] bg-[rgba(255,138,36,0.12)] shadow-[0_0_20px_rgba(255,138,36,0.18)]'
                      : 'border-[var(--border-subtle)] bg-[rgba(15,25,35,0.35)] hover:border-[var(--border-medium)] hover:bg-[rgba(20,32,44,0.45)]'
                  } ${!r.available ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <div className="flex items-start justify-between gap-1 mb-1.5">
                    <div className="font-extrabold text-[var(--text-primary)] text-sm sm:text-base">
                      {r.title}
                    </div>
                    {selected && (
                      <span className="w-4 h-4 rounded-full bg-[var(--accent-orange)] text-white flex items-center justify-center text-[10px] shrink-0">
                        <Check className="w-2.5 h-2.5" />
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-[var(--text-secondary)] desc-glow line-clamp-3">
                    {r.available ? r.blurb : 'Curriculum mapping underway'}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-6 p-4 rounded-2xl bg-[rgba(15,25,35,0.30)] border border-[var(--border-subtle)]">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm font-semibold">
              <span className="text-[var(--text-secondary)] flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-[var(--accent-orange)]" />
                Weekly Commitment
              </span>
              <b className="text-[var(--accent-orange)] font-mono text-base">{hours} hrs/wk</b>
            </div>
            <input
              type="range"
              min={2}
              max={30}
              value={hours}
              onChange={e => setHours(+e.target.value)}
              className="w-full accent-[var(--accent-orange)] cursor-pointer"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm font-semibold">
              <span className="text-[var(--text-secondary)] flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-[var(--accent-orange)]" />
                Target Horizon
              </span>
              <b className="text-[var(--accent-orange)] font-mono text-base">{weeks} weeks</b>
            </div>
            <input
              type="range"
              min={4}
              max={40}
              value={weeks}
              onChange={e => setWeeks(+e.target.value)}
              className="w-full accent-[var(--accent-orange)] cursor-pointer"
            />
          </div>
        </div>

        <div className="max-w-xs space-y-1.5">
          <label className="block text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
            Instruction & Dialogue Language
          </label>
          <select translate="no"
            className="input bg-[rgba(15,25,35,0.40)] border-[var(--border-subtle)] text-[var(--text-primary)] rounded-xl"
            value={lang}
            onChange={e => setLang(e.target.value)}
          >
            <option value="english">English (Global standard)</option>
            <option value="hindi">हिन्दी (Hindi)</option>
            <option value="hinglish">Hinglish (Colloquial tech conversation)</option>
          </select>
        </div>

        <div className="rounded-xl bg-[rgba(15,25,35,0.30)] border border-[rgba(77,157,255,0.22)] p-4 text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)] flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-[#4D9DFF] shrink-0 mt-0.5" />
          <div>
            <b className="text-[var(--text-primary)]">What follows next:</b> An adaptive 8-question placement diagnostic. Before each question you'll indicate your confidence level — a high-confidence mistake provides crucial signal to your learner twin to address deep misconceptions immediately.
          </div>
        </div>

        <button
          className="btn btn-orange w-full sm:w-auto py-3 px-8 text-sm sm:text-base font-semibold flex items-center justify-center gap-2 shadow-[0_6px_20px_rgba(255,120,30,0.28)]"
          onClick={go}
          disabled={busy}
        >
          {busy ? 'Configuring Twin…' : 'Start My Diagnostic Placement'}
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
