import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

// Test credentials
export const TEST_USER = {
  username: 'testuser',
  password: 'testpassword',
}

export const TEST_TOKENS = {
  access_token: 'test-access-token',
  refresh_token: 'test-refresh-token',
}

export const REFRESHED_TOKENS = {
  access_token: 'refreshed-access-token',
  refresh_token: 'refreshed-refresh-token',
}

export const authHandlers = [
  // Login endpoint
  http.post(`${BASE_URL}/auth/login`, async ({ request }) => {
    const body = await request.json() as { username: string; password: string }

    if (body.username === TEST_USER.username && body.password === TEST_USER.password) {
      return HttpResponse.json(TEST_TOKENS)
    }

    // Invalid credentials
    return HttpResponse.json(
      { detail: 'Invalid username or password' },
      { status: 401 }
    )
  }),

  // Token refresh endpoint
  http.post(`${BASE_URL}/auth/refresh`, async ({ request }) => {
    const body = await request.json() as { refresh_token: string }

    if (body.refresh_token === TEST_TOKENS.refresh_token || body.refresh_token === REFRESHED_TOKENS.refresh_token) {
      return HttpResponse.json(REFRESHED_TOKENS)
    }

    return HttpResponse.json(
      { detail: 'Invalid refresh token' },
      { status: 401 }
    )
  }),

  // Logout endpoint
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
