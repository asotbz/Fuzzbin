import { MemoryRouter } from 'react-router-dom'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { setTokens, clearTokens, getTokens } from '../../../auth/tokenStore'
import { renderWithQueryClient } from '../../../test/testUtils'
import LibraryPage from './LibraryPage'

function mockOkJson(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function setupFetchMock(options?: { oidcLogoutUrl?: string | null; oidcLogoutStatus?: number }) {
  const oidcLogoutStatus = options?.oidcLogoutStatus ?? (options?.oidcLogoutUrl !== undefined ? 200 : 404)

  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)

    if (url.includes('/search/facets')) {
      return mockOkJson({
        tags: [{ value: 'rock', count: 3 }],
        genres: [{ value: 'alt', count: 2 }],
        years: [{ value: '1991', count: 1 }],
        directors: [{ value: 'sam', count: 1 }],
        total_videos: 3,
      })
    }

    if (url.includes('/videos')) {
      return mockOkJson({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 1,
      })
    }

    if (url.includes('/auth/oidc/logout-url')) {
      if (oidcLogoutStatus !== 200) {
        return new Response('Not found', { status: oidcLogoutStatus })
      }
      return mockOkJson({ logout_url: options?.oidcLogoutUrl ?? null })
    }

    if (url.includes('/auth/logout')) {
      return new Response(null, { status: 204 })
    }

    return new Response('Not found', { status: 404 })
  })

  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('LibraryPage', () => {
  beforeEach(() => {
    clearTokens()
    setTokens({ accessToken: 'test' })
    setupFetchMock()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders facet options when facets load', async () => {
    renderWithQueryClient(
      <MemoryRouter>
        <LibraryPage />
      </MemoryRouter>
    )

    const importLink = screen.getByRole('link', { name: /import/i })
    expect(importLink).toHaveAttribute('href', '/import')

    const tagsButton = await screen.findByRole('button', { name: /tags filters/i })
    await waitFor(() => expect(tagsButton).not.toBeDisabled())
    fireEvent.click(tagsButton)

    expect(await screen.findByRole('button', { name: /rock/i })).toBeInTheDocument()
  })

  it('initializes search from URL query param', async () => {
    renderWithQueryClient(
      <MemoryRouter initialEntries={['/library?search=nirvana']}>
        <LibraryPage />
      </MemoryRouter>
    )

    const input = await screen.findByLabelText('Search videos')
    expect(input).toHaveValue('nirvana')
  })

  it('logs out locally when OIDC logout URL is unavailable', async () => {
    const fetchMock = setupFetchMock({ oidcLogoutStatus: 404 })

    renderWithQueryClient(
      <MemoryRouter>
        <LibraryPage />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByRole('button', { name: /log out/i }))

    await waitFor(() => {
      expect(getTokens().accessToken).toBeNull()
    })

    const calledUrls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(calledUrls.some((url) => url.includes('/auth/oidc/logout-url'))).toBe(true)
    expect(calledUrls.some((url) => url.includes('/auth/logout'))).toBe(true)
  })

  it('redirects to IdP logout URL when available', async () => {
    const fetchMock = setupFetchMock({
      oidcLogoutUrl: 'https://auth.example.com/logout?post_logout_redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Flogin%3Flocal%3D1',
      oidcLogoutStatus: 200,
    })

    window.location.href = 'http://localhost:8000/library'

    renderWithQueryClient(
      <MemoryRouter>
        <LibraryPage />
      </MemoryRouter>
    )

    fireEvent.click(await screen.findByRole('button', { name: /log out/i }))

    await waitFor(() => {
      expect(window.location.href).toBe(
        'https://auth.example.com/logout?post_logout_redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Flogin%3Flocal%3D1'
      )
    })

    const calledUrls = fetchMock.mock.calls.map(([input]) => String(input))
    expect(calledUrls.some((url) => url.includes('/auth/logout'))).toBe(true)
  })
})
