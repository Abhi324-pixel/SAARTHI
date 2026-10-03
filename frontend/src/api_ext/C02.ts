import { req } from '../api'

// Mentor console and the safeguarding report queue (spec C02)
export const apiC02 = {
  me: () => req('/mentor-console/me'),
  acceptPledge: (version: string) => req('/mentor-console/me/pledge', { body: { version } }),
  setAvailability: (availability: string[]) => req('/mentor-console/me/availability', { method: 'PUT', body: { availability } }),
  cases: (group?: string) => req('/mentor-console/cases' + (group ? `?group=${group}` : '')),
  caseDetail: (id: string) => req(`/mentor-console/cases/${id}`),
  accept: (id: string, slot: string) => req(`/mentor-console/cases/${id}/accept`, { body: { slot } }),
  decline: (id: string, reason: string) => req(`/mentor-console/cases/${id}/decline`, { body: { reason } }),
  message: (id: string, text: string) => req(`/mentor-console/cases/${id}/messages`, { body: { text } }),
  held: (id: string) => req(`/mentor-console/cases/${id}/held`, { method: 'POST' }),
  outcome: (id: string, notes: string, next_step: string, demonstrated: number) => req(`/mentor-console/cases/${id}/outcome`, { body: { notes, next_step, demonstrated } }),
  flag: (id: string, detail: string) => req(`/mentor-console/cases/${id}/flag`, { body: { detail } }),
  adminReports: (status = 'open') => req(`/admin/reports?status=${status}`),
  adminResolve: (id: string, note: string) => req(`/admin/reports/${id}/resolve`, { body: { note } }),
}
