import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import { listJobs, type JobListParams, type JobListResponse } from '../../../lib/api/endpoints/jobs'
import { jobsKeys } from '../../../lib/api/queryKeys'

type UseJobsQueryOptions = Omit<
  UseQueryOptions<JobListResponse, Error>,
  'queryKey' | 'queryFn'
>

/**
 * Hook to fetch jobs from the REST API with filtering and pagination.
 *
 * @param params - Filter and pagination parameters
 * @param options - Additional TanStack Query options
 */
export function useJobsQuery(params: JobListParams = {}, options?: UseJobsQueryOptions) {
  return useQuery({
    queryKey: jobsKeys.list(params),
    queryFn: () => listJobs(params),
    ...options,
  })
}

/**
 * Hook to fetch active jobs (pending, waiting, running).
 * Polls every 5 seconds as a fallback when WebSocket isn't connected.
 */
export function useActiveJobs(options?: UseJobsQueryOptions) {
  return useJobsQuery(
    { status: 'pending,waiting,running', limit: 200 },
    {
      refetchInterval: 5000, // Poll as fallback
      staleTime: 2000,
      ...options,
    }
  )
}

/**
 * Hook to fetch completed jobs with pagination.
 */
export function useCompletedJobs(
  { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {},
  options?: UseJobsQueryOptions
) {
  return useJobsQuery(
    { status: 'completed', limit, offset },
    {
      staleTime: 30000, // 30s - completed jobs don't change often
      ...options,
    }
  )
}

/**
 * Hook to fetch failed jobs with pagination.
 */
export function useFailedJobs(
  { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {},
  options?: UseJobsQueryOptions
) {
  return useJobsQuery(
    { status: 'failed,cancelled,timeout', limit, offset },
    {
      staleTime: 30000, // 30s - failed jobs don't change often
      ...options,
    }
  )
}

/**
 * Hook to fetch job history (completed + failed/cancelled/timeout) with pagination.
 */
export function useHistoryJobs(
  { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {},
  options?: UseJobsQueryOptions
) {
  return useJobsQuery(
    { status: 'completed,failed,cancelled,timeout', limit, offset },
    {
      staleTime: 30000,
      ...options,
    }
  )
}
