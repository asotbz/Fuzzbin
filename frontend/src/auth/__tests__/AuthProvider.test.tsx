import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { AuthProvider } from '../AuthProvider'
import { clearTokens, setTokens, getTokens } from '../tokenStore'
import * as jwtModule from '../../lib/jwt'
import * as clientModule from '../../api/client'

// Mock the modules
vi.mock('../../lib/jwt', () => ({
  isTokenExpired: vi.fn(),
}))

vi.mock('../../api/client', () => ({
  scheduleTokenRefresh: vi.fn(),
  clearRefreshTimer: vi.fn(),
  apiJson: vi.fn(),
}))

describe('AuthProvider', () => {
  beforeEach(() => {
    // Clear any stored tokens before each test
    clearTokens()
    vi.clearAllMocks()
  })

  afterEach(() => {
    clearTokens()
  })

  it('renders children when initialized', async () => {
    const { getByText } = render(
      <AuthProvider>
        <div>Child Content</div>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(getByText('Child Content')).toBeInTheDocument()
    })
  })

  it('schedules refresh for valid token', async () => {
    // Setup: store a valid token
    const validToken = 'valid-access-token'
    setTokens({ accessToken: validToken })
    
    // Token is not expired
    vi.mocked(jwtModule.isTokenExpired).mockReturnValue(false)

    const { getByText } = render(
      <AuthProvider>
        <div>Child Content</div>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(getByText('Child Content')).toBeInTheDocument()
    })

    // Should schedule refresh for valid token
    expect(clientModule.scheduleTokenRefresh).toHaveBeenCalledWith(validToken)
  })

  it('attempts refresh for expired token', async () => {
    // Setup: store an expired token
    const expiredToken = 'expired-access-token'
    const newToken = 'new-access-token'
    setTokens({ accessToken: expiredToken })
    
    // Token is expired
    vi.mocked(jwtModule.isTokenExpired).mockReturnValue(true)
    
    // Mock successful refresh
    vi.mocked(clientModule.apiJson).mockResolvedValue({
      access_token: newToken,
      expires_in: 3600,
    })

    const { getByText } = render(
      <AuthProvider>
        <div>Child Content</div>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(getByText('Child Content')).toBeInTheDocument()
    })

    // Should have attempted refresh
    expect(clientModule.apiJson).toHaveBeenCalledWith({
      method: 'POST',
      path: '/auth/refresh',
      auth: 'none',
      allowRefresh: false,
    })

    // Should schedule refresh for new token
    expect(clientModule.scheduleTokenRefresh).toHaveBeenCalledWith(newToken)

    // New token should be stored
    expect(getTokens().accessToken).toBe(newToken)
  })

  it('clears tokens when refresh fails', async () => {
    // Setup: store an expired token
    const expiredToken = 'expired-access-token'
    setTokens({ accessToken: expiredToken })
    
    // Token is expired
    vi.mocked(jwtModule.isTokenExpired).mockReturnValue(true)
    
    // Mock failed refresh
    vi.mocked(clientModule.apiJson).mockRejectedValue(new Error('Refresh failed'))

    const { getByText } = render(
      <AuthProvider>
        <div>Child Content</div>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(getByText('Child Content')).toBeInTheDocument()
    })

    // Tokens should be cleared
    expect(getTokens().accessToken).toBeNull()
  })

  it('clears tokens when refresh returns no token', async () => {
    // Setup: store an expired token
    const expiredToken = 'expired-access-token'
    setTokens({ accessToken: expiredToken })
    
    // Token is expired
    vi.mocked(jwtModule.isTokenExpired).mockReturnValue(true)
    
    // Mock refresh returning no token
    vi.mocked(clientModule.apiJson).mockResolvedValue({})

    const { getByText } = render(
      <AuthProvider>
        <div>Child Content</div>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(getByText('Child Content')).toBeInTheDocument()
    })

    // Tokens should be cleared
    expect(getTokens().accessToken).toBeNull()
  })

  it('clears refresh timer on unmount', async () => {
    const { unmount, getByText } = render(
      <AuthProvider>
        <div>Child Content</div>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(getByText('Child Content')).toBeInTheDocument()
    })

    unmount()

    expect(clientModule.clearRefreshTimer).toHaveBeenCalled()
  })

  it('handles no stored token gracefully', async () => {
    // No tokens stored
    
    const { getByText } = render(
      <AuthProvider>
        <div>Child Content</div>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(getByText('Child Content')).toBeInTheDocument()
    })

    // Should not attempt refresh
    expect(clientModule.apiJson).not.toHaveBeenCalled()
    expect(clientModule.scheduleTokenRefresh).not.toHaveBeenCalled()
  })
})
