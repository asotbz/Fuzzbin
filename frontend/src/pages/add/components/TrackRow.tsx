import { useEffect, useState } from 'react'
import { getYouTubeMetadata } from '../../../lib/api/endpoints/spotify'
import { getDisplayTrackTitle, getDisplayAlbumTitle } from '../../../lib/utils/titleUtils'
import type {
  BatchPreviewItem,
  SpotifyTrackEnrichResponse,
  YouTubeMetadataResponse,
} from '../../../lib/api/types'

export interface TrackRowState {
  enrichmentStatus: 'pending' | 'loading' | 'success' | 'error' | 'no_match'
  enrichmentData?: SpotifyTrackEnrichResponse
  selected: boolean
}

interface TrackMetadata {
  title: string
  artist: string
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  youtubeId: string | null
}

interface TrackRowProps {
  track: BatchPreviewItem
  state: TrackRowState
  metadataOverride?: TrackMetadata
  onSelect: (selected: boolean) => void
  onEdit: () => void
  onSearchYouTube: () => void
  onPreviewYouTube: (youtubeId: string) => void
  onRetryIMVDb: () => void
}

export default function TrackRow({
  track,
  state,
  metadataOverride,
  onSelect,
  onEdit,
  onSearchYouTube,
  onPreviewYouTube,
  onRetryIMVDb,
}: TrackRowProps) {
  const { enrichmentStatus, enrichmentData, selected } = state

  // Get YouTube ID from metadata override (if user selected alternate) or enrichment data
  const youtubeId =
    metadataOverride?.youtubeId ||
    (enrichmentData?.youtube_ids && enrichmentData.youtube_ids.length > 0
      ? enrichmentData.youtube_ids[0]
      : null)

  // Get match type for badge
  const matchType = enrichmentData?.match_type

  // YouTube metadata state
  const [youtubeMetadata, setYoutubeMetadata] = useState<YouTubeMetadataResponse | null>(null)
  const [metadataLoading, setMetadataLoading] = useState(false)

  // Fetch YouTube metadata when YouTube ID is available
  useEffect(() => {
    if (!youtubeId) {
      setYoutubeMetadata(null)
      return
    }

    const fetchMetadata = async () => {
      setMetadataLoading(true)
      try {
        const metadata = await getYouTubeMetadata({ youtube_id: youtubeId })
        setYoutubeMetadata(metadata)
      } catch (error) {
        console.error('Failed to fetch YouTube metadata:', error)
        setYoutubeMetadata(null)
      } finally {
        setMetadataLoading(false)
      }
    }

    fetchMetadata()
  }, [youtubeId])

  // Format duration from seconds to MM:SS
  const formatDuration = (seconds: number | null | undefined): string => {
    if (!seconds) return ''
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // Format view count with K/M abbreviations
  const formatViewCount = (views: number | null | undefined): string => {
    if (!views) return ''
    if (views >= 1000000) {
      return `${(views / 1000000).toFixed(1)}M views`
    }
    if (views >= 1000) {
      return `${(views / 1000).toFixed(1)}K views`
    }
    return `${views} views`
  }

  // Get display titles (clean versions)
  const displayTitle = getDisplayTrackTitle(
    track.title,
    enrichmentData?.metadata?.title as string | undefined
  )
  const displayAlbum = getDisplayAlbumTitle(track.album)

  return (
    <div
      className={`trackRow ${
        enrichmentStatus === 'pending'
          ? 'trackRowPending'
          : enrichmentStatus === 'loading'
            ? 'trackRowLoading'
            : enrichmentStatus === 'success'
              ? 'trackRowSuccess'
              : enrichmentStatus === 'no_match'
                ? 'trackRowNoMatch'
                : 'trackRowError'
      } ${selected ? 'trackRowSelected' : ''} ${track.already_exists ? 'trackRowExists' : ''}`}
    >
      {/* Checkbox */}
      <div className="trackRowCheckbox">
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => onSelect(e.target.checked)}
          disabled={track.already_exists || enrichmentStatus === 'pending' || enrichmentStatus === 'loading'}
        />
      </div>

      {/* Track Info */}
      <div className="trackRowInfo">
        <div className="trackRowTitle">{displayTitle}</div>
        <div className="trackRowArtist">{track.artist}</div>
        {displayAlbum && <div className="trackRowAlbum">{displayAlbum}</div>}
      </div>

      {/* Match Status */}
      <div className="trackRowMatch">
        {enrichmentStatus === 'pending' && (
          <span className="trackRowStatusText">Waiting...</span>
        )}
        {enrichmentStatus === 'loading' && (
          <>
            <div className="trackRowSpinner" />
            <span className="trackRowStatusText">Searching IMVDb...</span>
          </>
        )}
        {enrichmentStatus === 'success' && (
          <>
            {track.already_exists ? (
              // Track already exists in library (enrichment was skipped)
              <span className="trackRowBadge trackRowBadgeExists">EXISTS</span>
            ) : (
              // Track was enriched successfully
              <>
                <svg className="trackRowIcon trackRowIconSuccess" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                {matchType && (
                  <span className={`trackRowBadge ${matchType === 'exact' ? 'trackRowBadgeExact' : 'trackRowBadgeFuzzy'}`}>
                    {matchType === 'exact' ? 'Exact Match' : 'Fuzzy Match'}
                  </span>
                )}
                {enrichmentData?.already_exists && (
                  <span className="trackRowBadge trackRowBadgeExists">Exists</span>
                )}
              </>
            )}
          </>
        )}
        {enrichmentStatus === 'no_match' && (
          <>
            <svg className="trackRowIcon trackRowIconWarning" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="trackRowStatusText">No IMVDb match</span>
          </>
        )}
        {enrichmentStatus === 'error' && (
          <>
            <svg className="trackRowIcon trackRowIconError" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            <span className="trackRowStatusText">Error</span>
          </>
        )}
      </div>

      {/* YouTube Preview */}
      <div className="trackRowYoutube">
        {youtubeId ? (
          <>
            <button
              type="button"
              className="trackRowActionButton"
              onClick={() => onPreviewYouTube(youtubeId)}
              title="Preview on YouTube"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </button>
            {metadataLoading ? (
              <div className="trackRowYoutubeMetadata">
                <span className="trackRowYoutubeMetadataLoading">Loading...</span>
              </div>
            ) : youtubeMetadata ? (
              youtubeMetadata.available ? (
                <div className="trackRowYoutubeMetadata">
                  {youtubeMetadata.channel && (
                    <span className="trackRowYoutubeChannel">{youtubeMetadata.channel}</span>
                  )}
                  {youtubeMetadata.view_count && (
                    <span className="trackRowYoutubeViews">
                      {formatViewCount(youtubeMetadata.view_count)}
                    </span>
                  )}
                  {youtubeMetadata.duration && (
                    <span className="trackRowYoutubeDuration">
                      {formatDuration(youtubeMetadata.duration)}
                    </span>
                  )}
                </div>
              ) : (
                <div className="trackRowYoutubeMetadata">
                  <svg
                    className="trackRowYoutubeWarning"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    title={youtubeMetadata.error || 'Video unavailable'}
                  >
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                    <line x1="12" y1="9" x2="12" y2="13" />
                    <line x1="12" y1="17" x2="12.01" y2="17" />
                  </svg>
                  <span className="trackRowYoutubeError">Unavailable</span>
                </div>
              )
            ) : null}
          </>
        ) : enrichmentStatus === 'success' || enrichmentStatus === 'no_match' ? (
          <span className="trackRowStatusText">No video</span>
        ) : null}
      </div>

      {/* Actions */}
      <div className="trackRowActions">
        <button
          type="button"
          className="trackRowActionButton"
          onClick={onEdit}
          disabled={enrichmentStatus === 'pending' || enrichmentStatus === 'loading'}
          title="Edit metadata"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </button>
        <button
          type="button"
          className="trackRowActionButton"
          onClick={onSearchYouTube}
          disabled={enrichmentStatus === 'pending' || enrichmentStatus === 'loading'}
          title="Search YouTube"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
        </button>
        {(enrichmentStatus === 'no_match' || (enrichmentStatus === 'success' && matchType === 'fuzzy')) && !track.already_exists && (
          <button
            type="button"
            className="trackRowActionButton"
            onClick={onRetryIMVDb}
            title="Retry IMVDb search"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M1 4v6h6" />
              <path d="M23 20v-6h-6" />
              <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
