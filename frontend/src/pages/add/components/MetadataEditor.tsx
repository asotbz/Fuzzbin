import { useState } from 'react'
import { getDisplayAlbumTitle } from '../../../lib/utils/titleUtils'
import type { BatchPreviewItem } from '../../../lib/api/types'
import type { TrackRowState } from './TrackRow'

export interface EditedMetadata {
  title: string
  artist: string
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  featuredArtists: string | null
  youtubeUrl: string | null
}

interface TrackMetadataOverride {
  title: string
  artist: string
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  featuredArtists: string | null
  youtubeId: string | null
}

interface MetadataEditorProps {
  track: BatchPreviewItem
  state: TrackRowState
  currentOverride?: TrackMetadataOverride
  onSave: (metadata: EditedMetadata) => void
  onCancel: () => void
}

function extractYouTubeId(url: string): string | null {
  if (!url) return null

  // Extract ID from various YouTube URL formats
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/, // Direct ID
  ]

  for (const pattern of patterns) {
    const match = url.match(pattern)
    if (match) return match[1]
  }

  return null
}

export default function MetadataEditor({ track, state, currentOverride, onSave, onCancel }: MetadataEditorProps) {
  const enrichmentData = state.enrichmentData

  // Initialize form with priority: currentOverride > enrichmentData > track
  const [title, setTitle] = useState<string>(
    currentOverride?.title || (enrichmentData?.metadata?.title as string | undefined) || track.title
  )
  const [artist, setArtist] = useState<string>(
    currentOverride?.artist || (enrichmentData?.metadata?.artist as string | undefined) || track.artist
  )
  const [year, setYear] = useState<string>(
    String(
      currentOverride?.year ?? (enrichmentData?.metadata?.year as number | null | undefined) ?? track.year ?? ''
    )
  )
  const [album, setAlbum] = useState<string>(
    currentOverride?.album ||
      (enrichmentData?.metadata?.album as string | null | undefined) ||
      getDisplayAlbumTitle(track.album ?? null) ||
      ''
  )
  const [label, setLabel] = useState<string>(
    currentOverride?.label || (enrichmentData?.metadata?.label as string | null | undefined) || track.label || ''
  )
  const [directors, setDirectors] = useState<string>(
    currentOverride?.directors || (enrichmentData?.metadata?.directors as string | null | undefined) || ''
  )
  const [featuredArtists, setFeaturedArtists] = useState<string>(
    currentOverride?.featuredArtists || (enrichmentData?.metadata?.featured_artists as string | null | undefined) || ''
  )
  const [youtubeUrl, setYoutubeUrl] = useState<string>(() => {
    // Priority: currentOverride > enrichmentData > empty
    if (currentOverride?.youtubeId) {
      return `https://youtube.com/watch?v=${currentOverride.youtubeId}`
    }
    if (enrichmentData?.youtube_ids && enrichmentData.youtube_ids.length > 0) {
      return `https://youtube.com/watch?v=${enrichmentData.youtube_ids[0]}`
    }
    return ''
  })

  const [youtubeUrlError, setYoutubeUrlError] = useState<string | null>(null)

  const handleYouTubeUrlChange = (value: string) => {
    setYoutubeUrl(value)
    if (value && !extractYouTubeId(value)) {
      setYoutubeUrlError('Invalid YouTube URL or ID')
    } else {
      setYoutubeUrlError(null)
    }
  }

  const handleSave = () => {
    if (!title.trim() || !artist.trim()) {
      return
    }

    const metadata: EditedMetadata = {
      title: title.trim(),
      artist: artist.trim(),
      year: year ? parseInt(year, 10) : null,
      album: album.trim() || null,
      label: label.trim() || null,
      directors: directors.trim() || null,
      featuredArtists: featuredArtists.trim() || null,
      youtubeUrl: youtubeUrl.trim() || null,
    }

    onSave(metadata)
  }

  return (
    <div className="metadataEditorOverlay" onClick={onCancel}>
      <div className="metadataEditorModal" onClick={(e) => e.stopPropagation()}>
        <div className="metadataEditorHeader">
          <h2 className="metadataEditorTitle">Edit Metadata</h2>
          <button type="button" className="metadataEditorClose" onClick={onCancel}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="metadataEditorBody">
          {/* Show comparison if we have IMVDb data */}
          {enrichmentData?.match_found && (
            <div className="metadataEditorComparison">
              <div className="metadataEditorComparisonHeader">
                <div className="metadataEditorComparisonLabel">Spotify</div>
                <div className="metadataEditorComparisonLabel">IMVDb</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div>{track.title}</div>
                <div>{(enrichmentData.metadata?.title as string | undefined) || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div>{track.artist}</div>
                <div>{(enrichmentData.metadata?.artist as string | undefined) || '-'}</div>
              </div>
            </div>
          )}

          {/* Form fields */}
          <div className="metadataEditorForm">
            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">
                Title <span className="metadataEditorRequired">*</span>
              </label>
              <input
                type="text"
                className="metadataEditorInput"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">
                Artist <span className="metadataEditorRequired">*</span>
              </label>
              <input
                type="text"
                className="metadataEditorInput"
                value={artist}
                onChange={(e) => setArtist(e.target.value)}
                required
              />
            </div>

            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">Year</label>
              <input
                type="number"
                className="metadataEditorInput"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                placeholder="YYYY"
                min="1900"
                max="2100"
              />
            </div>

            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">Album</label>
              <input
                type="text"
                className="metadataEditorInput"
                value={album}
                onChange={(e) => setAlbum(e.target.value)}
              />
            </div>

            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">Record Label</label>
              <input
                type="text"
                className="metadataEditorInput"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g., Columbia, Warner Records"
              />
            </div>

            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">Directors</label>
              <input
                type="text"
                className="metadataEditorInput"
                value={directors}
                onChange={(e) => setDirectors(e.target.value)}
                placeholder="Comma-separated"
              />
            </div>

            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">Featured Artists</label>
              <input
                type="text"
                className="metadataEditorInput"
                value={featuredArtists}
                onChange={(e) => setFeaturedArtists(e.target.value)}
                placeholder="e.g., T.I., Pharrell Williams"
              />
            </div>

            <div className="metadataEditorFormGroup">
              <label className="metadataEditorLabel">YouTube URL or ID</label>
              <input
                type="text"
                className={`metadataEditorInput ${youtubeUrlError ? 'metadataEditorInputError' : ''}`}
                value={youtubeUrl}
                onChange={(e) => handleYouTubeUrlChange(e.target.value)}
                placeholder="https://youtube.com/watch?v=... or video ID"
              />
              {youtubeUrlError && (
                <span className="metadataEditorError">{youtubeUrlError}</span>
              )}
            </div>
          </div>
        </div>

        <div className="metadataEditorFooter">
          <button type="button" className="metadataEditorButton" onClick={onCancel}>
            Cancel
          </button>
          <button
            type="button"
            className="metadataEditorButtonPrimary"
            onClick={handleSave}
            disabled={!title.trim() || !artist.trim() || !!youtubeUrlError}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}

export { extractYouTubeId }
