import { req } from '../api'

export interface ProgressPoint {
  at: string
  overall: number
  by_domain: Record<string, number>
  n: number
  simulated: boolean
}

export interface ProgressMarker {
  at: string
  kind: 'mentor' | 'misconception_resolved' | 'plan_changed'
  label: string
}

export interface ProgressHistory {
  series: ProgressPoint[]
  markers: ProgressMarker[]
  now: { overall: number; by_domain: Record<string, number> }
  projection: { overall: number; weeks: number }
  due_reviews: number
}

export interface RadarDomain {
  domain: string
  current: number
  target: number
}

export const apiT06 = {
  history: (days = 90) =>
    req<ProgressHistory>(`/progress/history?days=${days}`),

  radar: () =>
    req<{ domains: RadarDomain[] }>('/progress/radar'),
}
