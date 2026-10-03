# api_ext — API calls added by individual feature specs

One file per spec (`T04.ts`, `C03.ts`, …) so nobody edits the shared `src/api.ts`. Import the shared helper:

```ts
import { req } from '../api'

export const apiT04 = {
  streak: () => req('/streak'),
  setStreakGoal: (daily_goal: number) => req('/streak/settings', { method: 'PATCH', body: { daily_goal } }),
}
```

`req` adds the sign-in token, throws `ApiError` on non-2xx and signs the learner out on 401. See `docs/features/00-PLAYBOOK.md` §5f.
