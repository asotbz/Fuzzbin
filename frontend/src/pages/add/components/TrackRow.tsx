import type { BatchPreviewItem, SpotifyTrackEnrichResponse } from '../../../lib/api/types'

export interface TrackRowState {
  enrichmentStatus: 'pending' | 'loading' | 'success' | 'error' | 'no_match'
  enrichmentData?: SpotifyTrackEnrichResponse
  selected: boolean
}

interface TrackRowProps {
  track: BatchPreviewItem
  state: TrackRowState
  onSelect: (selected: boolean) => void
  onEdit: () => void
  onSearchYouTube: () => void
  onPreviewYouTube: (youtubeId: string) => void
}

export default function TrackRow({
  track,
  state,
  onSelect,
  onEdit,
  onSearchYouTube,
  onPreviewYouTube,
}: TrackRowProps) {
  const { enrichmentStatus, enrichmentData, selected } = state

  // Get YouTube ID from enrichment data
  const youtubeId =
    enrichmentData?.youtube_ids && enrichmentData.youtube_ids.length > 0
      ? enrichmentData.youtube_ids[0]
      : null

  // Get match type for badge
  const matchType = enrichmentData?.match_type

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
          disabled={enrichmentStatus === 'pending' || enrichmentStatus === 'loading'}
        />
      </div>

      {/* Track Info */}
      <div className="trackRowInfo">
        <div className="trackRowTitle">{track.title}</div>
        <div className="trackRowArtist">{track.artist}</div>
        {track.album && <div className="trackRowAlbum">{track.album}</div>}
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
        {track.already_exists && enrichmentStatus === 'pending' && (
          <span className="trackRowBadge trackRowBadgeExists">Exists</span>
        )}
      </div>

      {/* YouTube Preview */}
      <div className="trackRowYoutube">
        {youtubeId ? (
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
      </div>
    </div>
  )
}
