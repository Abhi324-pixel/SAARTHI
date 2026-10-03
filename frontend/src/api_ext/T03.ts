import { req } from '../api'

export interface FeedbackAction {
  type: 'none' | 'probe' | 'strategy'
  item?: any
  strategy?: string
  explanation?: any
  prereq_probe?: any
}

export interface FeedbackResponse {
  message: string
  action: FeedbackAction
  after?: {
    roadmap?: {
      version: number
      changed: boolean
      diff: any
      change_reason: string
      readiness_now: number
      readiness_after: number
    }
    escalation_suggestions?: any[]
  }
}

export interface AdaptationsResponse {
  practice_factors: Record<string, number>
  default_factor: number
  helpful_strategies: Record<string, number>
}

export const apiT03 = {
  feedback: (concept_id: string, signal: 'too_easy' | 'too_hard' | 'helpful' | 'not_helpful', context = 'explanation', item_id?: string) =>
    req<FeedbackResponse>('/feedback', {
      method: 'POST',
      body: JSON.stringify({ concept_id, signal, context, item_id }),
    }),

  adaptations: () =>
    req<AdaptationsResponse>('/feedback/adaptations'),

  reset: () =>
    req<{ ok: boolean; message: string; after?: any }>('/feedback/reset', {
      method: 'POST',
    }),
}
