import { req } from '../api'

// Google sign-in age step (spec C07)
export const apiC07 = {
  completeProfile: (b: { age: number; name?: string; language?: string }) => req('/me/complete-profile', { body: b }),
}
