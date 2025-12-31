import { describe, it, expect, beforeEach } from 'vitest'
import {
  getTokens,
  setTokens,
  clearTokens,
  subscribe,
} from '../tokenStore'

describe('tokenStore', () => {
  beforeEach(() => {
    clearTokens()
  })

  describe('getTokens', () => {
    it('returns null tokens initially', () => {
      const tokens = getTokens()

      expect(tokens.accessToken).toBeNull()
      expect(tokens.refreshToken).toBeNull()
    })
  })

  describe('setTokens', () => {
    it('stores access and refresh tokens', () => {
      setTokens({
        accessToken: 'test-access-token',
        refreshToken: 'test-refresh-token',
      })

      const tokens = getTokens()
      expect(tokens.accessToken).toBe('test-access-token')
      expect(tokens.refreshToken).toBe('test-refresh-token')
    })

    it('overwrites existing tokens', () => {
      setTokens({
        accessToken: 'first-access',
        refreshToken: 'first-refresh',
      })

      setTokens({
        accessToken: 'second-access',
        refreshToken: 'second-refresh',
      })

      const tokens = getTokens()
      expect(tokens.accessToken).toBe('second-access')
      expect(tokens.refreshToken).toBe('second-refresh')
    })
  })

  describe('clearTokens', () => {
    it('clears stored tokens', () => {
      setTokens({
        accessToken: 'test-access',
        refreshToken: 'test-refresh',
      })

      clearTokens()

      const tokens = getTokens()
      expect(tokens.accessToken).toBeNull()
      expect(tokens.refreshToken).toBeNull()
    })
  })

  describe('subscribe', () => {
    it('calls listener when tokens are set', () => {
      const listener = vi.fn()
      const unsubscribe = subscribe(listener)

      setTokens({
        accessToken: 'new-access',
        refreshToken: 'new-refresh',
      })

      expect(listener).toHaveBeenCalledTimes(1)
      unsubscribe()
    })

    it('calls listener when tokens are cleared', () => {
      const listener = vi.fn()
      const unsubscribe = subscribe(listener)

      setTokens({
        accessToken: 'test',
        refreshToken: 'test',
      })
      listener.mockClear()

      clearTokens()

      expect(listener).toHaveBeenCalledTimes(1)
      unsubscribe()
    })

    it('unsubscribes correctly', () => {
      const listener = vi.fn()
      const unsubscribe = subscribe(listener)

      unsubscribe()

      setTokens({
        accessToken: 'new-access',
        refreshToken: 'new-refresh',
      })

      expect(listener).not.toHaveBeenCalled()
    })

    it('supports multiple listeners', () => {
      const listener1 = vi.fn()
      const listener2 = vi.fn()
      const unsub1 = subscribe(listener1)
      const unsub2 = subscribe(listener2)

      setTokens({
        accessToken: 'test',
        refreshToken: 'test',
      })

      expect(listener1).toHaveBeenCalledTimes(1)
      expect(listener2).toHaveBeenCalledTimes(1)

      unsub1()
      unsub2()
    })

    it('only unsubscribes the correct listener', () => {
      const listener1 = vi.fn()
      const listener2 = vi.fn()
      const unsub1 = subscribe(listener1)
      subscribe(listener2)

      unsub1()

      setTokens({
        accessToken: 'test',
        refreshToken: 'test',
      })

      expect(listener1).not.toHaveBeenCalled()
      expect(listener2).toHaveBeenCalledTimes(1)
    })
  })
})
