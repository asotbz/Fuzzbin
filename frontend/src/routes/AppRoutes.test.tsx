import { MemoryRouter } from 'react-router-dom'
import { screen } from '@testing-library/react'
import AppRoutes from './AppRoutes'
import { clearTokens, setTokens } from '../auth/tokenStore'
import { renderWithQueryClient } from '../test/testUtils'

function mockOkJson(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('routing', () => {
  beforeEach(() => {
    clearTokens()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
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
          items: [
            {
              id: 1,
              title: 'Smells Like Teen Spirit',
              artist: 'Nirvana',
              year: 1991,
              duration: 301,
              status: 'ready',
              tags: [{ name: 'rock' }],
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
          total_pages: 1,
        })
      }

      return new Response('Not found', { status: 404 })
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects unauthenticated users to /login', () => {
    renderWithQueryClient(
      <MemoryRouter initialEntries={['/library']}>
        <AppRoutes />
      </MemoryRouter>
    )

    expect(screen.getByPlaceholderText('Username')).toBeInTheDocument()
  })

  it('redirects / to /library when authenticated', async () => {
    setTokens({ accessToken: 'test' })

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>
    )

    expect(await screen.findByText('Video Library')).toBeInTheDocument()
  })

  it('renders /import when authenticated', async () => {
    setTokens({ accessToken: 'test' })

    renderWithQueryClient(
      <MemoryRouter initialEntries={['/import']}>
        <AppRoutes />
      </MemoryRouter>
    )

    expect(await screen.findByText('Artist/Title Search')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^search$/i })).toHaveAttribute('href', '/import')
    expect(screen.getByRole('link', { name: /spotify playlist/i })).toHaveAttribute('href', '/import/spotify')
    expect(screen.getByRole('link', { name: /nfo scan/i })).toHaveAttribute('href', '/import/nfo')
  })
})
