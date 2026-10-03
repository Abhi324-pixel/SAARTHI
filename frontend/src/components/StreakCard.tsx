import { useState } from 'react'
import { apiT04, type StreakSummary } from '../api_ext/T04'
import { Bar, SectionTitle } from './ui'

// ---------------------------------------------------------------------------
// Streak message helpers
// ---------------------------------------------------------------------------

function streakMessage(s: StreakSummary): string {
  if (s.current === 0 && !s.today_active) {
    return 'Do one activity today to start your streak.'
  }
  if (s.goal_met_today) {
    return "You've hit today's goal — great work!"
  }
  if (s.freeze_used_on.length > 0) {
    const last = s.freeze_used_on[s.freeze_used_on.length - 1]
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    const lastDate = last.slice(0, 10)
    const yDate = yesterday.toISOString().slice(0, 10)
    if (lastDate === yDate) {
      return 'A freeze kept your streak alive yesterday.'
    }
  }
  const remaining = s.daily_goal - s.activities_today
  if (remaining === 1) {
    return 'One more activity keeps it going today.'
  }
  if (remaining > 1) {
    return `${remaining} more activities to reach today's goal.`
  }
  return `${s.current}-day streak — keep it going!`
}

// ---------------------------------------------------------------------------
// Dot row (7-day history bar)
// ---------------------------------------------------------------------------

function WeekDots({ week }: { week: StreakSummary['week'] }) {
  return (
    <div className="flex gap-1.5 items-center" aria-label="Last 7 days">
      {week.map((d) => (
        <div
          key={d.date}
          title={d.date}
          className="h-2.5 w-2.5 rounded-full"
          style={{
            background: d.active ? '#e07a1f' : '#e8edf3',
            transition: 'background .3s',
          }}
        />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Flame number
// ---------------------------------------------------------------------------

function FlameCount({ count }: { count: number }) {
  return (
    <div className="flex items-center gap-1.5 select-none" aria-label={`${count}-day streak`}>
      <span className="text-2xl" aria-hidden>🔥</span>
      <span className="text-3xl font-extrabold text-navy leading-none">{count}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Goal gear edit modal (inline)
// ---------------------------------------------------------------------------

function GoalEditor({
  goal,
  onSave,
  onClose,
}: {
  goal: number
  onSave: (g: number) => void
  onClose: () => void
}) {
  const [val, setVal] = useState(goal)
  return (
    <div className="flex items-center gap-2 mt-2">
      <label className="text-xs font-semibold text-muted">Daily goal</label>
      <input
        id="t04-daily-goal-input"
        type="number"
        min={1}
        max={10}
        value={val}
        onChange={(e) => setVal(Number(e.target.value))}
        className="input w-16 text-sm"
      />
      <button className="btn btn-primary btn-sm" onClick={() => onSave(val)}>Save</button>
      <button className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// StreakCard — the main exported component
// ---------------------------------------------------------------------------

export interface StreakCardProps {
  /** Initial streak data from the dashboard response (avoids extra fetch on load) */
  initial: StreakSummary
}

export default function StreakCard({ initial }: StreakCardProps) {
  const [streak, setStreak] = useState<StreakSummary>(initial)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  // Respect the show toggle — render nothing if hidden
  if (!streak.show) return null

  async function saveGoal(g: number) {
    if (g < 1 || g > 10) return
    setSaving(true)
    setErr(null)
    try {
      const updated = await apiT04.updateSettings({ daily_goal: g })
      setStreak(updated)
      setEditing(false)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  const msg = streakMessage(streak)

  return (
    <div className="card p-5 space-y-3" id="t04-streak-card">
      <SectionTitle
        eyebrow="Habit"
        title="Study streak"
        right={
          <button
            id="t04-goal-gear"
            className="btn btn-ghost btn-sm"
            title="Edit daily goal"
            onClick={() => setEditing((o) => !o)}
            aria-label="Edit daily goal"
          >
            ⚙
          </button>
        }
      />

      {/* Flame + best row */}
      <div className="flex items-end gap-4 flex-wrap">
        <FlameCount count={streak.current} />
        <div className="text-sm text-muted space-y-0.5">
          <div>Best: <b className="text-navy">{streak.longest}</b> days</div>
          <div>
            {streak.freezes > 0 ? (
              <>🧊 <b className="text-navy">{streak.freezes}</b> freeze{streak.freezes > 1 ? 's' : ''} held</>
            ) : (
              <span>No freezes held</span>
            )}
          </div>
        </div>
      </div>

      {/* 7-day dots */}
      <WeekDots week={streak.week} />

      {/* Today's goal progress bar */}
      <div>
        <div className="flex justify-between text-xs font-semibold mb-1">
          <span className="text-muted">Today's goal</span>
          <span className="text-navy">{streak.activities_today} / {streak.daily_goal}</span>
        </div>
        <Bar value={streak.daily_goal > 0 ? streak.activities_today / streak.daily_goal : 0} />
      </div>

      {/* Friendly message */}
      <div className="text-xs text-muted leading-snug">{msg}</div>

      {/* Goal editor */}
      {editing && (
        <GoalEditor
          goal={streak.daily_goal}
          onSave={saveGoal}
          onClose={() => setEditing(false)}
        />
      )}
      {saving && <div className="text-xs text-muted">Saving…</div>}
      {err && <div className="text-xs text-red-600">{err}</div>}
    </div>
  )
}
