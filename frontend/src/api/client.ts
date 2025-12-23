import { clearTokens, getTokens, setTokens } from '../auth/tokenStore'

const DEFAULT_BASE_URL = 'http://localhost:8000'

function getBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL
  return (typeof envUrl === 'string' && envUrl.length > 0 ? envUrl : DEFAULT_BASE_URL).replace(/\/$/, '')
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

type Json = Record<string, unknown>

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
  })

  if (resp.status === 401 && (options.allowRefresh ?? true) && !hasRetried) {
    const refreshToken = getTokens().refreshToken
    if (refreshToken && options.path !== '/auth/login' && options.path !== '/auth/refresh') {
      const refreshed = await tryRefresh(refreshToken)
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

async function tryRefresh(refreshToken: string): Promise<boolean> {
  try {
    const refreshed = await doFetch<{ access_token: string; refresh_token: string }>({
      method: 'POST',
      path: '/auth/refresh',
      auth: 'none',
      allowRefresh: false,
      body: { refresh_token: refreshToken } satisfies Json,
    })

    if (refreshed?.access_token && refreshed?.refresh_token) {
      setTokens({ accessToken: refreshed.access_token, refreshToken: refreshed.refresh_token })
      return true
    }
  } catch {
    // fallthrough
  }

  clearTokens()
  return false
}

export async function apiJson<T>(options: FetchOptions): Promise<T> {
  return doFetch<T>(options)
}
