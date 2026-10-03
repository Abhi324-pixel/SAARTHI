import { req } from '../api'

export interface StreakWeekDay {
  date: string
  active: boolean
}

export interface StreakSummary {
  current: number
  longest: number
  freezes: number
  freeze_used_on: string[]
  today_active: boolean
  goal_met_today: boolean
  week: StreakWeekDay[]
  total_active_days: number
  activities_today: number
  daily_goal: number
  show: boolean
}

export interface StreakSettingsIn {
  daily_goal?: number
  show?: boolean
}

export const apiT04 = {
  getStreak: () =>
    req<StreakSummary>('/streak'),

  updateSettings: (body: StreakSettingsIn) =>
    req<StreakSummary>('/streak/settings', {
      method: 'PATCH',
      body,
    }),
}
