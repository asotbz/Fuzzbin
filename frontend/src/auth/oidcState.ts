const LEGACY_STATE_KEY = 'oidc_state'
const PENDING_STATES_KEY = 'oidc_pending_states'
const MAX_PENDING_STATES = 10

function readPendingStates(): string[] {
  const raw = sessionStorage.getItem(PENDING_STATES_KEY)
  if (!raw) return []

  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((v): v is string => typeof v === 'string' && v.length > 0)
  } catch {
    return []
  }
}

function writePendingStates(states: string[]): void {
  if (states.length === 0) {
    sessionStorage.removeItem(PENDING_STATES_KEY)
    return
  }
  sessionStorage.setItem(PENDING_STATES_KEY, JSON.stringify(states.slice(-MAX_PENDING_STATES)))
}

export function rememberOidcState(state: string): void {
  const states = readPendingStates()
  if (!states.includes(state)) {
    states.push(state)
    writePendingStates(states)
  }

  // Keep legacy key for compatibility with older callback logic/tests.
  sessionStorage.setItem(LEGACY_STATE_KEY, state)
}

export function consumeOidcState(returnedState: string): boolean {
  // Check modern pending-state list first (handles concurrent or repeated starts).
  const states = readPendingStates()
  if (states.includes(returnedState)) {
    writePendingStates(states.filter((state) => state !== returnedState))
    sessionStorage.removeItem(LEGACY_STATE_KEY)
    return true
  }

  // Fallback for legacy single-state flow.
  const legacy = sessionStorage.getItem(LEGACY_STATE_KEY)
  sessionStorage.removeItem(LEGACY_STATE_KEY)
  if (legacy === returnedState) {
    return true
  }

  return false
}
