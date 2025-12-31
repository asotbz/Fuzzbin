import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const mockJobs = [
  {
    id: 'job-1',
    type: 'import',
    status: 'completed',
    progress: 100,
    message: 'Import completed successfully',
    created_at: '2024-01-01T10:00:00Z',
    started_at: '2024-01-01T10:00:01Z',
    completed_at: '2024-01-01T10:01:00Z',
    result: {
      video_id: 1,
      title: 'Imported Video',
    },
  },
  {
    id: 'job-2',
    type: 'import',
    status: 'running',
    progress: 50,
    message: 'Downloading video...',
    created_at: '2024-01-01T11:00:00Z',
    started_at: '2024-01-01T11:00:01Z',
    completed_at: null,
    result: null,
  },
  {
    id: 'job-3',
    type: 'scan',
    status: 'queued',
    progress: 0,
    message: 'Waiting to start...',
    created_at: '2024-01-01T12:00:00Z',
    started_at: null,
    completed_at: null,
    result: null,
  },
]

export const jobsHandlers = [
  // List jobs
  http.get(`${BASE_URL}/jobs`, ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status')

    let filtered = [...mockJobs]

    if (status) {
      filtered = filtered.filter(j => j.status === status)
    }

    return HttpResponse.json({
      items: filtered,
      total: filtered.length,
    })
  }),

  // Get single job
  http.get(`${BASE_URL}/jobs/:id`, ({ params }) => {
    const job = mockJobs.find(j => j.id === params.id)

    if (!job) {
      return HttpResponse.json(
        { detail: 'Job not found' },
        { status: 404 }
      )
    }

    return HttpResponse.json(job)
  }),

  // Cancel job
  http.post(`${BASE_URL}/jobs/:id/cancel`, ({ params }) => {
    const job = mockJobs.find(j => j.id === params.id)

    if (!job) {
      return HttpResponse.json(
        { detail: 'Job not found' },
        { status: 404 }
      )
    }

    if (job.status === 'completed' || job.status === 'failed') {
      return HttpResponse.json(
        { detail: 'Cannot cancel completed or failed job' },
        { status: 400 }
      )
    }

    return HttpResponse.json({
      ...job,
      status: 'cancelled',
      message: 'Job cancelled by user',
    })
  }),
]
