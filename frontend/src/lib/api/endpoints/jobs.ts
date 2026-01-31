import { apiJson } from '../../../api/client'
import type { GetJobResponse } from '../types'

export interface JobListParams {
  /** Comma-separated status filter (e.g., 'pending,running' or 'completed,failed') */
  status?: string
  /** Comma-separated job type filter */
  type?: string
  /** Maximum jobs to return (default: 100) */
  limit?: number
  /** Offset for pagination */
  offset?: number
}

export interface JobItem {
  id: string
  type: string
  status: string
  progress: number
  current_step: string
  total_items: number
  processed_items: number
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  metadata: Record<string, unknown>
  video_id: number | null
  video_title: string | null
  video_artist: string | null
}

export interface JobListResponse {
  jobs: JobItem[]
  total: number
  limit: number | null
  offset: number | null
}

export async function listJobs(params: JobListParams = {}): Promise<JobListResponse> {
  const searchParams = new URLSearchParams()
  if (params.status) searchParams.set('status', params.status)
  if (params.type) searchParams.set('type', params.type)
  if (params.limit !== undefined) searchParams.set('limit', String(params.limit))
  if (params.offset !== undefined) searchParams.set('offset', String(params.offset))

  const query = searchParams.toString()
  const path = query ? `/jobs?${query}` : '/jobs'

  return apiJson<JobListResponse>({ path })
}

export async function getJob(jobId: string): Promise<GetJobResponse> {
  return apiJson<GetJobResponse>({
    path: `/jobs/${encodeURIComponent(jobId)}`,
  })
}

export async function cancelJob(jobId: string): Promise<void> {
  await apiJson<void>({
    method: 'DELETE',
    path: `/jobs/${encodeURIComponent(jobId)}`,
  })
}

export async function retryJob(jobId: string): Promise<{ original_job_id: string; new_job_id: string }> {
  return apiJson<{ original_job_id: string; new_job_id: string }>({
    method: 'POST',
    path: `/jobs/${encodeURIComponent(jobId)}/retry`,
  })
}
