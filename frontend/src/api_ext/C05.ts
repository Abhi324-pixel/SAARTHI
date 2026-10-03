import { req } from '../api'

// Notifications and unread counts (spec C05)
export const apiC05 = {
  summary: () => req('/notifications/summary'),
  list: (limit = 30) => req(`/notifications?limit=${limit}`),
  markRead: (ids: string[]) => req('/notifications/read', { body: { ids } }),
  markAllRead: () => req('/notifications/read', { body: { all: true } }),
  caseRead: (caseId: string) => req(`/cases/${caseId}/read`, { method: 'POST' }),
}
