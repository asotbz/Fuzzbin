import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { decodeJwt, isTokenExpired, getTokenExpiryMs } from '../jwt'

describe('jwt utilities', () => {
  describe('decodeJwt', () => {
    it('decodes a valid JWT token', () => {
      // Create a valid JWT with known payload
      // Payload: { "sub": "testuser", "user_id": 123, "exp": 1700000000, "iat": 1699990000, "type": "access" }
      const payload = {
        sub: 'testuser',
        user_id: 123,
        exp: 1700000000,
        iat: 1699990000,
        type: 'access',
      }
      const encodedPayload = btoa(JSON.stringify(payload))
      const token = `header.${encodedPayload}.signature`

      const result = decodeJwt(token)

      expect(result).toEqual(payload)
    })

    it('handles URL-safe base64 encoding', () => {
      // Payload with characters that get URL-safe encoded (+ becomes -, / becomes _)
      const payload = { sub: 'test+user/name', exp: 1700000000 }
      // Manually create URL-safe base64
      const base64 = btoa(JSON.stringify(payload))
      const urlSafeBase64 = base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
      const token = `header.${urlSafeBase64}.signature`

      const result = decodeJwt(token)

      expect(result?.sub).toBe('test+user/name')
    })

    it('returns null for token with wrong number of parts', () => {
      expect(decodeJwt('invalid')).toBeNull()
      expect(decodeJwt('only.two')).toBeNull()
      expect(decodeJwt('too.many.parts.here')).toBeNull()
    })

    it('returns null for token with invalid base64', () => {
      const token = 'header.!!!invalid-base64!!!.signature'

      const result = decodeJwt(token)

      expect(result).toBeNull()
    })

    it('returns null for token with invalid JSON payload', () => {
      const invalidJson = btoa('not valid json')
      const token = `header.${invalidJson}.signature`

      const result = decodeJwt(token)

      expect(result).toBeNull()
    })

    it('handles empty payload gracefully', () => {
      const emptyPayload = btoa('{}')
      const token = `header.${emptyPayload}.signature`

      const result = decodeJwt(token)

      expect(result).toEqual({})
    })

    it('handles payload with only some claims', () => {
      const payload = { exp: 1700000000 }
      const token = `header.${btoa(JSON.stringify(payload))}.signature`

      const result = decodeJwt(token)

      expect(result).toEqual({ exp: 1700000000 })
      expect(result?.sub).toBeUndefined()
      expect(result?.user_id).toBeUndefined()
    })
  })

  describe('isTokenExpired', () => {
    beforeEach(() => {
      // Mock Date.now to return a fixed timestamp
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2024-01-15T12:00:00Z'))
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('returns false for non-expired token', () => {
      // Token expires in 1 hour (3600 seconds from "now")
      const futureExp = Math.floor(Date.now() / 1000) + 3600
      const token = createToken({ exp: futureExp })

      expect(isTokenExpired(token)).toBe(false)
    })

    it('returns true for expired token', () => {
      // Token expired 1 hour ago
      const pastExp = Math.floor(Date.now() / 1000) - 3600
      const token = createToken({ exp: pastExp })

      expect(isTokenExpired(token)).toBe(true)
    })

    it('returns true when token expires within buffer time', () => {
      // Token expires in 30 seconds, but default buffer is 60 seconds
      const soonExp = Math.floor(Date.now() / 1000) + 30
      const token = createToken({ exp: soonExp })

      expect(isTokenExpired(token)).toBe(true)
    })

    it('returns false when token expires after buffer time', () => {
      // Token expires in 120 seconds, buffer is 60 seconds
      const laterExp = Math.floor(Date.now() / 1000) + 120
      const token = createToken({ exp: laterExp })

      expect(isTokenExpired(token)).toBe(false)
    })

    it('uses custom buffer time', () => {
      // Token expires in 100 seconds
      const exp = Math.floor(Date.now() / 1000) + 100
      const token = createToken({ exp })

      // With 50-second buffer, should not be expired
      expect(isTokenExpired(token, 50)).toBe(false)

      // With 150-second buffer, should be expired
      expect(isTokenExpired(token, 150)).toBe(true)
    })

    it('returns true for token without exp claim', () => {
      const token = createToken({ sub: 'testuser' })

      expect(isTokenExpired(token)).toBe(true)
    })

    it('returns true for invalid token', () => {
      expect(isTokenExpired('invalid-token')).toBe(true)
    })
  })

  describe('getTokenExpiryMs', () => {
    beforeEach(() => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date('2024-01-15T12:00:00Z'))
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('returns milliseconds until token expiry', () => {
      // Token expires in 1 hour (3600 seconds)
      const futureExp = Math.floor(Date.now() / 1000) + 3600
      const token = createToken({ exp: futureExp })

      const result = getTokenExpiryMs(token)

      // Should be approximately 3600000 ms (1 hour)
      expect(result).toBe(3600000)
    })

    it('returns 0 for expired token', () => {
      // Token expired 1 hour ago
      const pastExp = Math.floor(Date.now() / 1000) - 3600
      const token = createToken({ exp: pastExp })

      const result = getTokenExpiryMs(token)

      expect(result).toBe(0)
    })

    it('returns 0 for token without exp claim', () => {
      const token = createToken({ sub: 'testuser' })

      const result = getTokenExpiryMs(token)

      expect(result).toBe(0)
    })

    it('returns 0 for invalid token', () => {
      const result = getTokenExpiryMs('invalid-token')

      expect(result).toBe(0)
    })

    it('returns exact milliseconds for precise timing', () => {
      // Token expires exactly 500ms from now
      const nowMs = Date.now()
      const expSeconds = Math.floor(nowMs / 1000) + 1 // 1 second from now
      const token = createToken({ exp: expSeconds })

      const result = getTokenExpiryMs(token)

      // Result should be 1000ms (token exp is rounded to seconds)
      expect(result).toBe(1000)
    })
  })
})

/**
 * Helper to create a JWT token with given payload
 */
function createToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const encodedPayload = btoa(JSON.stringify(payload))
  return `${header}.${encodedPayload}.fake-signature`
}
