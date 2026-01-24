import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS, mockConfigHistory } from '../../../../mocks/handlers'
import { useConfigHistory } from '../useConfigHistory'

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

describe('useConfigHistory', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('fetches config history', async () => {
    const { result } = renderHook(() => useConfigHistory(), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toBeDefined()
  })

  it('returns history entries', async () => {
    const { result } = renderHook(() => useConfigHistory(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.entries).toEqual(mockConfigHistory.entries)
    expect(result.current.data?.current_index).toBe(1)
  })

  it('includes undo/redo state', async () => {
    const { result } = renderHook(() => useConfigHistory(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.can_undo).toBe(true)
    expect(result.current.data?.can_redo).toBe(false)
  })
})
