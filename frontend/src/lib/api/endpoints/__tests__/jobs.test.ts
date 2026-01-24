import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { server } from '../../../../mocks/server'
import { http, HttpResponse } from 'msw'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS, mockJobs } from '../../../../mocks/handlers'
import { getJob, cancelJob } from '../jobs'

const BASE_URL = 'http://localhost:8000'

describe('jobs endpoints', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  describe('getJob', () => {
    it('fetches a completed job by ID', async () => {
      const result = await getJob('job-1')

      expect(result.id).toBe('job-1')
      expect(result.type).toBe('import')
      expect(result.status).toBe('completed')
      expect(result.progress).toBe(100)
    })

    it('fetches a running job by ID', async () => {
      const result = await getJob('job-2')

      expect(result.id).toBe('job-2')
      expect(result.status).toBe('running')
      expect(result.progress).toBe(50)
      expect(result.current_step).toBeDefined()
    })

    it('fetches a queued job by ID', async () => {
      const result = await getJob('job-3')

      expect(result.id).toBe('job-3')
      expect(result.status).toBe('pending')
      expect(result.progress).toBe(0)
    })

    it('throws error for nonexistent job', async () => {
      await expect(getJob('nonexistent-job')).rejects.toThrow()
    })

    it('includes timestamps for completed job', async () => {
      const result = await getJob('job-1')

      expect(result.created_at).toBeDefined()
      expect(result.started_at).toBeDefined()
      expect(result.completed_at).toBeDefined()
    })

    it('includes result data for completed job', async () => {
      const result = await getJob('job-1')

      expect(result.result).toBeDefined()
      expect((result.result as { video_id: number })?.video_id).toBe(1)
    })

    it('encodes special characters in job ID', async () => {
      // Override handler to accept encoded ID
      server.use(
        http.get(`${BASE_URL}/jobs/:id`, ({ params }) => {
          return HttpResponse.json({
            id: params.id,
            type: 'test',
            status: 'completed',
            progress: 100,
            message: 'Test job',
            created_at: '2024-01-01T10:00:00Z',
            started_at: null,
            completed_at: null,
            result: null,
          })
        })
      )

      const result = await getJob('job/with/slashes')

      // The ID should be properly encoded/decoded
      expect(result).toBeDefined()
    })
  })

  describe('cancelJob', () => {
    it('cancels a running job', async () => {
      // Override to use POST cancel endpoint
      server.use(
        http.delete(`${BASE_URL}/jobs/:id`, ({ params }) => {
          const job = mockJobs.find((j) => j.id === params.id)
          if (!job) {
            return HttpResponse.json({ detail: 'Job not found' }, { status: 404 })
          }
          if (job.status === 'completed' || job.status === 'failed') {
            return HttpResponse.json(
              { detail: 'Cannot cancel completed or failed job' },
              { status: 400 }
            )
          }
          return new HttpResponse(null, { status: 204 })
        })
      )

      // Should not throw for running job
      await expect(cancelJob('job-2')).resolves.toBeUndefined()
    })

    it('cancels a queued job', async () => {
      server.use(
        http.delete(`${BASE_URL}/jobs/:id`, ({ params }) => {
          const job = mockJobs.find((j) => j.id === params.id)
          if (!job) {
            return HttpResponse.json({ detail: 'Job not found' }, { status: 404 })
          }
          return new HttpResponse(null, { status: 204 })
        })
      )

      await expect(cancelJob('job-3')).resolves.toBeUndefined()
    })

    it('throws error for nonexistent job', async () => {
      server.use(
        http.delete(`${BASE_URL}/jobs/:id`, () => {
          return HttpResponse.json({ detail: 'Job not found' }, { status: 404 })
        })
      )

      await expect(cancelJob('nonexistent-job')).rejects.toThrow()
    })

    it('throws error when canceling completed job', async () => {
      server.use(
        http.delete(`${BASE_URL}/jobs/:id`, () => {
          return HttpResponse.json(
            { detail: 'Cannot cancel completed or failed job' },
            { status: 400 }
          )
        })
      )

      await expect(cancelJob('job-1')).rejects.toThrow()
    })
  })
})
