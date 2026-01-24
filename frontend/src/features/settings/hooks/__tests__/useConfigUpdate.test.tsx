import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS } from '../../../../mocks/handlers'
import { useConfigUpdate } from '../useConfigUpdate'
import { Toaster } from 'sonner'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  })

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster />
    </QueryClientProvider>
  )
}

describe('useConfigUpdate', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('returns mutation functions', () => {
    const { result } = renderHook(() => useConfigUpdate(), {
      wrapper: createWrapper(),
    })

    expect(result.current.mutate).toBeDefined()
    expect(result.current.mutateAsync).toBeDefined()
    expect(result.current.isPending).toBe(false)
  })

  it('updates config successfully', async () => {
    const { result } = renderHook(() => useConfigUpdate(), {
      wrapper: createWrapper(),
    })

    await act(async () => {
      result.current.mutate({
        updates: { 'logging.level': 'DEBUG' },
        description: 'Test update',
      })
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.updated_fields).toContain('logging.level')
    expect(result.current.data?.safety_level).toBe('safe')
  })

  it('handles 409 errors for unsafe changes without force', async () => {
    const { result } = renderHook(() => useConfigUpdate(), {
      wrapper: createWrapper(),
    })

    await act(async () => {
      result.current.mutate({
        updates: { 'library.library_dir': '/new/path' },
        force: false,
      })
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    // The mutation should fail with a 409 error
    expect(result.current.error).toBeDefined()
  })

  it('succeeds with force=true for unsafe changes', async () => {
    const { result } = renderHook(() => useConfigUpdate(), {
      wrapper: createWrapper(),
    })

    await act(async () => {
      result.current.mutate({
        updates: { 'library.library_dir': '/new/path' },
        force: true,
      })
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })
  })
})
