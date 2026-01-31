import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { server } from '../../../../mocks/server'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS } from '../../../../mocks/handlers'
import { useJobsQuery, useActiveJobs, useCompletedJobs, useFailedJobs } from '../useJobsQuery'

const BASE_URL = 'http://localhost:8000'

const mockJobsResponse = {
  jobs: [
    {
      id: 'job-1',
      type: 'scan',
      status: 'completed',
      priority: 5,
      progress: 100,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:01:00Z',
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }
}

describe('useJobsQuery', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('fetches jobs with default parameters', async () => {
    server.use(
      http.get(`${BASE_URL}/jobs`, () => {
        return HttpResponse.json(mockJobsResponse)
      })
    )

    const { result } = renderHook(() => useJobsQuery(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data).toBeDefined()
    expect(result.current.data?.jobs).toHaveLength(1)
    expect(result.current.data?.total).toBe(1)
  })

  it('fetches jobs with custom parameters', async () => {
    server.use(
      http.get(`${BASE_URL}/jobs`, () => {
        return HttpResponse.json(mockJobsResponse)
      })
    )

    const { result } = renderHook(
      () => useJobsQuery({ status: 'completed', limit: 10, offset: 5 }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.jobs[0].status).toBe('completed')
  })
})

describe('useActiveJobs', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('fetches active jobs with correct status filter', async () => {
    server.use(
      http.get(`${BASE_URL}/jobs`, () => {
        return HttpResponse.json({
          jobs: [{ ...mockJobsResponse.jobs[0], status: 'running' }],
          total: 1,
          limit: 200,
          offset: 0,
        })
      })
    )

    const { result } = renderHook(() => useActiveJobs(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.jobs[0].status).toBe('running')
  })
})

describe('useCompletedJobs', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('fetches completed jobs', async () => {
    server.use(
      http.get(`${BASE_URL}/jobs`, () => {
        return HttpResponse.json(mockJobsResponse)
      })
    )

    const { result } = renderHook(() => useCompletedJobs(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.jobs[0].status).toBe('completed')
  })

  it('supports pagination parameters', async () => {
    server.use(
      http.get(`${BASE_URL}/jobs`, () => {
        return HttpResponse.json({ ...mockJobsResponse, limit: 25, offset: 10 })
      })
    )

    const { result } = renderHook(
      () => useCompletedJobs({ limit: 25, offset: 10 }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBeDefined()
  })
})

describe('useFailedJobs', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  it('fetches failed jobs', async () => {
    server.use(
      http.get(`${BASE_URL}/jobs`, () => {
        return HttpResponse.json({
          jobs: [{ ...mockJobsResponse.jobs[0], status: 'failed' }],
          total: 1,
          limit: 50,
          offset: 0,
        })
      })
    )

    const { result } = renderHook(() => useFailedJobs(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.jobs[0].status).toBe('failed')
  })

  it('supports pagination parameters', async () => {
    server.use(
      http.get(`${BASE_URL}/jobs`, () => {
        return HttpResponse.json({ ...mockJobsResponse, status: 'failed', limit: 25, offset: 10 })
      })
    )

    const { result } = renderHook(
      () => useFailedJobs({ limit: 25, offset: 10 }),
      { wrapper: createWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBeDefined()
  })
})
