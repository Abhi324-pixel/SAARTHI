import { req } from '../api'

// Guardian consent (spec D01). The guardian endpoints are public: no sign-in token is needed (req simply sends none).
export const apiD01 = {
  requestGuardian: (guardian_email: string, lang: string) =>
    req('/consent/request', { body: { scope: 'mentor_sessions', guardian_email, lang } }),
  guardianPreview: (token: string) => req('/guardian/preview?token=' + encodeURIComponent(token)),
  guardianDecision: (token: string, decision: 'approve' | 'decline') => req('/guardian/decision', { body: { token, decision } }),
  guardianWithdraw: (token: string) => req('/guardian/withdraw', { body: { token } }),
  devOutbox: () => req('/dev/outbox'),
}
