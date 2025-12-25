import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import './video.css'
import type { Video } from '../../lib/api/types'
import { videosKeys } from '../../lib/api/queryKeys'

function formatDuration(seconds: unknown): string {
  const sec = typeof seconds === 'number' && Number.isFinite(seconds) ? Math.max(0, Math.round(seconds)) : null
  if (sec === null) return '—'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function getTagLabel(tag: unknown): string | null {
  if (!tag || typeof tag !== 'object') return null
  const anyTag = tag as Record<string, unknown>
  const label = anyTag.name ?? anyTag.tag_name ?? anyTag.value
  return typeof label === 'string' && label.trim().length > 0 ? label.trim() : null
}

async function submitDownloadJob(videoId: number, youtubeId: string): Promise<{ job_id: string }> {
  // Submit download job directly via backend API
  const response = await fetch('/api/jobs', {
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

export default function VideoCard({ video }: { video: Video }) {
  const queryClient = useQueryClient()
  const [showRetrySuccess, setShowRetrySuccess] = useState(false)
  
  const anyVideo = video as Record<string, unknown>
  const videoId = typeof anyVideo.id === 'number' ? anyVideo.id : null
  const title = (typeof anyVideo.title === 'string' && anyVideo.title.trim().length > 0 ? anyVideo.title : 'Untitled') as string
  const artist = (typeof anyVideo.artist === 'string' && anyVideo.artist.trim().length > 0 ? anyVideo.artist : '—') as string
  const year = typeof anyVideo.year === 'number' ? String(anyVideo.year) : null
  const duration = formatDuration(anyVideo.duration)
  const status = typeof anyVideo.status === 'string' ? anyVideo.status : null
  const youtubeId = typeof anyVideo.youtube_id === 'string' ? anyVideo.youtube_id : null

  const tagsRaw = Array.isArray(anyVideo.tags) ? anyVideo.tags : []
  const tags = tagsRaw.map(getTagLabel).filter((t): t is string => Boolean(t)).slice(0, 3)

  // Show retry button if: status is download_failed OR (status is discovered AND youtube_id exists)
  const canRetryDownload = videoId && youtubeId && (status === 'download_failed' || status === 'discovered')

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

  return (
    <div className="videoCard" role="article">
      <div className="videoCardThumb" aria-hidden="true">
        <div className="videoCardDuration">{duration}</div>
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
      <div className="videoCardBody">
        <div className="videoCardTitle" title={title}>
          {title}
        </div>
        <div className="videoCardArtist">
          {artist}
          {year ? <span className="videoCardYear">· {year}</span> : null}
        </div>

        <div className="videoCardMeta">
          {status ? <span className="badge badgeCyan">{status}</span> : null}
          {retryMutation.isError ? (
            <span className="badge badgeError" title={retryMutation.error?.message}>
              Download failed
            </span>
          ) : null}
          {tags.length > 0 ? (
            <div className="videoCardTags">
              {tags.map((t) => (
                <span key={t} className="badge badgeCyan badgeTilt">
                  {t}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
