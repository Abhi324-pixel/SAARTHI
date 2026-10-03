import { req } from '../api'

export interface DeadlineStatus {
  on_track: boolean
  projected_finish: string
  gap_days: number
  needed_hours_per_week: number
  weeks_left: number
  minutes_needed: number
  passed?: boolean
}

export interface Phase {
  key: string
  title: string
  domain: string
  start_week: number
  end_week: number
  minutes: number
  concept_ids: string[]
  target_date: string
  deadline: string | null
  deadline_status: DeadlineStatus | null
}

export interface Checkpoint {
  id: string
  title: string
  due_date: string | null
  concept_id: string | null
  concept_name?: string | null
  done: boolean
  is_concept_linked: boolean
  done_at?: string | null
  created_at: string
}

export interface PhaseCheckResponse {
  phase_key: string
  phase_title: string
  items: any[]
  count: number
}

export const apiT05 = {
  setDeadline: (key: string, date: string) =>
    req<{ ok: boolean; phase: Phase; deadline_status: DeadlineStatus | null }>(`/phases/${key}/deadline`, {
      method: 'PUT',
      body: { date },
    }),

  deleteDeadline: (key: string) =>
    req<{ ok: boolean }>(`/phases/${key}/deadline`, {
      method: 'DELETE',
    }),

  phaseCheck: (key: string) =>
    req<PhaseCheckResponse>(`/phases/${key}/check`, {
      method: 'POST',
    }),

  getCheckpoints: () =>
    req<{ checkpoints: Checkpoint[] }>('/checkpoints'),

  createCheckpoint: (data: { title: string; due_date?: string | null; concept_id?: string | null }) =>
    req<Checkpoint>('/checkpoints', {
      method: 'POST',
      body: data,
    }),

  toggleCheckpoint: (id: string) =>
    req<{ id: string; done: boolean; done_at: string | null }>(`/checkpoints/${id}`, {
      method: 'PATCH',
    }),

  deleteCheckpoint: (id: string) =>
    req<{ ok: boolean }>(`/checkpoints/${id}`, {
      method: 'DELETE',
    }),
}
