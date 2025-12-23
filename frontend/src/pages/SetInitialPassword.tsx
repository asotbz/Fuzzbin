import type { FormEvent } from 'react'
import { useMemo, useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { getApiBaseUrl } from '../api/client'
import { setTokens } from '../auth/tokenStore'
import { useAuthTokens } from '../auth/useAuthTokens'

type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export default function SetInitialPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const tokens = useAuthTokens()

  const [username, setUsername] = useState(searchParams.get('username') ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = useMemo(() => {
    return (
      username.trim().length > 0 &&
      currentPassword.length > 0 &&
      newPassword.length >= 8 &&
      !isSubmitting
    )
  }, [username, currentPassword, newPassword, isSubmitting])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return

    setError(null)
    setIsSubmitting(true)

    try {
      const resp = await fetch(`${getApiBaseUrl()}/auth/set-initial-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username,
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })

      if (resp.status === 429) {
        const retryAfter = resp.headers.get('Retry-After')
        const seconds = retryAfter ? Number(retryAfter) : undefined
        setError(typeof seconds === 'number' && Number.isFinite(seconds) ? `Try again in ${Math.max(1, Math.round(seconds))}s` : 'Try again')
        return
      }

      if (!resp.ok) {
        let msg = resp.statusText || 'Request failed'
        try {
          const data = (await resp.json()) as { detail?: unknown }
          if (typeof data?.detail === 'string' && data.detail.length > 0) msg = data.detail
        } catch {
          // ignore
        }
        setError(msg)
        return
      }

      const data = (await resp.json()) as TokenResponse
      setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token })
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
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          placeholder="Current password"
        />

        <input
          className="textInput"
          type="password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="New password"
        />

        <button className="btnPrimary" type="submit" disabled={!canSubmit}>
          {isSubmitting ? '…' : 'Set password'}
        </button>

        {error ? <div className="errorText">{error}</div> : null}
      </form>
    </div>
  )
}
