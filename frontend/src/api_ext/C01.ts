import { req } from '../api'

// Mentor sign-up and the safeguarding lead's review (spec C01)
export const apiC01 = {
  myApplication: () => req('/mentor/apply'),
  saveProfile: (b: any) => req('/mentor/apply', { method: 'PUT', body: b }),
  screenQuestions: () => req('/mentor/apply/screen'),
  submitScreen: (answers: Record<string, number>, open: Record<string, string>) => req('/mentor/apply/screen', { body: { answers, open } }),
  acceptPledge: (version: string) => req('/mentor/apply/pledge', { body: { version } }),
  submitApplication: () => req('/mentor/apply/submit', { method: 'POST' }),
  adminApplications: (status?: string) => req('/admin/mentor-applications' + (status ? `?status=${status}` : '')),
  adminDecide: (id: string, decision: string, note: string, checks: { kind: string }[]) =>
    req(`/admin/mentor-applications/${id}/decision`, { body: { decision, note, checks } }),
  adminMentors: () => req('/admin/mentors'),
  adminSuspend: (id: string, note: string) => req(`/admin/mentors/${id}/suspend`, { body: { note } }),
}
