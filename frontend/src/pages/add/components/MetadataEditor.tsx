import { useState } from 'react'
import { getDisplayAlbumTitle } from '../../../lib/utils/titleUtils'
import type { BatchPreviewItem } from '../../../lib/api/types'
import type { TrackRowState } from './TrackRow'

export interface EditedMetadata {
  title: string
  artist: string
  isrc: string | null
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  featuredArtists: string | null
  youtubeUrl: string | null
  genre: string | null
}

interface TrackMetadataOverride {
  title: string
  artist: string
  isrc: string | null
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  featuredArtists: string | null
  youtubeId: string | null
  genre: string | null
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

function normalizeIsrc(value: string): string {
  return value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase()
}

export default function MetadataEditor({ track, state, currentOverride, onSave, onCancel }: MetadataEditorProps) {
  const enrichmentData = state.enrichmentData

  // Initialize form with priority: currentOverride > enrichmentData > track
  const [title, setTitle] = useState<string>(
    currentOverride?.title || enrichmentData?.title || track.title
  )
  const [artist, setArtist] = useState<string>(
    currentOverride?.artist || enrichmentData?.artist || track.artist
  )
  const [isrc, setIsrc] = useState<string>(
    currentOverride?.isrc || track.isrc || ''
  )
  const [year, setYear] = useState<string>(
    String(currentOverride?.year ?? enrichmentData?.year ?? track.year ?? '')
  )
  const [album, setAlbum] = useState<string>(
    currentOverride?.album || enrichmentData?.album || getDisplayAlbumTitle(track.album ?? null) || ''
  )
  const [label, setLabel] = useState<string>(
    currentOverride?.label || enrichmentData?.label || track.label || ''
  )
  const [directors, setDirectors] = useState<string>(
    currentOverride?.directors || enrichmentData?.directors || ''
  )
  const [featuredArtists, setFeaturedArtists] = useState<string>(
    currentOverride?.featuredArtists || enrichmentData?.featured_artists || ''
  )
  const [genre, setGenre] = useState<string>(
    currentOverride?.genre || enrichmentData?.genre || ''
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

  const [isrcError, setIsrcError] = useState<string | null>(null)
  const [youtubeUrlError, setYoutubeUrlError] = useState<string | null>(null)

  const handleIsrcChange = (value: string) => {
    setIsrc(value)
    const normalized = normalizeIsrc(value)
    if (normalized && normalized.length !== 12) {
      setIsrcError('ISRC must be 12 characters (format: CCXXXYYNNNNN)')
    } else {
      setIsrcError(null)
    }
  }

  const handleYouTubeUrlChange = (value: string) => {
    setYoutubeUrl(value)
    if (value && !extractYouTubeId(value)) {
      setYoutubeUrlError('Invalid YouTube URL or ID')
    } else {
      setYoutubeUrlError(null)
    }
  }

  const handleRestoreCanonical = () => {
    if (!enrichmentData) return
    
    // Restore canonical values from enrichment data
    if (enrichmentData.title) setTitle(enrichmentData.title)
    if (enrichmentData.artist) setArtist(enrichmentData.artist)
    if (enrichmentData.year !== undefined) setYear(String(enrichmentData.year ?? ''))
    if (enrichmentData.album !== undefined) setAlbum(enrichmentData.album ?? '')
    if (enrichmentData.label !== undefined) setLabel(enrichmentData.label ?? '')
    if (enrichmentData.directors !== undefined) setDirectors(enrichmentData.directors ?? '')
    if (enrichmentData.featured_artists !== undefined) setFeaturedArtists(enrichmentData.featured_artists ?? '')
    if (enrichmentData.genre !== undefined) setGenre(enrichmentData.genre ?? '')
    if (enrichmentData.youtube_ids && enrichmentData.youtube_ids.length > 0) {
      setYoutubeUrl(`https://youtube.com/watch?v=${enrichmentData.youtube_ids[0]}`)
    }
  }

  const handleSave = () => {
    if (!title.trim() || !artist.trim()) {
      return
    }

    const normalizedIsrc = normalizeIsrc(isrc).trim()
    const metadata: EditedMetadata = {
      title: title.trim(),
      artist: artist.trim(),
      isrc: normalizedIsrc || null,
      year: year ? parseInt(year, 10) : null,
      album: album.trim() || null,
      label: label.trim() || null,
      directors: directors.trim() || null,
      featuredArtists: featuredArtists.trim() || null,
      youtubeUrl: youtubeUrl.trim() || null,
      genre: genre.trim() || null,
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
          {/* Show comparison if we have enrichment data */}
          {enrichmentData && (
            <div className="metadataEditorComparison">
              <div className="metadataEditorComparisonHeader">
                <div className="metadataEditorComparisonLabel">Spotify</div>
                <div className="metadataEditorComparisonLabel">MusicBrainz + IMVDb</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Title:</strong> {track.title}</div>
                <div><strong>Title:</strong> {enrichmentData.title || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Artist:</strong> {track.artist}</div>
                <div><strong>Artist:</strong> {enrichmentData.artist || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Album:</strong> {track.album || '-'}</div>
                <div><strong>Album:</strong> {enrichmentData.album || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Year:</strong> {track.year || '-'}</div>
                <div><strong>Year:</strong> {enrichmentData.year || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Label:</strong> {track.label || '-'}</div>
                <div><strong>Label:</strong> {enrichmentData.label || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Genre:</strong> {'-'}</div>
                <div><strong>Genre:</strong> {enrichmentData.genre || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Directors:</strong> {'-'}</div>
                <div><strong>Directors:</strong> {enrichmentData.directors || '-'}</div>
              </div>
              <div className="metadataEditorComparisonRow">
                <div><strong>Featured Artists:</strong> {'-'}</div>
                <div><strong>Featured Artists:</strong> {enrichmentData.featured_artists || '-'}</div>
              </div>
              {enrichmentData.title && enrichmentData.artist && (
                <div className="metadataEditorActions">
                  <button
                    type="button"
                    className="metadataEditorButton"
                    onClick={handleRestoreCanonical}
                  >
                    Restore from Enrichment Data
                  </button>
                </div>
              )}
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
              <label className="metadataEditorLabel">ISRC</label>
              <input
                type="text"
                className={`metadataEditorInput ${isrcError ? 'metadataEditorInputError' : ''}`}
                value={isrc}
                onChange={(e) => handleIsrcChange(e.target.value)}
                placeholder="e.g., USGF19942501"
              />
              {isrcError && (
                <span className="metadataEditorError">{isrcError}</span>
              )}
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
              <label className="metadataEditorLabel">Genre</label>
              <input
                type="text"
                className="metadataEditorInput"
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                placeholder="e.g., Rock, Pop, Hip Hop/R&B"
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
              {enrichmentData?.youtube_ids && enrichmentData.youtube_ids.length > 1 ? (
                <select
                  className="metadataEditorInput"
                  value={extractYouTubeId(youtubeUrl) || ''}
                  onChange={(e) => {
                    const selectedId = e.target.value
                    if (selectedId) {
                      setYoutubeUrl(`https://youtube.com/watch?v=${selectedId}`)
                      setYoutubeUrlError(null)
                    } else {
                      setYoutubeUrl('')
                    }
                  }}
                >
                  <option value="">Select a YouTube video</option>
                  {enrichmentData.youtube_ids.map((id: string, index: number) => (
                    <option key={id} value={id}>
                      YouTube Video {index + 1}: {id}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  className={`metadataEditorInput ${youtubeUrlError ? 'metadataEditorInputError' : ''}`}
                  value={youtubeUrl}
                  onChange={(e) => handleYouTubeUrlChange(e.target.value)}
                  placeholder="https://youtube.com/watch?v=... or video ID"
                />
              )}
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
            disabled={!title.trim() || !artist.trim() || !!youtubeUrlError || !!isrcError}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export { extractYouTubeId }
