import { useState, useMemo, useCallback } from 'react'
import { toast } from 'sonner'
import CompactJobCard from '../components/CompactJobCard'
import { useFailedJobs } from '../hooks/useJobsQuery'
import { retryJob, type JobItem } from '../../../lib/api/endpoints/jobs'
import type { JobState } from '../../../lib/ws/useJobEvents'
import './HistoryTab.css'

// Adapter: Convert REST JobItem to JobState format used by components
function toJobState(job: JobItem): JobState {
  return {
    job_id: job.id,
    job_type: job.type,
    status: job.status as JobState['status'],
    progress: job.progress,
    current_step: job.current_step,
    processed_items: job.processed_items,
    total_items: job.total_items,
    created_at: job.created_at,
    started_at: job.started_at,
    completed_at: job.completed_at,
    metadata: {
      ...job.metadata,
      video_id: job.video_id,
      video_title: job.video_title,
      video_artist: job.video_artist,
    },
    error: job.error ?? undefined,
    result: job.result ?? undefined,
  }
}

export function FailedJobsTab() {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [offset, setOffset] = useState(0)
  const limit = 50

  // Fetch failed jobs from REST API
  const { data, isLoading, refetch } = useFailedJobs({ limit, offset })

  const failedJobs = useMemo(() => {
    if (!data?.jobs) return []
    // Already sorted by backend, just convert
    return data.jobs.map(toJobState)
  }, [data])

  const totalJobs = data?.total ?? 0
  const hasMore = offset + limit < totalJobs
  const hasPrev = offset > 0

  const allSelected = failedJobs.length > 0 && selectedIds.size === failedJobs.length
  const someSelected = selectedIds.size > 0

  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(failedJobs.map(j => j.job_id)))
    }
  }

  const handleSelect = (jobId: string, selected: boolean) => {
    const newSelected = new Set(selectedIds)
    if (selected) {
      newSelected.add(jobId)
    } else {
      newSelected.delete(jobId)
    }
    setSelectedIds(newSelected)
  }

  const handleRetry = useCallback(async (job: JobState) => {
    try {
      const result = await retryJob(job.job_id)
      toast.success(`Job resubmitted: ${result.new_job_id}`)
      refetch() // Refresh the list
    } catch (error) {
      console.error('Failed to retry job:', error)
      toast.error('Failed to retry job')
    }
  }, [refetch])

  const handleRetrySelected = async () => {
    const selectedJobs = failedJobs.filter(j => selectedIds.has(j.job_id))
    let successCount = 0
    for (const job of selectedJobs) {
      try {
        await retryJob(job.job_id)
        successCount++
      } catch (error) {
        console.error(`Failed to retry job ${job.job_id}:`, error)
      }
    }
    if (successCount > 0) {
      toast.success(`${successCount} job(s) resubmitted`)
      refetch()
    }
    setSelectedIds(new Set())
  }

  const handleClear = useCallback((_jobId: string) => {
    // For now, just show a toast - clearing is client-side only
    toast.info('Job cleared from view')
  }, [])

  const handleClearSelected = () => {
    toast.info(`${selectedIds.size} job(s) cleared from view`)
    setSelectedIds(new Set())
  }

  if (isLoading && failedJobs.length === 0) {
    return (
      <div className="historyTab">
        <div className="emptyState">
          <div className="emptyIcon">⏳</div>
          <div className="emptyMessage">Loading...</div>
        </div>
      </div>
    )
  }

  if (failedJobs.length === 0) {
    return (
      <div className="historyTab">
        <div className="emptyState">
          <div className="emptyIcon">✓</div>
          <div className="emptyMessage">No failed jobs</div>
          <p className="emptySubtext">All jobs have completed successfully</p>
        </div>
      </div>
    )
  }

  return (
    <div className="historyTab">
      <div className="historyHeader">
        <label className="selectAllLabel">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={handleSelectAll}
          />
          Select all ({failedJobs.length})
        </label>
        <div className="batchActions">
          <button
            className="batchActionBtn"
            disabled={!someSelected}
            onClick={handleRetrySelected}
            title="Retry selected jobs"
          >
            ↻ Retry ({selectedIds.size})
          </button>
          <button
            className="batchActionBtn batchActionBtnDanger"
            disabled={!someSelected}
            onClick={handleClearSelected}
            title="Clear selected jobs from history"
          >
            Clear ({selectedIds.size})
          </button>
        </div>
      </div>

      <div className="compactJobList">
        {failedJobs.map(job => (
          <CompactJobCard
            key={job.job_id}
            job={job}
            selected={selectedIds.has(job.job_id)}
            onSelect={handleSelect}
            onRetry={handleRetry}
            onClear={handleClear}
          />
        ))}
      </div>

      {/* Pagination */}
      {totalJobs > limit && (
        <div className="paginationControls">
          <button
            className="paginationBtn"
            disabled={!hasPrev}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            ← Previous
          </button>
          <span className="paginationInfo">
            {offset + 1}–{Math.min(offset + limit, totalJobs)} of {totalJobs}
          </span>
          <button
            className="paginationBtn"
            disabled={!hasMore}
            onClick={() => setOffset(offset + limit)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
