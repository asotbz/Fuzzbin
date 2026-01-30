import { clearTokens, getTokens, setTokens } from '../auth/tokenStore'
import { decodeJwt } from '../lib/jwt'

// Proactive refresh timer
let refreshTimer: ReturnType<typeof setTimeout> | null = null

// Buffer time before token expiry to trigger refresh (1 minute)
const REFRESH_BUFFER_MS = 60 * 1000

function getBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  // If VITE_API_BASE_URL is set, use it; otherwise use current origin (works behind reverse proxy)
  const baseUrl = typeof envUrl === 'string' && envUrl.length > 0 ? envUrl : window.location.origin
  return baseUrl.replace(/\/$/, '')
}

export function getApiBaseUrl() {
  return getBaseUrl()
}

export class APIError extends Error {
  readonly status: number
  readonly retryAfterSeconds?: number

  constructor(message: string, status: number, retryAfterSeconds?: number) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.retryAfterSeconds = retryAfterSeconds
  }
}

type FetchOptions = {
  method?: string
  path: string
  body?: unknown
  headers?: Record<string, string>
  auth?: 'auto' | 'none'
  allowRefresh?: boolean
}

async function doFetch<T>(options: FetchOptions, hasRetried = false): Promise<T> {
  const url = `${getBaseUrl()}${options.path.startsWith('/') ? options.path : `/${options.path}`}`

  const headers: Record<string, string> = {
    ...(options.headers ?? {}),
  }

  const tokens = getTokens()
  const shouldAuth = (options.auth ?? 'auto') === 'auto'
  if (shouldAuth && tokens.accessToken) {
    headers.Authorization = `Bearer ${tokens.accessToken}`
  }

  let body: BodyInit | undefined
  if (options.body !== undefined) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json'
    body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body)
  }

  const resp = await fetch(url, {
    method: options.method ?? 'GET',
    headers,
    body,
    credentials: 'include', // Required for httpOnly cookie refresh token
  })

  if (resp.status === 401 && (options.allowRefresh ?? true) && !hasRetried) {
    // httpOnly cookie is sent automatically, so we just need to check if we have an access token
    // indicating we were logged in and should try to refresh
    const { accessToken } = getTokens()
    if (accessToken && options.path !== '/auth/login' && options.path !== '/auth/refresh') {
      const refreshed = await tryRefresh()
      if (refreshed) {
        return doFetch<T>(options, true)
      }
    }
  }

  if (!resp.ok) {
    const retryAfter = resp.headers.get('Retry-After')
    const retryAfterSeconds = retryAfter ? Number(retryAfter) : undefined

    let message = resp.statusText || 'Request failed'
    try {
      const data = (await resp.json()) as { detail?: unknown }
      if (typeof data?.detail === 'string' && data.detail.length > 0) message = data.detail
    } catch {
      // ignore
    }

    throw new APIError(message, resp.status, Number.isFinite(retryAfterSeconds) ? retryAfterSeconds : undefined)
  }

  if (resp.status === 204) {
    return undefined as T
  }

  const text = await resp.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

/**
 * Try to refresh the access token using the httpOnly cookie.
 * The browser automatically sends the refresh token cookie.
 */
async function tryRefresh(): Promise<boolean> {
  try {
    const refreshed = await doFetch<{ access_token: string; expires_in: number }>({
      method: 'POST',
      path: '/auth/refresh',
      auth: 'none',
      allowRefresh: false,
      // No body needed - refresh token is sent via httpOnly cookie
    })

    if (refreshed?.access_token) {
      setTokens({ accessToken: refreshed.access_token })
      // Schedule next proactive refresh
      scheduleTokenRefresh(refreshed.access_token)
      return true
    }
  } catch {
    // fallthrough
  }

  clearTokens()
  clearRefreshTimer()
  return false
}

/**
 * Schedule a proactive token refresh before the access token expires.
 */
export function scheduleTokenRefresh(accessToken: string): void {
  clearRefreshTimer()

  const payload = decodeJwt(accessToken)
  if (!payload?.exp) {
    return
  }

  const nowMs = Date.now()
  const expiryMs = payload.exp * 1000
  const timeUntilRefresh = expiryMs - nowMs - REFRESH_BUFFER_MS

  if (timeUntilRefresh > 0) {
    refreshTimer = setTimeout(() => {
      tryRefresh()
    }, timeUntilRefresh)
  }
}

/**
 * Clear the proactive refresh timer (e.g., on logout).
 */
export function clearRefreshTimer(): void {
  if (refreshTimer) {
    clearTimeout(refreshTimer)
    refreshTimer = null
  }
}

/**
 * Logout the user.
 *
 * Calls the backend /auth/logout endpoint to:
 * 1. Revoke the current access token
 * 2. Clear the httpOnly refresh token cookie
 *
 * Then clears local state (access token in localStorage and memory).
 */
export async function logout(): Promise<void> {
  try {
    // Call logout endpoint to revoke token and clear cookie
    await doFetch({
      method: 'POST',
      path: '/auth/logout',
      auth: 'auto', // Send the access token for revocation
      allowRefresh: false,
    })
  } catch {
    // Even if the API call fails, clear local state
  }

  clearRefreshTimer()
  clearTokens()
}

export async function apiJson<T>(options: FetchOptions): Promise<T> {
  return doFetch<T>(options)
}
