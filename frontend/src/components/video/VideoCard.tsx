import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import './video.css'
import type { Video } from '../../lib/api/types'
import { videosKeys } from '../../lib/api/queryKeys'
import type { JobStatus } from '../../lib/ws/useJobEvents'
import { getApiBaseUrl } from '../../api/client'
import { useVideoThumbnail } from '../../api/useVideoThumbnail'

function formatDuration(seconds: unknown): string {
  const sec = typeof seconds === 'number' && Number.isFinite(seconds) ? Math.max(0, Math.round(seconds)) : null
  if (sec === null) return '—'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

async function submitDownloadJob(videoId: number, youtubeId: string): Promise<{ job_id: string }> {
  // Submit download job directly via backend API
  const response = await fetch(`${getApiBaseUrl()}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      type: 'import_download',
      metadata: {
        video_id: videoId,
        youtube_id: youtubeId,
      },
    }),
  })
  
  if (!response.ok) {
    throw new Error(`Failed to submit download job: ${response.statusText}`)
  }
  
  return response.json()
}

// Inline SVG icons to avoid external dependency
function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function FileCheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="m9 15 2 2 4-4" />
    </svg>
  )
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  )
}

function AlertCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" x2="12" y1="8" y2="12" />
      <line x1="12" x2="12.01" y1="16" y2="16" />
    </svg>
  )
}

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

/** Get status icon for video status */
function getStatusIcon(status: string | null, hasActiveJob: boolean) {
  // If there's an active job, show spinner
  if (hasActiveJob) {
    return <SpinnerIcon className="videoCardStatusIcon videoCardStatusSpinner" />
  }

  // Show status-based icon
  switch (status) {
    case 'discovered':
      return <EyeIcon className="videoCardStatusIcon videoCardStatusDiscovered" />
    case 'imported':
    case 'metadata_enriched':
      return <FileCheckIcon className="videoCardStatusIcon videoCardStatusImported" />
    case 'downloaded':
    case 'organized':
      return <DownloadIcon className="videoCardStatusIcon videoCardStatusDownloaded" />
    case 'download_failed':
      return <AlertCircleIcon className="videoCardStatusIcon videoCardStatusFailed" />
    default:
      return null
  }
}

export interface VideoCardJobStatus {
  hasActiveJob: boolean
  jobStatus?: JobStatus
  jobProgress?: number
}

interface VideoCardProps {
  video: Video
  selectable?: boolean
  selected?: boolean
  onToggleSelection?: (id: number) => void
  onClick?: () => void
  /** Callback when play button is clicked */
  onPlay?: (video: Video) => void
  /** Job status info from WebSocket subscription */
  jobStatus?: VideoCardJobStatus
  /** Timestamp for thumbnail cache-busting (from WebSocket events) */
  thumbnailTimestamp?: number
}

export default function VideoCard({
  video,
  selectable = false,
  selected = false,
  onToggleSelection,
  onClick,
  onPlay,
  jobStatus,
  thumbnailTimestamp,
}: VideoCardProps) {
  const queryClient = useQueryClient()
  const [showRetrySuccess, setShowRetrySuccess] = useState(false)

  const anyVideo = video as Record<string, unknown>
  const videoId = typeof anyVideo.id === 'number' ? anyVideo.id : null
  const title = (typeof anyVideo.title === 'string' && anyVideo.title.trim().length > 0 ? anyVideo.title : 'Untitled') as string
  const artist = (typeof anyVideo.artist === 'string' && anyVideo.artist.trim().length > 0 ? anyVideo.artist : '') as string
  const album = typeof anyVideo.album === 'string' && anyVideo.album.trim().length > 0 ? anyVideo.album : null
  const year = typeof anyVideo.year === 'number' ? anyVideo.year : null
  const studio = typeof anyVideo.studio === 'string' && anyVideo.studio.trim().length > 0 ? anyVideo.studio : null
  const director = typeof anyVideo.director === 'string' && anyVideo.director.trim().length > 0 ? anyVideo.director : null
  const duration = formatDuration(anyVideo.duration)
  const status = typeof anyVideo.status === 'string' ? anyVideo.status : null
  const youtubeId = typeof anyVideo.youtube_id === 'string' ? anyVideo.youtube_id : null

  // Fetch thumbnail with authentication and cache-busting
  const { thumbnailUrl } = useVideoThumbnail(videoId, { cacheBustTimestamp: thumbnailTimestamp })

  // Check if there's an active job for this video
  const hasActiveJob = jobStatus?.hasActiveJob ?? false

  // Show retry button if: status is download_failed OR (status is discovered AND youtube_id exists)
  const canRetryDownload = videoId && youtubeId && (status === 'download_failed' || status === 'discovered') && !hasActiveJob

  const retryMutation = useMutation({
    mutationFn: () => {
      if (!videoId || !youtubeId) throw new Error('Missing video ID or YouTube ID')
      return submitDownloadJob(videoId, youtubeId)
    },
    onSuccess: () => {
      setShowRetrySuccess(true)
      setTimeout(() => setShowRetrySuccess(false), 3000)
      // Invalidate queries to refresh the video list
      queryClient.invalidateQueries({ queryKey: videosKeys.all })
    },
  })

  const handleCardClick = () => {
    if (onClick) onClick()
  }

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation()
  }

  const handleCheckboxChange = () => {
    if (onToggleSelection && videoId) {
      onToggleSelection(videoId)
    }
  }

  // Build album/year string
  const albumYear = album && year
    ? `${album} (${year})`
    : album
      ? album
      : year
        ? `(${year})`
        : null

  return (
    <div
      className={`videoCard ${selectable && selected ? 'videoCardSelected' : ''}`}
      onClick={handleCardClick}
      role="article"
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      <div
        className="videoCardThumb"
        style={{
          backgroundImage: thumbnailUrl ? `url(${thumbnailUrl})` : undefined
        }}
        aria-hidden="true"
      >
        {/* Center: Play button overlay (shown on hover) */}
        {onPlay && (
          <button
            className="videoCardPlayOverlay"
            onClick={(e) => {
              e.stopPropagation()
              onPlay(video)
            }}
            aria-label={`Play ${title}`}
            title="Play video"
          >
            <PlayIcon className="videoCardPlayIcon" />
          </button>
        )}

        {/* Top-left: Status indicator or spinner */}
        <div className="videoCardStatusContainer">
          {getStatusIcon(status, hasActiveJob)}
          {selectable && (
            <div className="videoCardCheckboxWrapper" onClick={handleCheckboxClick}>
              <input
                type="checkbox"
                className="videoCardCheckbox"
                checked={selected}
                onChange={handleCheckboxChange}
                aria-label={`Select ${title}`}
              />
            </div>
          )}
        </div>

        {/* Bottom-right: Duration */}
        <div className="videoCardDuration">{duration}</div>

        {/* Bottom-left: MTV-style metadata overlay */}
        <div className="videoCardOverlay">
          {artist && <div className="videoCardOverlayArtist">{artist}</div>}
          <div className="videoCardOverlayTitle">{title}</div>
          {albumYear && <div className="videoCardOverlayAlbum">{albumYear}</div>}
          {studio && <div className="videoCardOverlayLabel">{studio}</div>}
          {director && <div className="videoCardOverlayDirector">Dir: {director}</div>}
        </div>

        {/* Download/retry button */}
        {canRetryDownload ? (
          <button
            className="videoCardRetryButton"
            onClick={(e) => {
              e.stopPropagation()
              void retryMutation.mutateAsync()
            }}
            disabled={retryMutation.isPending || showRetrySuccess}
            title={status === 'download_failed' ? 'Retry failed download' : 'Download video'}
            aria-label={status === 'download_failed' ? 'Retry download' : 'Download video'}
          >
            {retryMutation.isPending ? '⏳' : showRetrySuccess ? '✓' : '↓'}
          </button>
        ) : null}
      </div>
    </div>
  )
}
