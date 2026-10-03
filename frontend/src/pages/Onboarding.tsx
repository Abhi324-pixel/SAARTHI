import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { apiT01, IntakeTurnResponse } from '../api_ext/T01'
import { MicButton } from '../components/audio'
import { Callout } from '../components/ui'
import { useApp } from '../store'

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

  useEffect(() => { api.roles().then(setRoles).catch(() => {}) }, [])
  useEffect(() => { if (me?.language) setLang(me.language) }, [me?.language])

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
    <div className="min-h-full flex items-center justify-center p-4">
      <div className="card p-6 sm:p-8 w-full max-w-3xl space-y-6">
        <div>
          <div className="eyebrow">Step 1 of 2</div>
          <h1 className="h-page">Namaste{me?.name ? `, ${me.name.split(' ')[0]}` : ''}! What do you want to become?</h1>
          <p className="text-muted mt-1">
            SAARTHI builds a skill graph for your goal, then finds out what you actually know — not what you think you know.
          </p>
        </div>

        {/* T01: Free-text Conversational Intake Card */}
        <div className="p-4 rounded-2xl bg-paper/70 border border-line space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-teal uppercase tracking-wide">
              {t('T01.intake.title')}
            </span>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-muted hidden sm:inline">Voice or text</span>
              <MicButton onText={txt => { setGoalText(prev => prev ? `${prev} ${txt}` : txt) }} />
            </div>
          </div>

          <textarea
            className="input w-full text-sm min-h-[75px] resize-y"
            placeholder="e.g. I want to become a backend developer in 4 months, 8 hours a week, I know basic Python and some SQL, explain in Hinglish..."
            value={goalText}
            onChange={e => setGoalText(e.target.value)}
          />

          <div className="flex items-center justify-between gap-2 flex-wrap">
            <button
              type="button"
              disabled={intakeBusy || !goalText.trim()}
              onClick={() => handleIntakeSubmit()}
              className="btn btn-secondary text-xs py-1.5 px-3"
            >
              {intakeBusy ? 'Understanding…' : '✨ Parse my goal'}
            </button>
            <span className="text-[11px] text-muted">Or configure directly below</span>
          </div>

          {/* Fallback alert if LLM is unavailable */}
          {intakeData?.unavailable && (
            <Callout tone="saffron" title="Offline mode">
              {intakeData.message || t('T01.intake.fallback')}
            </Callout>
          )}

          {/* Understood Chips & Confirmation */}
          {intakeData && !intakeData.unavailable && intakeData.understood && (
            <div className="p-3.5 bg-paper rounded-xl border border-line space-y-3 mt-2">
              <div className="flex items-center justify-between">
                <span className="font-extrabold text-navy text-xs">{t('T01.intake.understood')}</span>
                <span className="text-[10px] text-muted">Confidence: {Math.round(intakeData.understood.confidence * 100)}%</span>
              </div>

              {intakeData.understood.goal_text && (
                <div className="text-xs italic text-muted">
                  "{intakeData.understood.goal_text}"
                </div>
              )}

              {intakeData.unavailable_role && (
                <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/30 border border-amber-200 text-xs text-amber-900 dark:text-amber-200">
                  <b>{intakeData.unavailable_role}</b> is not available yet. The closest role we have is <b>Backend Developer</b> (SQL is shared), so we've selected that for you!
                </div>
              )}

              {/* Extracted constraint chips */}
              <div className="flex flex-wrap gap-1.5 text-xs">
                {intakeData.understood.role_title && (
                  <span className="chip bg-blue-100 text-blue-900 font-semibold">
                    🎯 Role: {intakeData.understood.role_title}
                  </span>
                )}
                {intakeData.understood.weekly_hours && (
                  <span className="chip bg-amber-100 text-amber-900 font-semibold">
                    ⏱ {intakeData.understood.weekly_hours} hrs/wk
                  </span>
                )}
                {intakeData.understood.horizon_weeks && (
                  <span className="chip bg-emerald-100 text-emerald-900 font-semibold">
                    📅 {intakeData.understood.horizon_weeks} weeks
                  </span>
                )}
                {intakeData.understood.language && (
                  <span className="chip bg-purple-100 text-purple-900 font-semibold">
                    🌐 {intakeData.understood.language}
                  </span>
                )}
              </div>

              {/* Claimed skills */}
              {intakeData.understood.known_skills && intakeData.understood.known_skills.length > 0 && (
                <div className="space-y-1 text-xs pt-1 border-t border-line">
                  <div className="text-[11px] text-muted font-semibold">Prior experience claims (tested first in placement):</div>
                  <div className="flex flex-wrap gap-1">
                    {intakeData.understood.known_skills.map((s, i) => (
                      <span key={i} className="chip bg-teal/10 text-teal font-medium text-[11px]">
                        ✓ {s.concept_name} ({s.phrase})
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Follow-up question if any */}
              {intakeData.follow_up && (
                <div className="p-2.5 rounded-lg bg-blue-50/70 dark:bg-blue-950/20 border border-blue-200 space-y-2 text-xs">
                  <div className="font-semibold text-navy">SAARTHI asks: {intakeData.follow_up}</div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      className="input text-xs py-1 px-2 flex-1"
                      placeholder="e.g. 8 hours a week"
                      value={followUpReply}
                      onChange={e => setFollowUpReply(e.target.value)}
                    />
                    <button
                      type="button"
                      disabled={intakeBusy || !followUpReply.trim()}
                      onClick={() => {
                        const reply = followUpReply.trim()
                        setFollowUpReply('')
                        handleIntakeSubmit(reply)
                      }}
                      className="btn btn-secondary text-xs py-1 px-3"
                    >
                      Answer
                    </button>
                  </div>
                </div>
              )}

              <div className="pt-2">
                <button
                  type="button"
                  onClick={handleConfirmIntake}
                  disabled={busy}
                  className="btn btn-primary text-xs w-full py-2"
                >
                  {busy ? 'Setting up…' : t('T01.intake.confirm')}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Standard Manual Configuration Controls (always functional) */}
        <div className="space-y-4 pt-2 border-t border-line">
          <div className="text-xs font-bold text-muted uppercase tracking-wide">
            Role & Schedule Configuration
          </div>

          <div className="grid sm:grid-cols-3 gap-3" role="radiogroup" aria-label="Target role">
            {roles.map(r => (
              <button
                key={r.id}
                role="radio"
                aria-checked={role === r.id}
                disabled={!r.available}
                onClick={() => setRole(r.id)}
                className={`text-left rounded-2xl border p-4 transition ${
                  role === r.id ? 'border-saffron bg-saffron-soft ring-2 ring-saffron/30' : 'border-line bg-white'
                } ${!r.available ? 'opacity-50' : 'hover:bg-paper'}`}
              >
                <div className="font-extrabold text-navy">{r.title}</div>
                <div className="text-xs text-muted mt-1">{r.available ? r.blurb : 'Coming soon'}</div>
              </button>
            ))}
          </div>

          <div className="grid sm:grid-cols-2 gap-6">
            <label className="block text-sm font-semibold">
              Hours per week: <b className="text-saffron">{hours}</b>
              <input
                type="range"
                min={2}
                max={30}
                value={hours}
                onChange={e => setHours(+e.target.value)}
                className="w-full accent-[#e07a1f] mt-2"
              />
            </label>
            <label className="block text-sm font-semibold">
              Weeks available: <b className="text-saffron">{weeks}</b>
              <input
                type="range"
                min={4}
                max={40}
                value={weeks}
                onChange={e => setWeeks(+e.target.value)}
                className="w-full accent-[#e07a1f] mt-2"
              />
            </label>
          </div>

          <label className="block text-sm font-semibold max-w-xs">
            I want to talk in
            <select translate="no"
              className="input mt-1"
              value={lang}
              onChange={e => setLang(e.target.value)}
            >
              <option value="english">English</option>
              <option value="hindi">हिन्दी</option>
              <option value="hinglish">Hinglish</option>
            </select>
          </label>
        </div>

        <div className="rounded-xl bg-paper p-4 text-sm leading-relaxed">
          <b className="text-navy">What happens next:</b> a short placement of 8 questions. Before each answer you'll say how sure you are — a confident wrong answer tells SAARTHI more than a lucky guess. You'll see your skill graph fill in and your roadmap appear.
        </div>

        <button
          className="btn btn-saffron w-full sm:w-auto py-3 px-8 text-base"
          onClick={go}
          disabled={busy}
        >
          {busy ? 'Setting up…' : 'Start my placement →'}
        </button>
      </div>
    </div>
  )
}
