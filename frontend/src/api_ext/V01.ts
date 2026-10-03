import { req } from '../api'

// Resume and video interview (spec V01). Camera and microphone data never go through these calls.
export interface ResumeSummary { skills: string[]; projects: { name: string; what: string }[]; education: string[]; experience: string[]; updated_at?: string }
export interface InterviewFeedback { status: 'ok' | 'too_short' | 'unavailable'; strengths: { point: string; quote: string }[]; gaps: string[]; gap_concepts?: string[] }
export interface FocusTopic { concept_id: string; name: string; times: number; state: 'addable' | 'in_plan' | 'at_target' }
export interface InterviewStart { id: string; status: string; total: number; answered: number; question: string | null; use_resume: boolean }
export interface InterviewAnswerResult { feedback: InterviewFeedback; done: boolean; next_question: string | null; answered: number; total: number }
export interface ClientMetrics { face_in_frame_pct?: number; facing_camera_pct?: number; voice_level_ok_pct?: number; speaking_seconds?: number; recording_saved?: boolean }
export interface InterviewReport {
  id: string; status: string; role_title: string; use_resume: boolean
  turns: { question: string; answer: string; feedback: InterviewFeedback }[]
  summary: { answers: number; grounded_strengths: number; suggestions: number; answers_with_quotes: number; too_short: number }
  written_summary: string | null
  focus_topics: FocusTopic[]
  created_at: string
  client_metrics: ClientMetrics | null
  note: string
}

export const apiV01 = {
  resume: (): Promise<{ summary: ResumeSummary | null }> => req('/resume'),
  uploadResume: (file: File): Promise<{ summary: ResumeSummary }> => { const f = new FormData(); f.append('file', file); return req('/resume', { form: f }) },
  deleteResume: (): Promise<{ deleted: boolean }> => req('/resume', { method: 'DELETE' }),
  start: (use_resume: boolean): Promise<InterviewStart> => req('/video-interview/start', { body: { use_resume } }),
  answer: (id: string, text: string): Promise<InterviewAnswerResult> => req(`/video-interview/${id}/answer`, { body: { text } }),
  finish: (id: string, client_metrics: Record<string, unknown>): Promise<InterviewReport> => req(`/video-interview/${id}/finish`, { body: { client_metrics } }),
  report: (id: string): Promise<InterviewReport> => req(`/video-interview/${id}`),
  addFocus: (id: string): Promise<{ added: { concept_id: string; name: string }[]; roadmap_version: number; roadmap_change: string; focus_topics: FocusTopic[] }> => req(`/video-interview/${id}/focus`, { method: 'POST' }),
  history: (): Promise<{ interviews: { id: string; status: string; created_at: string; answers: number; use_resume: boolean }[] }> => req('/video-interview'),
}
