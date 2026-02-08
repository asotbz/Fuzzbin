import type { FormEvent } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { getApiBaseUrl, scheduleTokenRefresh } from '../api/client'
import { useOidcConfig } from '../api/useOidcConfig'
import { startOidcLogin } from '../lib/api/endpoints/oidc'
import { setTokens } from '../auth/tokenStore'
import { useAuthTokens } from '../auth/useAuthTokens'

type AccessTokenResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const tokens = useAuthTokens()
  const { data: oidcConfig, isLoading: isOidcLoading } = useOidcConfig()
  const forceLocal = searchParams.get('local') === '1'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isOidcStarting, setIsOidcStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Auto-trigger OIDC login when enabled and not overridden with ?local=1
  const oidcAutoStarted = useRef(false)
  useEffect(() => {
    if (
      !isOidcLoading &&
      oidcConfig?.enabled &&
      !forceLocal &&
      !tokens.accessToken &&
      !oidcAutoStarted.current
    ) {
      oidcAutoStarted.current = true
      onOidcLogin()
    }
  }, [isOidcLoading, oidcConfig?.enabled, forceLocal, tokens.accessToken])

  const canSubmit = useMemo(() => username.trim().length > 0 && password.length > 0 && !isSubmitting, [username, password, isSubmitting])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return

    setError(null)
    setIsSubmitting(true)

    try {
      const resp = await fetch(`${getApiBaseUrl()}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include', // Required for httpOnly cookie
      })

      const headerSaysRotation = resp.headers.get('X-Password-Change-Required') === 'true'

      if (resp.status === 429) {
        const retryAfter = resp.headers.get('Retry-After')
        const seconds = retryAfter ? Number(retryAfter) : undefined
        setError(typeof seconds === 'number' && Number.isFinite(seconds) ? `Try again in ${Math.max(1, Math.round(seconds))}s` : 'Try again')
        return
      }

      if (resp.status === 403 && headerSaysRotation) {
        navigate(`/set-initial-password?username=${encodeURIComponent(username)}`, {
          state: { currentPassword: password },
        })
        return
      }

      if (!resp.ok) {
        let msg = resp.statusText || 'Login failed'
        try {
          const data = (await resp.json()) as { detail?: unknown }
          if (typeof data?.detail === 'string' && data.detail.length > 0) msg = data.detail

          // Fallback when the rotation header isn't readable (CORS) or missing.
          if (resp.status === 403 && typeof data?.detail === 'string' && data.detail.includes('/auth/set-initial-password')) {
            navigate(`/set-initial-password?username=${encodeURIComponent(username)}`, {
              state: { currentPassword: password },
            })
            return
          }
        } catch {
          // ignore
        }
        setError(msg)
        return
      }

      const data = (await resp.json()) as AccessTokenResponse
      setTokens({ accessToken: data.access_token })
      // Schedule proactive token refresh
      scheduleTokenRefresh(data.access_token)
      navigate('/library')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function onOidcLogin() {
    setError(null)
    setIsOidcStarting(true)
    try {
      const { auth_url, state } = await startOidcLogin()
      sessionStorage.setItem('oidc_state', state)
      window.location.href = auth_url
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start OIDC login')
      setIsOidcStarting(false)
    }
  }

  if (tokens.accessToken) return <Navigate to="/library" replace />

  // When OIDC is enabled and not overridden, show a redirecting state
  if (oidcConfig?.enabled && !forceLocal) {
    return (
      <div className="centeredPage">
        <div className="panel">
          <img className="splash" src="/fuzzbin-logo.png" alt="Fuzzbin" />
          {error ? (
            <>
              <div className="errorText">{error}</div>
              <button
                className="btnPrimary"
                type="button"
                onClick={onOidcLogin}
                disabled={isOidcStarting}
                style={{ width: '100%', marginTop: '0.5rem' }}
              >
                {isOidcStarting ? '…' : 'Try again'}
              </button>
              <a
                href="/login?local=1"
                style={{ display: 'block', textAlign: 'center', marginTop: '0.75rem', fontSize: '0.8rem', opacity: 0.6 }}
              >
                Sign in with password instead
              </a>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '1rem 0', opacity: 0.7 }}>
              Redirecting to {oidcConfig.provider_name}…
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="centeredPage">
      <form className="panel" onSubmit={onSubmit}>
        <img className="splash" src="/fuzzbin-logo.png" alt="Fuzzbin" />

        <input
          className="textInput"
          autoComplete="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
        />

        <input
          className="textInput"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
        />

        <button className="btnPrimary" type="submit" disabled={!canSubmit}>
          {isSubmitting ? '…' : 'Login'}
        </button>

        {oidcConfig?.enabled && forceLocal ? (
          <>
            <div className="dividerRow" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0.5rem 0' }}>
              <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--border, #444)' }} />
              <span style={{ fontSize: '0.8rem', opacity: 0.6 }}>or</span>
              <hr style={{ flex: 1, border: 'none', borderTop: '1px solid var(--border, #444)' }} />
            </div>

            <button
              className="btnPrimary"
              type="button"
              disabled={isOidcStarting}
              onClick={onOidcLogin}
              style={{ width: '100%' }}
            >
              {isOidcStarting ? '…' : `Continue with ${oidcConfig.provider_name}`}
            </button>
          </>
        ) : null}

        {error ? <div className="errorText">{error}</div> : null}
      </form>
    </div>
  )
}
