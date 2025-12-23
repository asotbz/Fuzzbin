import { MemoryRouter } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { setTokens, clearTokens } from '../../../auth/tokenStore'
import { renderWithQueryClient } from '../../../test/testUtils'
import LibraryPage from './LibraryPage'

function mockOkJson(data: unknown) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('LibraryPage', () => {
  beforeEach(() => {
    clearTokens()
    setTokens({ accessToken: 'test', refreshToken: 'test' })

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
          items: [],
          total: 0,
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

  it('renders facet options when facets load', async () => {
    renderWithQueryClient(
      <MemoryRouter>
        <LibraryPage />
      </MemoryRouter>
    )

    expect(await screen.findByText('rock')).toBeInTheDocument()
  })
})
