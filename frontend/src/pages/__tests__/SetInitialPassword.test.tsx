import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { server } from '../../mocks/server'
import { http, HttpResponse } from 'msw'
import SetInitialPasswordPage from '../SetInitialPassword'
import { clearTokens, getTokens, setTokens } from '../../auth/tokenStore'

const BASE_URL = 'http://localhost:8000'

function renderSetPassword(
  initialPath = '/set-initial-password',
  state?: { currentPassword?: string }
) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: initialPath, state }]}>
      <Routes>
        <Route path="/set-initial-password" element={<SetInitialPasswordPage />} />
        <Route path="/library" element={<div>Library Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('SetInitialPasswordPage', () => {
  beforeEach(() => {
    clearTokens()
    vi.clearAllMocks()
  })

  afterEach(() => {
    clearTokens()
  })

  it('renders password form', () => {
    renderSetPassword()

    expect(screen.getByPlaceholderText('Username')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Current password')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('New password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Set password' })).toBeInTheDocument()
  })

  it('disables submit button when fields are incomplete', () => {
    renderSetPassword()

    expect(screen.getByRole('button', { name: 'Set password' })).toBeDisabled()
  })

  it('requires new password to be at least 8 characters', async () => {
    const user = userEvent.setup()
    renderSetPassword()

    await user.type(screen.getByPlaceholderText('Username'), 'admin')
    await user.type(screen.getByPlaceholderText('Current password'), 'oldpass')
    await user.type(screen.getByPlaceholderText('New password'), 'short') // 5 chars

    expect(screen.getByRole('button', { name: 'Set password' })).toBeDisabled()

    await user.clear(screen.getByPlaceholderText('New password'))
    await user.type(screen.getByPlaceholderText('New password'), 'longenough') // 10 chars

    expect(screen.getByRole('button', { name: 'Set password' })).toBeEnabled()
  })

  it('enables submit button when all fields are valid', async () => {
    const user = userEvent.setup()
    renderSetPassword()

    await user.type(screen.getByPlaceholderText('Username'), 'admin')
    await user.type(screen.getByPlaceholderText('Current password'), 'oldpassword')
    await user.type(screen.getByPlaceholderText('New password'), 'newpassword123')

    expect(screen.getByRole('button', { name: 'Set password' })).toBeEnabled()
  })

  it('submits password change and redirects on success', async () => {
    const user = userEvent.setup()

    server.use(
      http.post(`${BASE_URL}/auth/set-initial-password`, () => {
        return HttpResponse.json({
          access_token: 'new-access-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      })
    )

    renderSetPassword()

    await user.type(screen.getByPlaceholderText('Username'), 'admin')
    await user.type(screen.getByPlaceholderText('Current password'), 'changeme')
    await user.type(screen.getByPlaceholderText('New password'), 'newsecurepassword')
    await user.click(screen.getByRole('button', { name: 'Set password' }))

    await waitFor(() => {
      expect(screen.getByText('Library Page')).toBeInTheDocument()
    })

    expect(getTokens().accessToken).toBe('new-access-token')
  })

  it('shows error on invalid current password', async () => {
    const user = userEvent.setup()

    server.use(
      http.post(`${BASE_URL}/auth/set-initial-password`, () => {
        return HttpResponse.json(
          { detail: 'Invalid current password' },
          { status: 401 }
        )
      })
    )

    renderSetPassword()

    await user.type(screen.getByPlaceholderText('Username'), 'admin')
    await user.type(screen.getByPlaceholderText('Current password'), 'wrongpass')
    await user.type(screen.getByPlaceholderText('New password'), 'newsecurepassword')
    await user.click(screen.getByRole('button', { name: 'Set password' }))

    await waitFor(() => {
      expect(screen.getByText('Invalid current password')).toBeInTheDocument()
    })
  })

  it('shows rate limit message on 429', async () => {
    const user = userEvent.setup()

    server.use(
      http.post(`${BASE_URL}/auth/set-initial-password`, () => {
        return HttpResponse.json(
          { detail: 'Too many requests' },
          {
            status: 429,
            headers: { 'Retry-After': '30' },
          }
        )
      })
    )

    renderSetPassword()

    await user.type(screen.getByPlaceholderText('Username'), 'admin')
    await user.type(screen.getByPlaceholderText('Current password'), 'oldpass')
    await user.type(screen.getByPlaceholderText('New password'), 'newsecurepassword')
    await user.click(screen.getByRole('button', { name: 'Set password' }))

    await waitFor(() => {
      expect(screen.getByText(/Try again in 30s/)).toBeInTheDocument()
    })
  })

  it('redirects to library if already logged in', () => {
    setTokens({ accessToken: 'existing-token' })

    renderSetPassword()

    expect(screen.getByText('Library Page')).toBeInTheDocument()
  })

  it('shows submitting state during request', async () => {
    const user = userEvent.setup()

    server.use(
      http.post(`${BASE_URL}/auth/set-initial-password`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json({
          access_token: 'new-token',
          token_type: 'bearer',
          expires_in: 3600,
        })
      })
    )

    renderSetPassword()

    await user.type(screen.getByPlaceholderText('Username'), 'admin')
    await user.type(screen.getByPlaceholderText('Current password'), 'oldpass')
    await user.type(screen.getByPlaceholderText('New password'), 'newsecurepassword')
    await user.click(screen.getByRole('button', { name: 'Set password' }))

    expect(screen.getByRole('button', { name: '…' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '…' })).toBeDisabled()

    await waitFor(() => {
      expect(screen.getByText('Library Page')).toBeInTheDocument()
    })
  })

  describe('pre-filled flow (from login)', () => {
    it('hides current password field when pre-filled from state', () => {
      render(
        <MemoryRouter
          initialEntries={[{
            pathname: '/set-initial-password',
            search: '?username=admin',
            state: { currentPassword: 'changeme' },
          }]}
        >
          <Routes>
            <Route path="/set-initial-password" element={<SetInitialPasswordPage />} />
            <Route path="/library" element={<div>Library Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByPlaceholderText('Username')).toBeInTheDocument()
      expect(screen.queryByPlaceholderText('Current password')).not.toBeInTheDocument()
      expect(screen.getByText('Choose a new password for your account')).toBeInTheDocument()
    })

    it('disables username field when pre-filled', () => {
      render(
        <MemoryRouter
          initialEntries={[{
            pathname: '/set-initial-password',
            search: '?username=admin',
            state: { currentPassword: 'changeme' },
          }]}
        >
          <Routes>
            <Route path="/set-initial-password" element={<SetInitialPasswordPage />} />
            <Route path="/library" element={<div>Library Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByPlaceholderText('Username')).toBeDisabled()
      expect(screen.getByPlaceholderText('Username')).toHaveValue('admin')
    })

    it('can submit with pre-filled credentials', async () => {
      const user = userEvent.setup()

      server.use(
        http.post(`${BASE_URL}/auth/set-initial-password`, () => {
          return HttpResponse.json({
            access_token: 'new-access-token',
            token_type: 'bearer',
            expires_in: 3600,
          })
        })
      )

      render(
        <MemoryRouter
          initialEntries={[{
            pathname: '/set-initial-password',
            search: '?username=admin',
            state: { currentPassword: 'changeme' },
          }]}
        >
          <Routes>
            <Route path="/set-initial-password" element={<SetInitialPasswordPage />} />
            <Route path="/library" element={<div>Library Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      await user.type(screen.getByPlaceholderText('New password'), 'newsecurepassword')
      await user.click(screen.getByRole('button', { name: 'Set password' }))

      await waitFor(() => {
        expect(screen.getByText('Library Page')).toBeInTheDocument()
      })
    })
  })
})
