import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useActivityWebSocket, type JobData } from '../useActivityWebSocket'

describe('useActivityWebSocket', () => {
  it('returns disconnected state when no token provided', () => {
    const { result } = renderHook(() => useActivityWebSocket(null))

    // Without a token, should be in disconnected/idle state
    expect(result.current.state).toBe('disconnected')
    // jobs is a Map
    expect(result.current.jobs.size).toBe(0)
    expect(result.current.lastError).toBeNull()
  })

  it('exports JobData type alias', () => {
    // Type check - should compile if JobData is properly exported
    const job: JobData = {
      job_id: '123',
      job_type: 'IMPORT_NFO',
      status: 'pending',
      priority: 5,
      created_at: '2024-01-01T00:00:00Z',
      current: 0,
      total: 100,
      message: 'Test job',
      result: undefined,
      error: undefined,
    }
    expect(job.job_id).toBe('123')
  })
})
