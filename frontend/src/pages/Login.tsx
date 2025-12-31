import type { FormEvent } from 'react'
import { useMemo, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { getApiBaseUrl, scheduleTokenRefresh } from '../api/client'
import { setTokens } from '../auth/tokenStore'
import { useAuthTokens } from '../auth/useAuthTokens'

type AccessTokenResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export default function LoginPage() {
  const navigate = useNavigate()
  const tokens = useAuthTokens()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
        navigate(`/set-initial-password?username=${encodeURIComponent(username)}`)
        return
      }

      if (!resp.ok) {
        let msg = resp.statusText || 'Login failed'
        try {
          const data = (await resp.json()) as { detail?: unknown }
          if (typeof data?.detail === 'string' && data.detail.length > 0) msg = data.detail

          // Fallback when the rotation header isn't readable (CORS) or missing.
          if (resp.status === 403 && typeof data?.detail === 'string' && data.detail.includes('/auth/set-initial-password')) {
            navigate(`/set-initial-password?username=${encodeURIComponent(username)}`)
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

  if (tokens.accessToken) return <Navigate to="/library" replace />

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

        {error ? <div className="errorText">{error}</div> : null}
      </form>
    </div>
  )
}
