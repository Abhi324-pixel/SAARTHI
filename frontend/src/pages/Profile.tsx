import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { apiC06, type ProfileResponse } from '../api_ext/C06'
import { Callout, DemoBadge, SectionTitle, Spinner } from '../components/ui'
import { useApp } from '../store'

const EDUCATION_OPTIONS = [
  { value: '', label: 'Select education level…' },
  { value: 'school_9_12', label: 'School (Class 9–12)' },
  { value: 'diploma', label: 'Diploma / Polytechnic' },
  { value: 'undergraduate', label: 'Undergraduate (College / University)' },
  { value: 'postgraduate', label: 'Postgraduate' },
  { value: 'working', label: 'Working Professional' },
  { value: 'other', label: 'Other' },
]

function getInitials(name: string): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function getAvatarColor(str: string): { bg: string; text: string } {
  const palette = [
    { bg: '#e07a1f', text: '#ffffff' },
    { bg: '#16324f', text: '#ffffff' },
    { bg: '#1f7a7a', text: '#ffffff' },
    { bg: '#7b1fa2', text: '#ffffff' },
    { bg: '#2e7d32', text: '#ffffff' },
    { bg: '#c2185b', text: '#ffffff' },
    { bg: '#0288d1', text: '#ffffff' },
    { bg: '#d84315', text: '#ffffff' },
  ]
  let hash = 0
  for (let i = 0; i < (str || '').length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i)
    hash |= 0
  }
  return palette[Math.abs(hash) % palette.length]
}

function maskEmail(email: string): string {
  if (!email || !email.includes('@')) return '••••••••'
  const [user, domain] = email.split('@')
  if (user.length <= 2) return `${user[0]}***@${domain}`
  return `${user.slice(0, 2)}***@${domain}`
}

