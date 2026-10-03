import { req } from '../api'

export interface SnappedSkill {
  concept_id: string
  concept_name: string
  rating: number
  phrase: string
}

export interface UnderstoodDraft {
  goal_text: string
  role_id: string | null
  role_title: string | null
  weekly_hours: number | null
  horizon_weeks: number | null
  language: string | null
  known_skills: SnappedSkill[]
  confidence: number
}

export interface IntakeTurnResponse {
  understood: UnderstoodDraft
  follow_up: string | null
  ready: boolean
  unavailable_role: string | null
  unavailable?: boolean
  message?: string
}

export const apiT01 = {
  turn: (message: string) =>
    req<IntakeTurnResponse>('/intake/turn', {
      method: 'POST',
      body: { message },
    }),

  confirm: (overrides?: Partial<UnderstoodDraft>) =>
    req<{ me: any; roadmap: any }>('/intake/confirm', {
      method: 'POST',
      body: overrides || {},
    }),
}
