import { useMemo, useState } from 'react'
import type { JobData } from '../hooks/useActivityWebSocket'
import JobStatusBadge from './JobStatusBadge'
import CompactJobCard from './CompactJobCard'
import './HistoryJobGroup.css'

export interface HistoryJobGroupData {
  key: string
  videoId?: number
  videoTitle?: string
  videoArtist?: string
  jobs: JobData[]
  lastUpdatedAt: string | null
}

interface HistoryJobGroupProps {
  group: HistoryJobGroupData
  onRetryJob?: (job: JobData) => void
}

function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return 'unknown'
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

export default function HistoryJobGroup({ group, onRetryJob }: HistoryJobGroupProps) {
  const [expanded, setExpanded] = useState(false)

  const failedStatuses = useMemo(() => new Set(['failed', 'cancelled', 'timeout']), [])
  const failedCount = group.jobs.filter(job => failedStatuses.has(job.status)).length
  const completedCount = group.jobs.filter(job => job.status === 'completed').length
  const totalCount = group.jobs.length
  const groupStatus = failedCount > 0 ? 'failed' : 'completed'

  const baseTitleParts = [group.videoArtist, group.videoTitle].filter(Boolean)
  const fallbackJobId = group.jobs[0]?.job_id
  const baseTitle = baseTitleParts.length > 0
    ? baseTitleParts.join(' - ')
    : group.videoId
      ? `Video ${group.videoId}`
      : fallbackJobId
        ? `Job ${fallbackJobId}`
        : 'Unlinked Job'
  const title = group.videoId && baseTitleParts.length > 0
    ? `${baseTitle} (${group.videoId})`
    : baseTitle

  const lastUpdatedLabel = formatTimestamp(group.lastUpdatedAt)

  return (
    <div className={`historyJobGroup historyJobGroup${groupStatus === 'failed' ? 'Failed' : 'Completed'}`}>
      <button
        type="button"
        className="historyJobGroupHeader"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        <div className="historyJobGroupInfo">
          <div className="historyJobGroupTitle" title={title}>
            {title}
          </div>
          <div className="historyJobGroupMeta">
            <span>{totalCount} job{totalCount === 1 ? '' : 's'}</span>
            {failedCount > 0 && <span>{failedCount} failed</span>}
            {completedCount > 0 && <span>{completedCount} completed</span>}
            <span>Updated {lastUpdatedLabel}</span>
          </div>
        </div>
        <div className="historyJobGroupBadge">
          <JobStatusBadge status={groupStatus} />
          <span className={`historyJobGroupArrow ${expanded ? 'historyJobGroupArrowExpanded' : ''}`}>
            ▼
          </span>
        </div>
      </button>

      {expanded && (
        <div className="historyJobGroupJobs">
          {group.jobs.map(job => (
            <CompactJobCard
              key={job.job_id}
              job={job}
              onRetry={onRetryJob}
            />
          ))}
        </div>
      )}
    </div>
  )
}
