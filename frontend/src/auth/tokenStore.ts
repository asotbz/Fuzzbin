export type AuthTokens = {
  accessToken: string | null
  refreshToken: string | null
}

let tokens: AuthTokens = {
  accessToken: null,
  refreshToken: null,
}

const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export function getTokens(): AuthTokens {
  return tokens
}

export function setTokens(next: { accessToken: string; refreshToken: string }) {
  tokens = { accessToken: next.accessToken, refreshToken: next.refreshToken }
  emit()
}

export function clearTokens() {
  tokens = { accessToken: null, refreshToken: null }
  emit()
}

export function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
