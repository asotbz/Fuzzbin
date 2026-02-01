import { useState } from 'react'
import type { JobData } from '../hooks/useActivityWebSocket'
import JobStatusBadge from './JobStatusBadge'
import JobProgressBar from './JobProgressBar'
import './JobCard.css'

interface JobCardProps {
  job: JobData
  onCancel?: (jobId: string) => void
  onRetry?: (job: JobData) => void
  onClear?: (jobId: string) => void
}

const JOB_TYPE_LABELS: Record<string, string> = {
  'download_youtube': 'YouTube Download',
  'import_spotify_batch': 'Spotify Batch Import',
  'import_nfo': 'NFO Import',
  'import_add_single': 'Single Video Import',
  'metadata_enrich': 'Metadata Enrichment',
  'file_organize': 'File Organization',
  'library_scan': 'Library Scan',
  'import_organize': 'Organize Import',
  'import_nfo_generate': 'Generate NFO',
  'file_duplicate_resolve': 'Resolve Duplicates',
  'metadata_refresh': 'Metadata Refresh',
  'backup': 'System Backup',
  'video_post_process': 'Video Processing',
}

function formatJobType(jobType: string): string {
  return JOB_TYPE_LABELS[jobType] || jobType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

function formatDuration(startedAt: string | null, completedAt?: string | null): string | null {
  if (!startedAt || !completedAt) return null

  const start = new Date(startedAt)
  const end = new Date(completedAt)
  const diffMs = end.getTime() - start.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)

  if (diffSecs < 60) return `${diffSecs}s`
  const secs = diffSecs % 60
  return `${diffMins}m ${secs}s`
}

function getMetadataString(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key]
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function getMetadataNumber(metadata: Record<string, unknown>, key: string): number | null {
  const value = metadata[key]
  if (typeof value === 'number') return value
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export default function JobCard({ job, onCancel, onRetry, onClear }: JobCardProps) {
  const [showDetails, setShowDetails] = useState(false)

  const isRunning = ['pending', 'waiting', 'running'].includes(job.status)
  const isCompleted = job.status === 'completed'
  const isFailed = ['failed', 'cancelled', 'timeout'].includes(job.status)

  const cardClass = `jobCard ${isRunning ? 'jobCardRunning' : ''} ${isCompleted ? 'jobCardCompleted' : ''} ${isFailed ? 'jobCardFailed' : ''}`

  const startedTime = job.started_at ? formatTimestamp(job.started_at) : formatTimestamp(job.created_at)
  const duration = formatDuration(job.started_at, job.completed_at)
  const videoTitle = getMetadataString(job.metadata, 'video_title') ?? getMetadataString(job.metadata, 'title')
  const videoArtist = getMetadataString(job.metadata, 'video_artist') ?? getMetadataString(job.metadata, 'artist')
  const videoId = getMetadataNumber(job.metadata, 'video_id')
  const videoLabelParts = [videoArtist, videoTitle].filter(Boolean)
  const videoLabel = videoLabelParts.length > 0 ? videoLabelParts.join(' - ') : null
  const jobIdLabel = videoLabel
    ? `${videoLabel}${videoId ? ` (${videoId})` : ''}`
    : videoId
      ? `Video ${videoId}`
      : job.job_id

  return (
    <div className={cardClass}>
      <div className="jobCardHeader">
        <div className="jobInfo">
          <div className="jobType">{formatJobType(job.job_type)}</div>
          <div className="jobId">{jobIdLabel}</div>
        </div>
        <JobStatusBadge status={job.status} />
      </div>

      <div className="jobCurrentStep">{job.current_step}</div>

      <JobProgressBar job={job} />

      <div className="jobMeta">
        <span className="jobTimestamp">
          {job.processed_items}/{job.total_items} tasks
          {' • '}
          {isCompleted && duration ? `Completed ${startedTime} • Duration: ${duration}` :
           isFailed && duration ? `Failed ${startedTime} • Duration: ${duration}` :
           isRunning && job.started_at ? `Started ${startedTime}` :
           `Queued ${startedTime}`}
        </span>
        <div className="jobActions">
          {isRunning && onCancel && (
            <button
              className="actionBtn actionBtnDanger"
              type="button"
              onClick={() => onCancel(job.job_id)}
              aria-label="Cancel job"
            >
              Cancel
            </button>
          )}
          {isFailed && onRetry && (
            <button
              className="actionBtn"
              type="button"
              onClick={() => onRetry(job)}
              aria-label="Retry job"
            >
              Retry
            </button>
          )}
          <button
            className="actionBtn"
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            aria-label="Toggle job details"
            aria-expanded={showDetails}
          >
            {showDetails ? 'Hide' : 'Details'}
          </button>
          {!isRunning && onClear && (
            <button
              className="actionBtn"
              type="button"
              onClick={() => onClear(job.job_id)}
              aria-label="Clear job"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {showDetails && (
        <div className="jobDetails">
          {job.error && (
            <div className="jobDetailsSection">
              <div className="jobDetailsLabel">Error:</div>
              <div className="jobDetailsValue jobDetailsError">{job.error}</div>
            </div>
          )}
          {job.result && Object.keys(job.result).length > 0 && (
            <div className="jobDetailsSection">
              <div className="jobDetailsLabel">Result:</div>
              <pre className="jobDetailsValue jobDetailsCode">{JSON.stringify(job.result, null, 2)}</pre>
            </div>
          )}
          {job.metadata && Object.keys(job.metadata).length > 0 && (
            <div className="jobDetailsSection">
              <div className="jobDetailsLabel">Metadata:</div>
              <pre className="jobDetailsValue jobDetailsCode">{JSON.stringify(job.metadata, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
