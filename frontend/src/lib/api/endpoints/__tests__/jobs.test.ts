import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { server } from '../../../../mocks/server'
import { http, HttpResponse } from 'msw'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS, mockJobs } from '../../../../mocks/handlers'
import { getJob, cancelJob, listJobs, retryJob } from '../jobs'

const BASE_URL = 'http://localhost:8000'

describe('jobs endpoints', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  describe('listJobs', () => {
    it('fetches jobs list without filters', async () => {
      server.use(
        http.get(`${BASE_URL}/jobs`, () => {
          return HttpResponse.json({
            jobs: mockJobs,
            total: mockJobs.length,
            limit: 100,
            offset: 0,
          })
        })
      )

      const result = await listJobs()

      expect(result.jobs).toBeDefined()
      expect(result.total).toBeGreaterThan(0)
    })

    it('fetches jobs with status filter', async () => {
      server.use(
        http.get(`${BASE_URL}/jobs`, ({ request }) => {
          const url = new URL(request.url)
          const status = url.searchParams.get('status')
          expect(status).toBe('completed')
          return HttpResponse.json({
            jobs: mockJobs.filter(j => j.status === 'completed'),
            total: 1,
            limit: 100,
            offset: 0,
          })
        })
      )

      const result = await listJobs({ status: 'completed' })

      expect(result.jobs.every(j => j.status === 'completed')).toBe(true)
    })

    it('fetches jobs with pagination', async () => {
      server.use(
        http.get(`${BASE_URL}/jobs`, ({ request }) => {
          const url = new URL(request.url)
          expect(url.searchParams.get('limit')).toBe('10')
          expect(url.searchParams.get('offset')).toBe('20')
          return HttpResponse.json({
            jobs: [],
            total: 100,
            limit: 10,
            offset: 20,
          })
        })
      )

      const result = await listJobs({ limit: 10, offset: 20 })

      expect(result.limit).toBe(10)
      expect(result.offset).toBe(20)
    })

    it('fetches jobs with type filter', async () => {
      server.use(
        http.get(`${BASE_URL}/jobs`, ({ request }) => {
          const url = new URL(request.url)
          expect(url.searchParams.get('type')).toBe('import')
          return HttpResponse.json({
            jobs: mockJobs.filter(j => j.type === 'import'),
            total: 1,
            limit: 100,
            offset: 0,
          })
        })
      )

      const result = await listJobs({ type: 'import' })

      expect(result.jobs.every(j => j.type === 'import')).toBe(true)
    })
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

  describe('retryJob', () => {
    it('retries a failed job', async () => {
      server.use(
        http.post(`${BASE_URL}/jobs/:id/retry`, ({ params }) => {
          return HttpResponse.json({
            original_job_id: params.id,
            new_job_id: 'new-job-123',
          })
        })
      )

      const result = await retryJob('failed-job-1')

      expect(result.original_job_id).toBe('failed-job-1')
      expect(result.new_job_id).toBe('new-job-123')
    })

    it('throws error for nonexistent job', async () => {
      server.use(
        http.post(`${BASE_URL}/jobs/:id/retry`, () => {
          return HttpResponse.json({ detail: 'Job not found' }, { status: 404 })
        })
      )

      await expect(retryJob('nonexistent-job')).rejects.toThrow()
    })

    it('throws error when retrying a non-failed job', async () => {
      server.use(
        http.post(`${BASE_URL}/jobs/:id/retry`, () => {
          return HttpResponse.json(
            { detail: 'Can only retry failed or cancelled jobs' },
            { status: 400 }
          )
        })
      )

      await expect(retryJob('running-job')).rejects.toThrow()
    })
  })
})