export default function Profile() {
  const { me, refreshMe, toast, logout, t } = useApp()
  const nav = useNavigate()

  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<ProfileResponse | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [showEmail, setShowEmail] = useState(false)

  // Form fields
  const [name, setName] = useState('')
  const [education, setEducation] = useState('')
  const [institution, setInstitution] = useState('')
  const [goalText, setGoalText] = useState('')

  // Transcript sharing state
  const [transcriptShare, setTranscriptShare] = useState(false)

  useEffect(() => {
    loadProfile()
  }, [])

  async function loadProfile() {
    setLoading(true)
    try {
      const res = await apiC06.getProfile()
      setData(res)
      setName(res.profile.name || '')
      setEducation(res.profile.education || '')
      setInstitution(res.profile.institution || '')
      setGoalText(res.profile.goal_text || '')
      setTranscriptShare(res.consent?.transcript_share === 'granted')
    } catch (e: any) {
      toast(e.message || 'Failed to load profile', 'err')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      toast('Name is required', 'warn')
      return
    }
    setSaving(true)
    try {
      const res = await apiC06.updateProfile({
        name: name.trim(),
        education: education || null,
        institution: institution.trim() || null,
        goal_text: goalText.trim() || null,
      })
      setData(res)
      setName(res.profile.name || '')
      setEducation(res.profile.education || '')
      setInstitution(res.profile.institution || '')
      setGoalText(res.profile.goal_text || '')
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
      await refreshMe()
      toast(t('C06.saved'))
    } catch (err: any) {
      toast(err.message || 'Update failed', 'err')
    } finally {
      setSaving(false)
    }
  }

  async function toggleTranscriptSharing(checked: boolean) {
    try {
      if (checked) {
        await api.consentSelf('transcript_share')
        setTranscriptShare(true)
        toast('Transcript sharing enabled for mentor cases')
      } else {
        await api.consentRevoke('transcript_share')
        setTranscriptShare(false)
        toast('Transcript sharing disabled')
      }
      // Refresh consent in state
      const fresh = await apiC06.getProfile()
      setData(fresh)
    } catch (e: any) {
      toast(e.message || 'Could not update transcript preference', 'err')
    }
  }

  async function exportData() {
    try {
      const exportJson = await api.exportMe()
      const blob = new Blob([JSON.stringify(exportJson, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `saarthi-profile-${data?.profile?.name ? data.profile.name.toLowerCase().replace(/\s+/g, '_') : 'export'}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      toast(e.message || 'Data export failed', 'err')
    }
  }

  async function deleteAccount() {
    if (!confirm('Are you absolutely sure you want to delete your profile and all learning progress? This action is permanent and cannot be undone.')) {
      return
    }
    try {
      await api.deleteMe()
      logout()
      nav('/login')
    } catch (e: any) {
      toast(e.message || 'Account deletion failed', 'err')
    }
  }

  if (loading || !data) {
    return (
      <div className="py-20 flex justify-center items-center">
        <Spinner label="Loading learner profile…" />
      </div>
    )
  }

  const { profile, stats, consent, what_mentors_see } = data
  const avatarStyle = getAvatarColor(profile.name || me?.id || 'learner')

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div className="eyebrow">Parichay · परिचय</div>
          <h1 className="h-page">{t('C06.profile.title')}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/genome" className="btn btn-ghost btn-sm">
            My Genome →
          </Link>
          <Link to="/settings" className="btn btn-ghost btn-sm">
            Settings
          </Link>
        </div>
      </div>

      {/* Card 1: Identity & Profile Details */}
      <div className="card p-6 space-y-5" id="c06-identity-card">
        <div className="flex items-center justify-between gap-3 flex-wrap border-b border-line pb-4">
          <div className="flex items-center gap-4">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center font-extrabold text-2xl shadow-sm select-none"
              style={{ background: avatarStyle.bg, color: avatarStyle.text }}
              aria-label={`Avatar initials for ${profile.name}`}
            >
              {getInitials(profile.name)}
            </div>
            <div>
              <div className="text-xl font-bold text-navy flex items-center gap-2">
                {profile.name}
                {profile.is_minor && (
                  <span className="chip" style={{ background: '#fdf3e9', color: '#9a4f0a' }}>
                    Minor (under 18)
                  </span>
                )}
              </div>
              <div className="text-xs text-muted mt-0.5 flex items-center gap-2 flex-wrap">
                <span>Role: <b className="text-navy">{profile.role_title || 'Learner'}</b></span>
                <span>·</span>
                <span>Member since: <b className="text-navy">{stats.member_since}</b></span>
              </div>
            </div>
          </div>

          <div className="text-right text-xs text-muted">
            <div>
              Email:{' '}
              {showEmail ? (
                <span className="font-mono text-navy font-semibold">{profile.email}</span>
              ) : (
                <span className="font-mono">{maskEmail(profile.email)}</span>
              )}
              <button
                type="button"
                onClick={() => setShowEmail(!showEmail)}
                className="ml-2 text-teal underline font-semibold"
              >
                {showEmail ? 'Hide' : 'Reveal'}
              </button>
            </div>
            <div className="mt-0.5">
              Age: <span className="font-semibold text-navy">{profile.age}</span> (immutable)
            </div>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <SectionTitle title={t('C06.identity')} />

          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block text-sm font-semibold">
              Full Name *
              <input
                id="c06-name-input"
                type="text"
                required
                maxLength={80}
                value={name}
                onChange={e => setName(e.target.value)}
                className="input mt-1 w-full"
                placeholder="Your full name"
              />
            </label>

            <label className="block text-sm font-semibold">
              Education Level
              <select
                id="c06-education-select"
                value={education}
                onChange={e => setEducation(e.target.value)}
                className="input mt-1 w-full"
              >
                {EDUCATION_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block text-sm font-semibold">
              School / College / Institution
              <input
                id="c06-institution-input"
                type="text"
                maxLength={80}
                value={institution}
                onChange={e => setInstitution(e.target.value)}
                className="input mt-1 w-full"
                placeholder="e.g. Govt Engineering College, Delhi University"
              />
              <span className="text-[11px] text-muted block mt-0.5">
                Up to 80 characters. Optional.
              </span>
            </label>

            <label className="block text-sm font-semibold">
              Primary Learning Goal
              <textarea
                id="c06-goal-input"
                maxLength={200}
                rows={2}
                value={goalText}
                onChange={e => setGoalText(e.target.value)}
                className="input mt-1 w-full resize-none"
                placeholder="e.g. Master SQL queries and land my first data analyst internship"
              />
              <span className="text-[11px] text-muted block mt-0.5">
                Shared with mentors in case reports. Remind yourself what you're working toward (≤200 chars).
              </span>
            </label>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              id="c06-save-btn"
              type="submit"
              disabled={saving}
              className="btn btn-primary"
            >
              {saving ? 'Saving…' : t('C06.save')}
            </button>
            {saveSuccess && (
              <span className="text-sm text-teal font-semibold animate-fade-in">
                ✓ {t('C06.saved')}
              </span>
            )}
          </div>
        </form>
      </div>

      {/* Card 2: Activity & Mastery Numbers */}
      <div className="card p-6 space-y-4" id="c06-activity-card">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <SectionTitle
            eyebrow="Honest evidence ledger"
            title={t('C06.activity')}
          />
          <Link to="/genome" className="text-xs font-semibold text-teal hover:underline">
            Open Skill Genome →
          </Link>
        </div>

        <p className="text-xs text-muted -mt-2">
          Real numbers computed directly from verified work products and checks. No artificial points or simulated XP.
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="rounded-xl border border-line p-3.5 bg-paper/50">
            <div className="text-2xl font-black text-navy">{stats.concepts_proficient_or_better}</div>
            <div className="text-xs font-bold text-muted mt-1">Proficient Concepts</div>
            <div className="text-[11px] text-muted mt-0.5">out of {stats.concepts_assessed} assessed</div>
          </div>

          <div className="rounded-xl border border-line p-3.5 bg-paper/50">
            <div className="text-2xl font-black text-navy">{stats.checks_answered}</div>
            <div className="text-xs font-bold text-muted mt-1">Checks Answered</div>
            <div className="text-[11px] text-muted mt-0.5">probe & placement items</div>
          </div>

          <div className="rounded-xl border border-line p-3.5 bg-paper/50">
            <div className="text-2xl font-black text-navy">{stats.work_products_run}</div>
            <div className="text-xs font-bold text-muted mt-1">SQL Work Products</div>
            <div className="text-[11px] text-muted mt-0.5">real queries executed</div>
          </div>

          <div className="rounded-xl border border-line p-3.5 bg-paper/50">
            <div className="text-2xl font-black text-navy">{stats.explain_backs_finished}</div>
            <div className="text-xs font-bold text-muted mt-1">Teach-backs Done</div>
            <div className="text-[11px] text-muted mt-0.5">verbal & typed explanations</div>
          </div>

          <div className="rounded-xl border border-line p-3.5 bg-paper/50">
            <div className="text-2xl font-black text-navy">{stats.interviews_finished}</div>
            <div className="text-xs font-bold text-muted mt-1">Mock Interviews</div>
            <div className="text-[11px] text-muted mt-0.5">completed sessions</div>
          </div>

          <div className="rounded-xl border border-line p-3.5 bg-paper/50">
            <div className="text-2xl font-black text-navy">{stats.mentor_cases_closed}</div>
            <div className="text-xs font-bold text-muted mt-1">Mentor Cases Closed</div>
            <div className="text-[11px] text-muted mt-0.5">Chhatrachhaya sessions</div>
          </div>

          {stats.streak ? (
            <div className="rounded-xl border border-line p-3.5 bg-paper/50 sm:col-span-2">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black text-saffron">
                  {stats.streak.current_streak} {stats.streak.current_streak === 1 ? 'day' : 'days'}
                </span>
                <span className="text-xs text-muted">
                  (Best: <b>{stats.streak.best_streak}d</b> · {stats.streak.active_days_count} active days total)
                </span>
              </div>
              <div className="text-xs font-bold text-muted mt-1">Study Streak</div>
              <div className="text-[11px] text-muted mt-0.5">
                Active today: {stats.streak.active_today ? 'Yes ✓' : 'Not yet'}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-line p-3.5 bg-paper/50 sm:col-span-2">
              <div className="text-sm font-bold text-navy">Member Since</div>
              <div className="text-xs text-muted mt-1">{stats.member_since}</div>
            </div>
          )}
        </div>
      </div>

      {/* Card 3: Privacy & Safeguarding Panel */}
      <div className="card p-6 space-y-5" id="c06-privacy-panel">
        <SectionTitle
          eyebrow="Trust & Safety"
          title={t('C06.privacy')}
        />

        {/* Guardian Status for Minors */}
        {profile.is_minor && (
          <Callout
            tone={consent.guardian_status === 'granted' ? 'teal' : 'saffron'}
            title={
              consent.guardian_status === 'granted'
                ? 'Guardian Approval Active'
                : 'Guardian Approval Pending'
            }
          >
            Because you are under 18, mentor interactions are supervised and require verified guardian consent under child safeguarding and DPDP provisions.
            <div className="mt-1 font-semibold text-xs">
              Status: <span className="uppercase">{consent.guardian_status}</span>
            </div>
          </Callout>
        )}

        {/* Mentor Visibility Breakdown */}
        <div className="space-y-3">
          <div className="text-sm font-bold text-navy">
            Mentor Visibility & Case Reports
          </div>
          <p className="text-xs text-muted">
            When you open a case in Chhatrachhaya, the matched mentor receives an automated briefing so you never have to repeat yourself. Here is exactly what is disclosed versus kept private:
          </p>

          <div className="grid sm:grid-cols-2 gap-4 text-xs">
            <div className="rounded-xl border border-line p-4 bg-teal/5">
              <div className="font-bold text-teal flex items-center gap-1.5 mb-2">
                <span>👁</span> What mentors see in your case
              </div>
              <ul className="space-y-1.5 text-ink/80">
                {what_mentors_see.keys.map(k => (
                  <li key={k} className="flex items-start justify-between gap-2 border-b border-line/40 pb-1">
                    <span className="font-semibold capitalize">{k.replace(/_/g, ' ')}:</span>
                    <span className="font-mono text-right text-navy truncate max-w-[160px]">
                      {what_mentors_see.values[k] !== undefined && what_mentors_see.values[k] !== null
                        ? String(what_mentors_see.values[k])
                        : '—'}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-line p-4 bg-paper">
              <div className="font-bold text-muted flex items-center gap-1.5 mb-2">
                <span>🔒</span> What mentors NEVER see
              </div>
              <ul className="space-y-1.5 text-muted">
                {what_mentors_see.never_shared.map(item => (
                  <li key={item} className="flex items-center gap-2">
                    <span className="text-red-500 font-bold">✕</span> {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Transcript Sharing Switch */}
        <div className="rounded-xl border border-line p-4 space-y-2">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              id="c06-transcript-toggle"
              type="checkbox"
              className="mt-1"
              checked={transcriptShare}
              onChange={e => toggleTranscriptSharing(e.target.checked)}
            />
            <div className="text-sm">
              <span className="font-bold text-navy block">
                Share recent conversation snippets with mentor
              </span>
              <span className="text-xs text-muted block mt-0.5">
                When enabled, excerpted transcripts of where you got stuck with the AI tutor are included in your case briefing to help the mentor understand your thinking.
              </span>
            </div>
          </label>
        </div>

        {/* Data Rights & Deletion */}
        <div className="rounded-xl border border-line p-4 space-y-3">
          <div className="text-sm font-bold text-navy">Your Data Rights</div>
          <p className="text-xs text-muted">
            You own your learning history and records. Download an archival copy of everything SAARTHI has stored, or permanently erase your account.
          </p>
          <div className="flex gap-3 flex-wrap">
            <button
              id="c06-download-data-btn"
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={exportData}
            >
              Download my data (JSON)
            </button>
            <button
              id="c06-delete-account-btn"
              type="button"
              className="btn btn-ghost btn-sm"
              style={{ color: '#c62828' }}
              onClick={deleteAccount}
            >
              Delete my account
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
