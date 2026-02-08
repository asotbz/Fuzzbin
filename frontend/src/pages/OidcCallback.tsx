import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { scheduleTokenRefresh } from '../api/client'
import { exchangeOidcCode } from '../lib/api/endpoints/oidc'
import { consumeOidcState } from '../auth/oidcState'
import { setTokens } from '../auth/tokenStore'

type Phase = 'exchanging' | 'error'

export default function OidcCallbackPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [phase, setPhase] = useState<Phase>('exchanging')
  const [error, setError] = useState<string | null>(null)
  const exchangeStarted = useRef(false)

  useEffect(() => {
    // React StrictMode runs effects twice in development; guard to ensure
    // we only consume OIDC state and start exchange once.
    if (exchangeStarted.current) return
    exchangeStarted.current = true

    const code = params.get('code')
    const returnedState = params.get('state')
    const idpError = params.get('error')
    const idpErrorDesc = params.get('error_description')

    // Handle IdP-side errors (e.g. user denied consent)
    if (idpError) {
      setPhase('error')
      setError(idpErrorDesc || idpError)
      return
    }

    if (!code || !returnedState) {
      setPhase('error')
      setError('Missing authorization code or state from identity provider.')
      return
    }

    // Client-side CSRF check against pending in-browser OIDC states.
    if (!consumeOidcState(returnedState)) {
      setPhase('error')
      setError(
        'State mismatch — possible CSRF attack. Please try logging in again. ' +
          'If running locally, ensure login starts and callback both use the same origin.'
      )
      return
    }

    async function doExchange() {
      try {
        const data = await exchangeOidcCode(code!, returnedState!)

        setTokens({ accessToken: data.access_token })
        scheduleTokenRefresh(data.access_token)
        navigate('/library', { replace: true })
      } catch (err) {
        setPhase('error')
        setError(err instanceof Error ? err.message : 'OIDC login failed')
      }
    }

    doExchange()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (phase === 'error') {
    return (
      <div className="centeredPage">
        <div className="panel" style={{ textAlign: 'center' }}>
          <img className="splash" src="/fuzzbin-logo.png" alt="Fuzzbin" />

          <div className="errorText" style={{ marginBottom: '1rem' }}>
            {error || 'An unknown error occurred during OIDC login.'}
          </div>

          <button className="btnPrimary" type="button" onClick={() => navigate('/login', { replace: true })}>
            Back to login
          </button>
        </div>
      </div>
    )
  }

  // Exchanging phase — spinner/loading state
  return (
    <div className="centeredPage">
      <div className="panel" style={{ textAlign: 'center' }}>
        <img className="splash" src="/fuzzbin-logo.png" alt="Fuzzbin" />
        <p>Completing login…</p>
      </div>
    </div>
  )
}
