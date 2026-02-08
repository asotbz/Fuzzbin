import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '../../mocks/server'
import { http, HttpResponse } from 'msw'
import OidcCallbackPage from '../OidcCallback'
import { clearTokens, getTokens } from '../../auth/tokenStore'

const BASE_URL = 'http://localhost:8000'

function createQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderCallback(searchParams: string = '') {
  const qc = createQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/oidc/callback${searchParams}`]}>
        <Routes>
          <Route path="/oidc/callback" element={<OidcCallbackPage />} />
          <Route path="/library" element={<div>Library Page</div>} />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('OidcCallbackPage', () => {
  beforeEach(() => {
    clearTokens()
    // Store the expected state in sessionStorage
    sessionStorage.setItem('oidc_state', 'valid-state')
  })

  afterEach(() => {
    clearTokens()
    sessionStorage.clear()
  })

  it('shows error when code is missing', () => {
    renderCallback('?state=valid-state')

    expect(screen.getByText(/Missing authorization code/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Back to login/ })).toBeInTheDocument()
  })

  it('shows error when state is missing', () => {
    renderCallback('?code=auth-code')

    expect(screen.getByText(/Missing authorization code/)).toBeInTheDocument()
  })

  it('shows error on state mismatch', () => {
    sessionStorage.setItem('oidc_state', 'expected-state')
    renderCallback('?code=auth-code&state=wrong-state')

    expect(screen.getByText(/State mismatch/)).toBeInTheDocument()
  })

  it('shows error on IdP error', () => {
    renderCallback('?error=access_denied&error_description=User+denied+consent')

    expect(screen.getByText(/User denied consent/)).toBeInTheDocument()
  })

  it('exchanges code and redirects on success', async () => {
    server.use(
      http.post(`${BASE_URL}/auth/oidc/exchange`, () => {
        return HttpResponse.json({
          access_token: 'oidc-access-token',
          token_type: 'bearer',
          expires_in: 1800,
        })
      })
    )

    renderCallback('?code=auth-code&state=valid-state')

    await waitFor(() => {
      expect(screen.getByText('Library Page')).toBeInTheDocument()
    })

    expect(getTokens().accessToken).toBe('oidc-access-token')
  })

  it('shows error on exchange failure', async () => {
    server.use(
      http.post(`${BASE_URL}/auth/oidc/exchange`, () => {
        return HttpResponse.json(
          { detail: 'Identity does not match' },
          { status: 403 }
        )
      })
    )

    renderCallback('?code=auth-code&state=valid-state')

    await waitFor(() => {
      expect(screen.getByText(/Identity does not match/)).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /Back to login/ })).toBeInTheDocument()
  })
})
