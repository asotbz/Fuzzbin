import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { useYouTubeMetadata } from '../useYouTubeMetadata'

const BASE_URL = 'http://localhost:8000'

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('useYouTubeMetadata', () => {
  it('returns null data and is not loading when youtubeId is null', () => {
    const { result } = renderHook(() => useYouTubeMetadata(null), {
      wrapper: makeWrapper(),
    })
    expect(result.current.data).toBeNull()
    expect(result.current.isLoading).toBe(false)
  })

  it('returns null data and is not loading when youtubeId is an empty string', () => {
    const { result } = renderHook(() => useYouTubeMetadata(''), {
      wrapper: makeWrapper(),
    })
    expect(result.current.data).toBeNull()
    expect(result.current.isLoading).toBe(false)
  })

  it('fetches metadata when a youtubeId is provided', async () => {
    const { result } = renderHook(() => useYouTubeMetadata('yt-abc123'), {
      wrapper: makeWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => expect(result.current.data).not.toBeNull())
    expect(result.current.data?.youtube_id).toBe('yt-abc123')
    expect(result.current.data?.available).toBe(true)
    expect(result.current.isLoading).toBe(false)
  })

  it('reports an unavailable video', async () => {
    const { result } = renderHook(
      () => useYouTubeMetadata('unavailable-video'),
      { wrapper: makeWrapper() }
    )

    await waitFor(() => expect(result.current.data).not.toBeNull())
    expect(result.current.data?.available).toBe(false)
    expect(result.current.data?.error).toBe('Video unavailable')
  })

  it('returns null data on server error (no throw)', async () => {
    server.use(
      http.post(`${BASE_URL}/add/youtube/metadata`, () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 })
      )
    )

    const { result } = renderHook(() => useYouTubeMetadata('error-id'), {
      wrapper: makeWrapper(),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false), {
      timeout: 3000,
    })
    expect(result.current.data).toBeNull()
  })
})
