import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

// Test credentials
export const TEST_USER = {
  username: 'testuser',
  password: 'testpassword',
}

// Access token response (refresh token is now in httpOnly cookie, not in response body)
export const TEST_TOKENS = {
  access_token: 'test-access-token',
  token_type: 'bearer',
  expires_in: 1800, // 30 minutes
}

export const REFRESHED_TOKENS = {
  access_token: 'refreshed-access-token',
  token_type: 'bearer',
  expires_in: 1800,
}

export const authHandlers = [
  // Login endpoint - returns access token, sets refresh token cookie
  http.post(`${BASE_URL}/auth/login`, async ({ request }) => {
    const body = await request.json() as { username: string; password: string }

    if (body.username === TEST_USER.username && body.password === TEST_USER.password) {
      // In real implementation, refresh token is set via Set-Cookie header
      // For mock purposes, we just return the access token
      return HttpResponse.json(TEST_TOKENS)
    }

    // Invalid credentials
    return HttpResponse.json(
      { detail: 'Invalid username or password' },
      { status: 401 }
    )
  }),

  // Token refresh endpoint - reads refresh token from cookie, not body
  http.post(`${BASE_URL}/auth/refresh`, () => {
    // In tests, we assume the httpOnly cookie exists and is valid
    // Real browser would send it automatically
    return HttpResponse.json(REFRESHED_TOKENS)
  }),

  // Logout endpoint - clears refresh token cookie
  http.post(`${BASE_URL}/auth/logout`, () => {
    return new HttpResponse(null, { status: 204 })
  }),

  // Who am I endpoint
  http.get(`${BASE_URL}/auth/me`, ({ request }) => {
    const authHeader = request.headers.get('Authorization')

    if (!authHeader?.startsWith('Bearer ')) {
      return HttpResponse.json(
        { detail: 'Not authenticated' },
        { status: 401 }
      )
    }

    // Check for expired token
    const token = authHeader.replace('Bearer ', '')
    if (token === 'expired-token') {
      return HttpResponse.json(
        { detail: 'Token has expired' },
        { status: 401 }
      )
    }

    return HttpResponse.json({
      username: TEST_USER.username,
      id: 1,
    })
  }),
]
