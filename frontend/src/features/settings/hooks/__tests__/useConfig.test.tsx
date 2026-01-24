import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS, mockConfig } from '../../../../mocks/handlers'
import { useConfig } from '../useConfig'

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

describe('useConfig', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('fetches configuration', async () => {
    const { result } = renderHook(() => useConfig(), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toBeDefined()
    expect(result.current.data?.config).toBeDefined()
    expect(result.current.data?.config_path).toBeDefined()
  })

  it('returns config structure', async () => {
    const { result } = renderHook(() => useConfig(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.config).toEqual(mockConfig)
    expect(result.current.data?.config_path).toBe('/config/config.yaml')
  })

  it('includes library settings', async () => {
    const { result } = renderHook(() => useConfig(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.config.library).toBeDefined()
    expect(result.current.data?.config.library.library_dir).toBe('/music_videos')
  })

  it('includes API settings', async () => {
    const { result } = renderHook(() => useConfig(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.config.apis).toBeDefined()
    expect(result.current.data?.config.apis.imvdb.enabled).toBe(true)
  })
})
