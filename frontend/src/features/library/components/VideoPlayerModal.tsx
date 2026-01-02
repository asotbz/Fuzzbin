import { useEffect, useRef, useCallback } from 'react'
import type { Video } from '../../../lib/api/types'
import { useAuthTokens } from '../../../auth/useAuthTokens'
import { getApiBaseUrl } from '../../../api/client'
import './VideoPlayerModal.css'

interface VideoPlayerModalProps {
  video: Video
  onClose: () => void
}

export default function VideoPlayerModal({ video, onClose }: VideoPlayerModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const { accessToken } = useAuthTokens()

  const anyVideo = video as Record<string, unknown>
  const videoId = typeof anyVideo.id === 'number' ? anyVideo.id : null
  const title = typeof anyVideo.title === 'string' ? anyVideo.title : 'Untitled'
  const artist = typeof anyVideo.artist === 'string' ? anyVideo.artist : ''

  // Construct stream URL with auth token as query param
  const streamUrl = videoId && accessToken
    ? `${getApiBaseUrl()}/videos/${videoId}/stream?token=${encodeURIComponent(accessToken)}`
    : null

  // Handle keyboard controls
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const video = videoRef.current
    if (!video) return

    // Don't handle keyboard shortcuts if video controls have focus
    // (let browser's native controls handle spacebar)
    if (e.target === video) return

    switch (e.key) {
      case 'Escape':
        onClose()
        break
      case ' ':
        e.preventDefault()
        if (video.paused) {
          video.play()
        } else {
          video.pause()
        }
        break
      case 'ArrowLeft':
        e.preventDefault()
        video.currentTime = Math.max(0, video.currentTime - 5)
        break
      case 'ArrowRight':
        e.preventDefault()
        video.currentTime = Math.min(video.duration, video.currentTime + 5)
        break
    }
  }, [onClose])

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Focus video element on mount for keyboard controls
  useEffect(() => {
    videoRef.current?.focus()
  }, [])

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  if (!streamUrl) {
    return null
  }

  return (
    <div className="videoPlayerModalOverlay" onClick={handleOverlayClick}>
      <div className="videoPlayerModal" onClick={(e) => e.stopPropagation()}>
        <div className="videoPlayerModalHeader">
          <div className="videoPlayerModalTitle">
            {artist && <span className="videoPlayerModalArtist">{artist}</span>}
            <span className="videoPlayerModalTrack">{title}</span>
          </div>
          <button
            className="videoPlayerModalClose"
            onClick={onClose}
            aria-label="Close player"
            title="Close (Esc)"
          >
            ✕
          </button>
        </div>
        <div className="videoPlayerModalBody">
          <video
            ref={videoRef}
            className="videoPlayerVideo"
            src={streamUrl}
            controls
            autoPlay
            tabIndex={0}
          >
            Your browser does not support video playback.
          </video>
        </div>
        <div className="videoPlayerModalHint">
          Space: play/pause • ←/→: seek ±5s • Esc: close
        </div>
      </div>
    </div>
  )
}
