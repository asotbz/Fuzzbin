import { useMemo, useState, useCallback } from 'react'
import { toast } from 'sonner'
import CompactJobCard from '../components/CompactJobCard'
import { useCompletedJobs } from '../hooks/useJobsQuery'
import type { JobItem } from '../../../lib/api/endpoints/jobs'
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

export default function CompletedJobsTab() {
  const [selectedJobs, setSelectedJobs] = useState<Set<string>>(new Set())
  const [offset, setOffset] = useState(0)
  const limit = 50

  // Fetch completed jobs from REST API
  const { data, isLoading } = useCompletedJobs({ limit, offset })

  const completedJobs = useMemo(() => {
    if (!data?.jobs) return []
    // Already sorted by backend, just convert
    return data.jobs.map(toJobState)
  }, [data])

  const totalJobs = data?.total ?? 0
  const hasMore = offset + limit < totalJobs
  const hasPrev = offset > 0

  const handleSelect = useCallback((jobId: string, selected: boolean) => {
    setSelectedJobs(prev => {
      const next = new Set(prev)
      if (selected) {
        next.add(jobId)
      } else {
        next.delete(jobId)
      }
      return next
    })
  }, [])

  const handleSelectAll = useCallback((selected: boolean) => {
    if (selected) {
      setSelectedJobs(new Set(completedJobs.map(j => j.job_id)))
    } else {
      setSelectedJobs(new Set())
    }
  }, [completedJobs])

  const handleClearJob = useCallback((_jobId: string) => {
    // For now, just show a toast - clearing is client-side only
    toast.info('Job cleared from view')
  }, [])

  const handleClearSelected = useCallback(() => {
    if (selectedJobs.size === 0) return
    toast.info(`${selectedJobs.size} job(s) cleared from view`)
    setSelectedJobs(new Set())
  }, [selectedJobs])

  const allSelected = completedJobs.length > 0 && selectedJobs.size === completedJobs.length

  if (isLoading && completedJobs.length === 0) {
    return (
      <div className="historyTab">
        <div className="emptyState">
          <div className="emptyIcon">⏳</div>
          <div className="emptyMessage">Loading...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="historyTab">
      {completedJobs.length === 0 ? (
        <div className="emptyState">
          <div className="emptyIcon">✓</div>
          <div className="emptyMessage">No completed jobs</div>
          <p className="emptySubtext">Completed jobs will appear here for 30 days</p>
        </div>
      ) : (
        <>
          <div className="historyHeader">
            <label className="selectAllLabel">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={(e) => handleSelectAll(e.target.checked)}
              />
              <span>Select all ({completedJobs.length})</span>
            </label>
            <div className="batchActions">
              <button
                className="batchActionBtn"
                type="button"
                onClick={handleClearSelected}
                disabled={selectedJobs.size === 0}
              >
                Clear Selected ({selectedJobs.size})
              </button>
            </div>
          </div>

          <div className="compactJobList">
            {completedJobs.map(job => (
              <CompactJobCard
                key={job.job_id}
                job={job}
                onClear={handleClearJob}
                selected={selectedJobs.has(job.job_id)}
                onSelect={handleSelect}
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
        </>
      )}
    </div>
  )
}
