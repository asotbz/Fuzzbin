import { describe, it, expect, beforeEach } from 'vitest'
import { server } from '../../mocks/server'
import { expiredTokenHandler } from '../../mocks/handlers/overrides'
import { TEST_TOKENS, REFRESHED_TOKENS } from '../../mocks/handlers'
import { apiJson, APIError } from '../client'
import { setTokens, clearTokens, getTokens } from '../../auth/tokenStore'

describe('apiJson', () => {
  beforeEach(() => {
    clearTokens()
  })

  describe('basic requests', () => {
    it('makes GET request and returns JSON', async () => {
      const result = await apiJson<{ items: unknown[] }>({ path: '/videos' })

      expect(result).toHaveProperty('items')
      expect(Array.isArray(result.items)).toBe(true)
    })

    it('makes POST request with body', async () => {
      setTokens({ accessToken: TEST_TOKENS.access_token })

      const result = await apiJson<{ results?: unknown[] }>({
        method: 'POST',
        path: '/add/search',
        body: { artist: 'Test Artist', track_title: 'Test Song', imvdb_per_page: 10, discogs_per_page: 10, youtube_max_results: 10 },
      })

      expect(result).toHaveProperty('results')
    })

    it('includes Authorization header when tokens exist', async () => {
      setTokens({ accessToken: TEST_TOKENS.access_token })

      // Should not throw 401 because we have a token
      const result = await apiJson<{ username: string }>({ path: '/auth/me' })
      expect(result.username).toBe('testuser')
    })

    it('does not include Authorization header when auth is "none"', async () => {
      setTokens({ accessToken: TEST_TOKENS.access_token })

      // Login endpoint doesn't require auth
      const result = await apiJson<{ access_token: string }>({
        method: 'POST',
        path: '/auth/login',
        body: { username: 'testuser', password: 'testpassword' },
        auth: 'none',
      })

      expect(result.access_token).toBe(TEST_TOKENS.access_token)
    })
  })

  describe('error handling', () => {
    it('throws APIError with status code on failure', async () => {
      await expect(
        apiJson({
          method: 'POST',
          path: '/auth/login',
          body: { username: 'wrong', password: 'wrong' },
          auth: 'none',
        })
      ).rejects.toThrow(APIError)

      try {
        await apiJson({
          method: 'POST',
          path: '/auth/login',
          body: { username: 'wrong', password: 'wrong' },
          auth: 'none',
        })
      } catch (e) {
        expect(e).toBeInstanceOf(APIError)
        expect((e as APIError).status).toBe(401)
        expect((e as APIError).message).toBe('Invalid username or password')
      }
    })

    it('extracts Retry-After header into retryAfterSeconds', async () => {
      // Use the rate limited handler
      const { rateLimitedLogin } = await import('../../mocks/handlers/overrides')
      server.use(rateLimitedLogin)

      try {
        await apiJson({
          method: 'POST',
          path: '/auth/login',
          body: { username: 'testuser', password: 'testpassword' },
          auth: 'none',
        })
        expect.fail('Should have thrown')
      } catch (e) {
        expect(e).toBeInstanceOf(APIError)
        expect((e as APIError).status).toBe(429)
        expect((e as APIError).retryAfterSeconds).toBe(60)
      }
    })
  })

  describe('token refresh', () => {
    it('automatically refreshes token on 401 and retries request', async () => {
      // Start with an expired access token
      // The refresh token is in an httpOnly cookie (handled by browser/mock)
      setTokens({ accessToken: 'expired-token' })

      // This request should:
      // 1. Fail with 401 (expired-token is rejected by /auth/me mock)
      // 2. Call /auth/refresh (browser sends httpOnly cookie)
      // 3. Retry original request with new access token
      const result = await apiJson<{ username: string }>({ path: '/auth/me' })

      expect(result.username).toBe('testuser')

      // Verify access token was refreshed
      const tokens = getTokens()
      expect(tokens.accessToken).toBe(REFRESHED_TOKENS.access_token)
    })

    it('clears tokens and throws when refresh fails', async () => {
      server.use(expiredTokenHandler)

      // Use expired access token (refresh will fail because mock returns 401)
      setTokens({ accessToken: 'expired-token' })

      await expect(
        apiJson({ path: '/auth/me' })
      ).rejects.toThrow(APIError)

      // Access token should be cleared after failed refresh
      const tokens = getTokens()
      expect(tokens.accessToken).toBeNull()
    })

    it('does not attempt refresh for login endpoint', async () => {
      // Even with expired tokens, login should not trigger refresh
      setTokens({ accessToken: 'expired-token' })

      const result = await apiJson<{ access_token: string }>({
        method: 'POST',
        path: '/auth/login',
        body: { username: 'testuser', password: 'testpassword' },
        auth: 'none',
      })

      expect(result.access_token).toBe(TEST_TOKENS.access_token)
    })

    it('does not attempt refresh when allowRefresh is false', async () => {
      // Use expired token
      setTokens({ accessToken: 'expired-token' })

      await expect(
        apiJson({
          path: '/auth/me',
          allowRefresh: false,
        })
      ).rejects.toThrow(APIError)
    })
  })
})

describe('APIError', () => {
  it('creates error with message and status', () => {
    const error = new APIError('Not found', 404)

    expect(error.message).toBe('Not found')
    expect(error.status).toBe(404)
    expect(error.name).toBe('APIError')
    expect(error.retryAfterSeconds).toBeUndefined()
  })

  it('includes retryAfterSeconds when provided', () => {
    const error = new APIError('Rate limited', 429, 30)

    expect(error.status).toBe(429)
    expect(error.retryAfterSeconds).toBe(30)
  })
})
