import type { JobData } from '../hooks/useActivityWebSocket'
import JobStatusBadge from './JobStatusBadge'
import './CompactJobCard.css'

interface CompactJobCardProps {
  job: JobData
  onRetry?: (job: JobData) => void
  onClear?: (jobId: string) => void
  selected?: boolean
  onSelect?: (jobId: string, selected: boolean) => void
}

const JOB_TYPE_LABELS: Record<string, string> = {
  'download_youtube': 'Download',
  'import_spotify_batch': 'Spotify Import',
  'import_nfo': 'NFO Import',
  'import_add_single': 'Single Import',
  'metadata_enrich': 'Enrich',
  'file_organize': 'Organize',
  'library_scan': 'Library Scan',
  'import_organize': 'Organize',
  'import_nfo_generate': 'NFO Generate',
  'file_duplicate_resolve': 'Duplicates',
  'metadata_refresh': 'Refresh',
  'backup': 'Backup',
  'video_post_process': 'Processing',
  'trash_cleanup': 'Cleanup',
  'cleanup_job_history': 'Job Cleanup',
  'export_nfo': 'NFO Export',
}

function formatJobType(jobType: string): string {
  return JOB_TYPE_LABELS[jobType] || jobType.replace(/_/g, ' ')
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
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function formatDuration(startedAt: string | null, completedAt?: string | null): string | null {
  if (!startedAt || !completedAt) return null

  const start = new Date(startedAt)
  const end = new Date(completedAt)
  const diffMs = end.getTime() - start.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)

  if (diffSecs < 60) return `${diffSecs}s`
  return `${diffMins}m ${diffSecs % 60}s`
}

export default function CompactJobCard({
  job,
  onRetry,
  onClear,
  selected = false,
  onSelect,
}: CompactJobCardProps) {
  const isFailed = ['failed', 'cancelled', 'timeout'].includes(job.status)
  const isCompleted = job.status === 'completed'
  const duration = formatDuration(job.started_at, job.completed_at)
  const completedTime = job.completed_at ? formatTimestamp(job.completed_at) : null

  // Get video info from metadata if available
  const videoTitle = (job.metadata?.video_title || job.metadata?.title) as string | undefined
  const videoArtist = (job.metadata?.video_artist || job.metadata?.artist) as string | undefined

  return (
    <div className={`compactJobCard ${isFailed ? 'compactJobCardFailed' : ''} ${isCompleted ? 'compactJobCardCompleted' : ''}`}>
      {onSelect && (
        <input
          type="checkbox"
          className="compactJobCheckbox"
          checked={selected}
          onChange={(e) => onSelect(job.job_id, e.target.checked)}
          aria-label={`Select job ${job.job_id}`}
        />
      )}

      <div className="compactJobType">
        {formatJobType(job.job_type)}
      </div>

      <div className="compactJobInfo">
        {videoTitle ? (
          <span className="compactJobTitle" title={videoTitle}>
            {videoArtist ? `${videoArtist} - ${videoTitle}` : videoTitle}
          </span>
        ) : (
          <span className="compactJobStep" title={job.current_step}>
            {job.current_step}
          </span>
        )}
      </div>

      <div className="compactJobMeta">
        {duration && <span className="compactJobDuration">{duration}</span>}
        {completedTime && <span className="compactJobTime">{completedTime}</span>}
      </div>

      <JobStatusBadge status={job.status} />

      <div className="compactJobActions">
        {isFailed && onRetry && (
          <button
            className="compactActionBtn"
            type="button"
            onClick={() => onRetry(job)}
            aria-label="Retry job"
            title="Retry"
          >
            ↻
          </button>
        )}
        {onClear && (
          <button
            className="compactActionBtn compactActionBtnClear"
            type="button"
            onClick={() => onClear(job.job_id)}
            aria-label="Clear job"
            title="Clear"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}
