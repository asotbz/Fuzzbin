/**
 * Token store with localStorage persistence.
 *
 * Stores access token in localStorage for persistence across page refreshes.
 * Refresh token is stored as an httpOnly cookie by the backend and is not
 * accessible to JavaScript.
 */

const STORAGE_KEY = 'fuzzbin_access_token'

export type AuthTokens = {
  accessToken: string | null
}

let tokens: AuthTokens = {
  accessToken: null,
}

const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export function getTokens(): AuthTokens {
  return tokens
}

/**
 * Set the access token (persists to localStorage).
 * Refresh token is handled via httpOnly cookie by the backend.
 */
export function setTokens(next: { accessToken: string }) {
  tokens = { accessToken: next.accessToken }
  try {
    localStorage.setItem(STORAGE_KEY, next.accessToken)
  } catch {
    // localStorage might be unavailable (private browsing, etc.)
  }
  emit()
}

/**
 * Clear all tokens (removes from localStorage).
 * Note: The httpOnly refresh token cookie should be cleared by calling /auth/logout.
 */
export function clearTokens() {
  tokens = { accessToken: null }
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ignore storage errors
  }
  emit()
}

/**
 * Load tokens from localStorage on app initialization.
 * Returns true if a token was found (does not validate it).
 */
export function loadTokens(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      tokens = { accessToken: stored }
      emit()
      return true
    }
  } catch {
    // Ignore storage errors
  }
  return false
}

export function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
