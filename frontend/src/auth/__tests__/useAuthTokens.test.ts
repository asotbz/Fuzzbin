import { describe, it, expect, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAuthTokens } from '../useAuthTokens'
import { setTokens, clearTokens } from '../tokenStore'

describe('useAuthTokens', () => {
  afterEach(() => {
    clearTokens()
  })

  it('returns current tokens', () => {
    const { result } = renderHook(() => useAuthTokens())

    expect(result.current.accessToken).toBeNull()
  })

  it('updates when tokens change', () => {
    const { result } = renderHook(() => useAuthTokens())

    act(() => {
      setTokens({ accessToken: 'new-token' })
    })

    expect(result.current.accessToken).toBe('new-token')
  })

  it('updates when tokens are cleared', () => {
    setTokens({ accessToken: 'existing-token' })
    const { result } = renderHook(() => useAuthTokens())

    expect(result.current.accessToken).toBe('existing-token')

    act(() => {
      clearTokens()
    })

    expect(result.current.accessToken).toBeNull()
  })
})
