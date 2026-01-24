import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const mockJobs = [
  {
    id: 'job-1',
    type: 'import',
    status: 'completed',
    progress: 100,
    current_step: 'completed',
    total_items: 1,
    processed_items: 1,
    created_at: '2024-01-01T10:00:00Z',
    started_at: '2024-01-01T10:00:01Z',
    completed_at: '2024-01-01T10:01:00Z',
    result: {
      video_id: 1,
      title: 'Imported Video',
    },
    error: null,
    metadata: {},
  },
  {
    id: 'job-2',
    type: 'import',
    status: 'running',
    progress: 50,
    current_step: 'Downloading video...',
    total_items: 2,
    processed_items: 1,
    created_at: '2024-01-01T11:00:00Z',
    started_at: '2024-01-01T11:00:01Z',
    completed_at: null,
    result: null,
    error: null,
    metadata: {},
  },
  {
    id: 'job-3',
    type: 'library_scan',
    status: 'pending',
    progress: 0,
    current_step: 'Waiting to start...',
    total_items: 0,
    processed_items: 0,
    created_at: '2024-01-01T12:00:00Z',
    started_at: null,
    completed_at: null,
    result: null,
    error: null,
    metadata: {},
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
