import { apiJson } from '../../../api/client'
import type { GetJobResponse } from '../types'

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
