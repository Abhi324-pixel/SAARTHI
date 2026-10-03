import { req } from '../api'

export interface ProfileData {
  name: string
  email: string
  age: number
  is_minor: boolean
  education?: string | null
  institution?: string | null
  goal_text?: string | null
  language: string
  role_id: string
  role_title: string
}

export interface ProfileStats {
  concepts_proficient_or_better: number
  concepts_assessed: number
  checks_answered: number
  work_products_run: number
  explain_backs_finished: number
  interviews_finished: number
  mentor_cases_closed: number
  member_since: string
  streak?: any | null
}

export interface ProfileConsent {
  mentor_sessions: string
  transcript_share: string
  is_minor: boolean
  guardian_status: string
}

export interface WhatMentorsSee {
  keys: string[]
  values: Record<string, any>
  never_shared: string[]
}

export interface ProfileResponse {
  profile: ProfileData
  stats: ProfileStats
  consent: ProfileConsent
  what_mentors_see: WhatMentorsSee
}

export interface ProfilePatchPayload {
  name?: string
  education?: string | null
  institution?: string | null
  goal_text?: string | null
}

export const apiC06 = {
  getProfile: () => req<ProfileResponse>('/profile'),

  updateProfile: (body: ProfilePatchPayload) =>
    req<ProfileResponse>('/profile', {
      method: 'PATCH',
      body,
    }),
}
