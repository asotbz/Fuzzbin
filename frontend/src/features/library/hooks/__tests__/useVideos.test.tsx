import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS } from '../../../../mocks/handlers'
import { useVideos } from '../useVideos'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
      },
    },
  })

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('useVideos', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('fetches videos with default query', async () => {
    const { result } = renderHook(() => useVideos({ page: 1, page_size: 20 }), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toBeDefined()
    expect(result.current.data?.items).toBeDefined()
    expect(Array.isArray(result.current.data?.items)).toBe(true)
  })

  it('fetches videos with search query', async () => {
    const { result } = renderHook(
      () => useVideos({ page: 1, page_size: 20, title: 'Test Video 1' }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.items).toHaveLength(1)
    expect(result.current.data?.items[0].title).toBe('Test Video 1')
  })

  it('returns paginated response structure', async () => {
    const { result } = renderHook(() => useVideos({ page: 1, page_size: 20 }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toHaveProperty('items')
    expect(result.current.data).toHaveProperty('total')
    expect(result.current.data).toHaveProperty('page')
    expect(result.current.data).toHaveProperty('page_size')
  })

  it('returns empty results for non-matching query', async () => {
    const { result } = renderHook(
      () => useVideos({ page: 1, page_size: 20, title: 'nonexistent' }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.items).toHaveLength(0)
    expect(result.current.data?.total).toBe(0)
  })
})
