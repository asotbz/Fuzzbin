import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getTokens,
  setTokens,
  clearTokens,
  subscribe,
  loadTokens,
} from '../tokenStore'

describe('tokenStore', () => {
  beforeEach(() => {
    clearTokens()
    localStorage.clear()
  })

  describe('getTokens', () => {
    it('returns null token initially', () => {
      const tokens = getTokens()

      expect(tokens.accessToken).toBeNull()
    })
  })

  describe('setTokens', () => {
    it('stores access token in memory and localStorage', () => {
      setTokens({
        accessToken: 'test-access-token',
      })

      const tokens = getTokens()
      expect(tokens.accessToken).toBe('test-access-token')
      expect(localStorage.getItem('fuzzbin_access_token')).toBe('test-access-token')
    })

    it('overwrites existing tokens', () => {
      setTokens({
        accessToken: 'first-access',
      })

      setTokens({
        accessToken: 'second-access',
      })

      const tokens = getTokens()
      expect(tokens.accessToken).toBe('second-access')
    })
  })

  describe('clearTokens', () => {
    it('clears stored tokens', () => {
      setTokens({
        accessToken: 'test-access',
      })

      clearTokens()

      const tokens = getTokens()
      expect(tokens.accessToken).toBeNull()
      expect(localStorage.getItem('fuzzbin_access_token')).toBeNull()
    })
  })

  describe('loadTokens', () => {
    it('loads token from localStorage', () => {
      localStorage.setItem('fuzzbin_access_token', 'stored-token')

      const hasToken = loadTokens()

      expect(hasToken).toBe(true)
      expect(getTokens().accessToken).toBe('stored-token')
    })

    it('returns false when no token in localStorage', () => {
      const hasToken = loadTokens()

      expect(hasToken).toBe(false)
      expect(getTokens().accessToken).toBeNull()
    })
  })

  describe('subscribe', () => {
    it('calls listener when tokens are set', () => {
      const listener = vi.fn()
      const unsubscribe = subscribe(listener)

      setTokens({
        accessToken: 'new-access',
      })

      expect(listener).toHaveBeenCalledTimes(1)
      unsubscribe()
    })

    it('calls listener when tokens are cleared', () => {
      const listener = vi.fn()
      const unsubscribe = subscribe(listener)

      setTokens({
        accessToken: 'test',
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
      })

      expect(listener1).not.toHaveBeenCalled()
      expect(listener2).toHaveBeenCalledTimes(1)
    })
  })
})
