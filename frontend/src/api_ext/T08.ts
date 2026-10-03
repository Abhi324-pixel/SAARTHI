import { req } from '../api'

/**
 * T08 API extensions: HR / Behavioural interview rounds, company packs, and history.
 */

export interface InterviewPackRound {
  concept_ids: string[]
  n: number
}

export interface InterviewPack {
  id: string
  title: string
  title_hi?: string
  description: string
  target_company_type: string
  rounds: {
    behavioural?: InterviewPackRound
    technical?: InterviewPackRound
  }
  concept_ids: string[]
  duration_minutes: number
  reviewed: boolean
  source: string
  reviewed_by: string
}

export interface InterviewHistoryItem {
  session_id: string
  created_at: string | null
  status: string
  round: string
  pack_id?: string | null
  role_title: string
  total_topics: number
  completed_topics: number
  checklist_items_covered: number
  checklist_items_total: number
  strengths: string[]
  needs_work: string[]
}

export async function fetchInterviewPacks(): Promise<InterviewPack[]> {
  const data = await req('/interview/packs')
  return data.packs || []
}

export async function fetchInterviewHistory(): Promise<InterviewHistoryItem[]> {
  const data = await req('/interview/history')
  return data.history || []
}
