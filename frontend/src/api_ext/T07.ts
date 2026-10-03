import { req } from '../api'

export interface ChatAction {
  type: string
  label: string
  concept_id?: string
  category?: string
}

export interface ChatResponse {
  session_id: string
  reply: string
  actions: ChatAction[]
  facts_used: string[]
  source: string
}

export const apiT07 = {
  sendMessage: (message: string, sessionId?: string) =>
    req<ChatResponse>('/chat', {
      method: 'POST',
      body: { message, session_id: sessionId },
    }),
  getSuggestions: () =>
    req<{ suggestions: string[] }>('/chat/suggestions'),
}
