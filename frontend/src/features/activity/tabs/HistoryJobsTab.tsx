import { useMemo, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { retryJob, type JobItem } from '../../../lib/api/endpoints/jobs'
import type { JobState } from '../../../lib/ws/useJobEvents'
import { useHistoryJobs } from '../hooks/useJobsQuery'
import HistoryJobGroup, { type HistoryJobGroupData } from '../components/HistoryJobGroup'
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

function getJobTimestamp(job: JobState): number {
  const ts = job.completed_at ?? job.started_at ?? job.created_at
  const date = ts ? new Date(ts) : null
  return date ? date.getTime() : 0
}

export default function HistoryJobsTab() {
  const [offset, setOffset] = useState(0)
  const limit = 50

  const { data, isLoading, refetch } = useHistoryJobs({ limit, offset })

  const historyJobs = useMemo(() => {
    if (!data?.jobs) return []
    return data.jobs.map(toJobState)
  }, [data])

  const groupedJobs = useMemo<HistoryJobGroupData[]>(() => {
    const groups = new Map<string, HistoryJobGroupData>()

    historyJobs.forEach((job) => {
      const videoId = job.metadata?.video_id as number | undefined
      const groupKey = typeof videoId === 'number' ? `video-${videoId}` : `job-${job.job_id}`
      const existing = groups.get(groupKey)

      const videoTitle = (job.metadata?.video_title || job.metadata?.title) as string | undefined
      const videoArtist = (job.metadata?.video_artist || job.metadata?.artist) as string | undefined
      const jobTimestamp = getJobTimestamp(job)

      if (!existing) {
        groups.set(groupKey, {
          key: groupKey,
          videoId: typeof videoId === 'number' ? videoId : undefined,
          videoTitle: videoTitle,
          videoArtist: videoArtist,
          jobs: [job],
          lastUpdatedAt: job.completed_at ?? job.created_at ?? null,
        })
        return
      }

      existing.jobs.push(job)
      if (!existing.videoTitle && videoTitle) existing.videoTitle = videoTitle
      if (!existing.videoArtist && videoArtist) existing.videoArtist = videoArtist

      const existingTimestamp = existing.lastUpdatedAt ? new Date(existing.lastUpdatedAt).getTime() : 0
      if (jobTimestamp >= existingTimestamp) {
        existing.lastUpdatedAt = job.completed_at ?? job.created_at ?? existing.lastUpdatedAt
      }
    })

    const grouped = Array.from(groups.values())
    grouped.forEach((group) => {
      group.jobs.sort((a, b) => getJobTimestamp(b) - getJobTimestamp(a))
    })

    return grouped.sort((a, b) => {
      const aTime = a.lastUpdatedAt ? new Date(a.lastUpdatedAt).getTime() : 0
      const bTime = b.lastUpdatedAt ? new Date(b.lastUpdatedAt).getTime() : 0
      return bTime - aTime
    })
  }, [historyJobs])

  const totalJobs = data?.total ?? 0
  const hasMore = offset + limit < totalJobs
  const hasPrev = offset > 0

  const handleRetry = useCallback(async (job: JobState) => {
    try {
      const result = await retryJob(job.job_id)
      toast.success(`Job resubmitted: ${result.new_job_id}`)
      refetch()
    } catch (error) {
      console.error('Failed to retry job:', error)
      toast.error('Failed to retry job')
    }
  }, [refetch])

  if (isLoading && groupedJobs.length === 0) {
    return (
      <div className="historyTab">
        <div className="emptyState">
          <div className="emptyIcon">⏳</div>
          <div className="emptyMessage">Loading...</div>
        </div>
      </div>
    )
  }

  if (groupedJobs.length === 0) {
    return (
      <div className="historyTab">
        <div className="emptyState">
          <div className="emptyIcon">✓</div>
          <div className="emptyMessage">No job history yet</div>
          <p className="emptySubtext">Completed and failed jobs will appear here</p>
        </div>
      </div>
    )
  }

  return (
    <div className="historyTab">
      <div className="historyGroupList">
        {groupedJobs.map(group => (
          <HistoryJobGroup key={group.key} group={group} onRetryJob={handleRetry} />
        ))}
      </div>

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
