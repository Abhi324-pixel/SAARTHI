import { req } from '../api'

export interface PrepQuestion {
  text: string
  from: 'misconception' | 'prerequisite' | 'concept' | 'career' | 'goal'
  hidden_answer?: string
}

export interface CasePrepData {
  bring: string[]
  questions: PrepQuestion[]
  icebreaker: string
  mentor_sees: Record<string, any>
  language: string
}

export interface CaseSummaryData {
  mentor_said: {
    notes: string
    next_step: string
    by: string
  }
  saarthi_saw: {
    concept: string
    concept_id: string | null
    p_before: number | null
    p_after: number | null
    evidence: Array<{ source: string; score: number; at: string }>
  }
  followup: {
    due: string
    task: string
  }
}

export const apiC03 = {
  getPrep: (caseId: string, lang?: string) =>
    req<CasePrepData>(`/cases/${caseId}/prep${lang ? `?lang=${encodeURIComponent(lang)}` : ''}`),
  sharePrep: (caseId: string, questionIndexes: number[]) =>
    req<{ sent: boolean; blocked?: boolean; reason?: string }>(`/cases/${caseId}/prep/share`, {
      method: 'POST',
      body: { question_indexes: questionIndexes },
    }),
  getSummary: (caseId: string) =>
    req<CaseSummaryData>(`/cases/${caseId}/summary`),
}
