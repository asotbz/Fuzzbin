/**
 * Override handlers for testing edge cases and error scenarios.
 * 
 * Usage in tests:
 *   import { server } from '../../mocks/server'
 *   import { rateLimitedLogin, expiredTokenHandler } from '../../mocks/handlers/overrides'
 * 
 *   beforeEach(() => {
 *     server.use(rateLimitedLogin) // Override just the login handler
 *   })
 */

import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

// === Auth Error Handlers ===

/**
 * Simulates rate limiting (429) on login with Retry-After header
 */
export const rateLimitedLogin = http.post(`${BASE_URL}/auth/login`, () => {
  return HttpResponse.json(
    { detail: 'Too many login attempts. Please try again later.' },
    {
      status: 429,
      headers: {
        'Retry-After': '60',
      },
    }
  )
})

/**
 * Simulates password rotation required (403 with special header)
 */
export const passwordRotationRequired = http.post(`${BASE_URL}/auth/login`, () => {
  return HttpResponse.json(
    { detail: 'Password change required' },
    {
      status: 403,
      headers: {
        'X-Password-Change-Required': 'true',
      },
    }
  )
})

/**
 * Simulates an expired/invalid token (401) that cannot be refreshed
 */
export const expiredTokenHandler = http.post(`${BASE_URL}/auth/refresh`, () => {
  return HttpResponse.json(
    { detail: 'Token has expired' },
    { status: 401 }
  )
})

// === API Error Handlers ===

/**
 * Simulates 401 Unauthorized on any authenticated endpoint
 */
export const unauthorizedHandler = http.get(`${BASE_URL}/videos`, () => {
  return HttpResponse.json(
    { detail: 'Not authenticated' },
    { status: 401 }
  )
})

/**
 * Simulates server error (500) on video list
 */
export const serverErrorHandler = http.get(`${BASE_URL}/videos`, () => {
  return HttpResponse.json(
    { detail: 'Internal server error' },
    { status: 500 }
  )
})

/**
 * Simulates network error (no response)
 */
export const networkErrorHandler = http.get(`${BASE_URL}/videos`, () => {
  return HttpResponse.error()
})

// === Add/Import Error Handlers ===

/**
 * Simulates import failure
 */
export const importFailedHandler = http.post(`${BASE_URL}/add/import`, () => {
  return HttpResponse.json(
    { detail: 'Failed to download video: Network timeout' },
    { status: 500 }
  )
})

/**
 * Simulates duplicate video detection
 */
export const duplicateVideoHandler = http.post(`${BASE_URL}/add/import`, () => {
  return HttpResponse.json(
    { detail: 'Video already exists in library', video_id: 1 },
    { status: 409 }
  )
})

// === Job Status Handlers ===

/**
 * Returns a job in failed state
 */
export const failedJobHandler = http.get(`${BASE_URL}/jobs/:id`, () => {
  return HttpResponse.json({
    id: 'job-failed',
    type: 'import',
    status: 'failed',
    progress: 45,
    message: 'Download failed: Video unavailable',
    created_at: '2024-01-01T10:00:00Z',
    started_at: '2024-01-01T10:00:01Z',
    completed_at: '2024-01-01T10:00:30Z',
    error: 'Video is unavailable or has been removed',
    result: null,
  })
})
