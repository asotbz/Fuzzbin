/**
 * AuthProvider component for handling token hydration on app load.
 *
 * This component:
 * 1. Loads access token from localStorage on mount
 * 2. If the token is expired, attempts a silent refresh using the httpOnly cookie
 * 3. Schedules proactive token refresh before expiry
 */
import { useEffect, useState, type ReactNode } from 'react'
import { loadTokens, getTokens, clearTokens } from './tokenStore'
import { isTokenExpired } from '../lib/jwt'
import { scheduleTokenRefresh, clearRefreshTimer, apiJson } from '../api/client'

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [isInitialized, setIsInitialized] = useState(false)

  useEffect(() => {
    async function initAuth() {
      // Load tokens from localStorage
      const hasStoredToken = loadTokens()

      if (hasStoredToken) {
        const { accessToken } = getTokens()

        if (accessToken) {
          // Check if token is expired (or about to expire)
          if (isTokenExpired(accessToken, 60)) {
            // Try to refresh using httpOnly cookie
            try {
              const result = await apiJson<{ access_token: string; expires_in: number }>({
                method: 'POST',
                path: '/auth/refresh',
                auth: 'none',
                allowRefresh: false,
              })

              if (result?.access_token) {
                // Import setTokens here to avoid circular dependency issues
                const { setTokens } = await import('./tokenStore')
                setTokens({ accessToken: result.access_token })
                scheduleTokenRefresh(result.access_token)
              } else {
                // Refresh failed, clear tokens
                clearTokens()
              }
            } catch {
              // Refresh failed (e.g., no valid refresh cookie), clear tokens
              clearTokens()
            }
          } else {
            // Token is still valid, schedule proactive refresh
            scheduleTokenRefresh(accessToken)
          }
        }
      }

      setIsInitialized(true)
    }

    initAuth()

    // Cleanup refresh timer on unmount
    return () => {
      clearRefreshTimer()
    }
  }, [])

  // Show nothing while initializing to prevent flash of login page
  if (!isInitialized) {
    return null
  }

  return <>{children}</>
}
