import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '../../mocks/server'
import { http, HttpResponse } from 'msw'
import LoginPage from '../Login'
import { clearTokens, getTokens, setTokens } from '../../auth/tokenStore'

const BASE_URL = 'http://localhost:8000'

function createQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

// Wrapper with router + query client (needed for useOidcConfig hook)
function renderLogin(initialEntries: string[] = ['/login']) {
  const qc = createQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/library" element={<div>Library Page</div>} />
          <Route path="/set-initial-password" element={<div>Set Password Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    clearTokens()
    vi.clearAllMocks()
  })

  afterEach(() => {
    clearTokens()
  })

  it('renders login form', () => {
    renderLogin()

    expect(screen.getByPlaceholderText('Username')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
  })

  it('disables submit button when fields are empty', () => {
    renderLogin()

    const submitButton = screen.getByRole('button', { name: 'Login' })
    expect(submitButton).toBeDisabled()
  })

  it('enables submit button when username and password are filled', async () => {
    const user = userEvent.setup()
    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'testuser')
    await user.type(screen.getByPlaceholderText('Password'), 'testpass')

    const submitButton = screen.getByRole('button', { name: 'Login' })
    expect(submitButton).toBeEnabled()
  })

  it('submits login and redirects to library on success', async () => {
    const user = userEvent.setup()
    
    // Override handler for successful login
    server.use(
      http.post(`${BASE_URL}/auth/login`, () => {
        return HttpResponse.json({
          access_token: 'test-access-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      })
    )

    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'testuser')
    await user.type(screen.getByPlaceholderText('Password'), 'testpass')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => {
      expect(screen.getByText('Library Page')).toBeInTheDocument()
    })

    // Token should be stored
    expect(getTokens().accessToken).toBe('test-access-token')
  })

  it('shows error message on invalid credentials', async () => {
    const user = userEvent.setup()
    
    // Override handler for failed login
    server.use(
      http.post(`${BASE_URL}/auth/login`, () => {
        return HttpResponse.json(
          { detail: 'Invalid username or password' },
          { status: 401 }
        )
      })
    )

    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'baduser')
    await user.type(screen.getByPlaceholderText('Password'), 'badpass')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid username or password')).toBeInTheDocument()
    })
  })

  it('shows rate limit message on 429', async () => {
    const user = userEvent.setup()
    
    // Override handler for rate limit
    server.use(
      http.post(`${BASE_URL}/auth/login`, () => {
        return HttpResponse.json(
          { detail: 'Too many requests' },
          { 
            status: 429,
            headers: { 'Retry-After': '30' }
          }
        )
      })
    )

    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'testuser')
    await user.type(screen.getByPlaceholderText('Password'), 'testpass')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => {
      expect(screen.getByText(/Try again in 30s/)).toBeInTheDocument()
    })
  })

  it('redirects to set-initial-password on 403 with header', async () => {
    const user = userEvent.setup()
    
    // Override handler for password change required
    server.use(
      http.post(`${BASE_URL}/auth/login`, () => {
        return HttpResponse.json(
          { detail: 'Password change required' },
          { 
            status: 403,
            headers: { 'X-Password-Change-Required': 'true' }
          }
        )
      })
    )

    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'testuser')
    await user.type(screen.getByPlaceholderText('Password'), 'changeme')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => {
      expect(screen.getByText('Set Password Page')).toBeInTheDocument()
    })
  })

  it('redirects to set-initial-password on 403 with detail message fallback', async () => {
    const user = userEvent.setup()
    
    // Override handler with no X-Password-Change-Required header, but detail contains the path
    server.use(
      http.post(`${BASE_URL}/auth/login`, () => {
        return HttpResponse.json(
          { detail: 'Please use /auth/set-initial-password to reset your password' },
          { status: 403 }
        )
      })
    )

    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'testuser')
    await user.type(screen.getByPlaceholderText('Password'), 'changeme')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => {
      expect(screen.getByText('Set Password Page')).toBeInTheDocument()
    })
  })

  it('shows error message on 403 without password change redirect', async () => {
    const user = userEvent.setup()
    
    // Override handler for generic 403
    server.use(
      http.post(`${BASE_URL}/auth/login`, () => {
        return HttpResponse.json(
          { detail: 'Access denied' },
          { status: 403 }
        )
      })
    )

    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'testuser')
    await user.type(screen.getByPlaceholderText('Password'), 'testpass')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => {
      expect(screen.getByText('Access denied')).toBeInTheDocument()
    })
  })

  it('redirects to library if already logged in', () => {
    // Set existing token
    setTokens({ accessToken: 'existing-token' })

    renderLogin()

    expect(screen.getByText('Library Page')).toBeInTheDocument()
  })

  it('shows submitting state during login', async () => {
    const user = userEvent.setup()
    
    // Override handler with delay
    server.use(
      http.post(`${BASE_URL}/auth/login`, async () => {
        await new Promise(resolve => setTimeout(resolve, 100))
        return HttpResponse.json({
          access_token: 'test-access-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      })
    )

    renderLogin()

    await user.type(screen.getByPlaceholderText('Username'), 'testuser')
    await user.type(screen.getByPlaceholderText('Password'), 'testpass')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    // Button should show loading state
    expect(screen.getByRole('button', { name: '…' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '…' })).toBeDisabled()

    // Wait for completion
    await waitFor(() => {
      expect(screen.getByText('Library Page')).toBeInTheDocument()
    })
  })

  it('auto-redirects to OIDC provider when OIDC is enabled', async () => {
    const originalLocation = window.location.href
    // Mock window.location.href setter
    const hrefSetter = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { ...window.location, href: originalLocation },
      writable: true,
    })
    Object.defineProperty(window.location, 'href', {
      set: hrefSetter,
      get: () => originalLocation,
    })

    server.use(
      http.get(`${BASE_URL}/auth/oidc/config`, () => {
        return HttpResponse.json({ enabled: true, provider_name: 'Keycloak' })
      })
    )

    renderLogin()

    await waitFor(() => {
      expect(hrefSetter).toHaveBeenCalledWith(
        expect.stringContaining('https://auth.example.com/authorize')
      )
    })
  })

  it('shows redirecting message when OIDC is enabled', async () => {
    server.use(
      http.get(`${BASE_URL}/auth/oidc/config`, () => {
        return HttpResponse.json({ enabled: true, provider_name: 'Keycloak' })
      }),
      // Make start hang so we can see the redirecting state
      http.post(`${BASE_URL}/auth/oidc/start`, async () => {
        await new Promise(() => {}) // never resolves
        return HttpResponse.json({ auth_url: '', state: '' })
      })
    )

    renderLogin()

    await waitFor(() => {
      expect(screen.getByText(/Redirecting to Keycloak/)).toBeInTheDocument()
    })
  })

  it('shows login form with OIDC button when ?local=1 is set', async () => {
    server.use(
      http.get(`${BASE_URL}/auth/oidc/config`, () => {
        return HttpResponse.json({ enabled: true, provider_name: 'Keycloak' })
      })
    )

    renderLogin(['/login?local=1'])

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Username')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('Password')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Continue with Keycloak/ })).toBeInTheDocument()
    })
  })

  it('does not show OIDC button when OIDC is disabled', async () => {
    // Default mock returns enabled: false
    renderLogin()

    // Wait for the config query to settle
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
    })

    expect(screen.queryByRole('button', { name: /Continue with/ })).not.toBeInTheDocument()
  })
})
