import { useState, useEffect, useEffectEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { enrichSpotifyTrack } from '../../../lib/api/endpoints/spotify'
import TrackRow, { type TrackRowState } from './TrackRow'
import IMVDbRetryModal from './IMVDbRetryModal'
import type { BatchPreviewItem, SpotifyTrackEnrichResponse } from '../../../lib/api/types'
import './ImportTrackTable.css'

interface TrackMetadata {
  title: string
  artist: string
  isrc?: string | null
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  featuredArtists: string | null
  youtubeId: string | null
  genre: string | null
}

interface ImportTrackTableProps {
  tracks: BatchPreviewItem[]
  metadataOverrides: Map<string, TrackMetadata>
  onEnrichmentComplete?: (
    track: BatchPreviewItem,
    enrichment: SpotifyTrackEnrichResponse
  ) => void
  onEditTrack: (track: BatchPreviewItem, state: TrackRowState) => void
  onSearchYouTube: (track: BatchPreviewItem, artist: string, trackTitle: string) => void
  onSelectionChange?: (selectedIds: Set<string>) => void
}

export default function ImportTrackTable({
  tracks,
  metadataOverrides,
  onEnrichmentComplete,
  onEditTrack,
  onSearchYouTube,
  onSelectionChange,
}: ImportTrackTableProps) {
  // Build initial track-state maps from the incoming `tracks` prop. Used both
  // for the lazy initializers below and for the render-time prev-deps reset
  // block further down (when `tracks` changes after mount).
  const buildInitialState = (
    items: BatchPreviewItem[]
  ): { states: Map<string, TrackRowState>; selected: Set<string> } => {
    const states = new Map<string, TrackRowState>()
    const selected = new Set<string>()
    items.forEach((track) => {
      const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
      states.set(trackId, {
        enrichmentStatus: 'pending',
        selected: !track.already_exists, // Auto-select new tracks
      })
      if (!track.already_exists) {
        selected.add(trackId)
      }
    })
    return { states, selected }
  }

  // Track states map — seed from `tracks` on mount so first-render enrichment
  // kick-off has a populated state map (otherwise `trackStates.size === 0`
  // would permanently short-circuit `advanceEnrichment`).
  const [trackStates, setTrackStates] = useState<Map<string, TrackRowState>>(
    () => buildInitialState(tracks).states
  )
  const [currentEnrichingIndex, setCurrentEnrichingIndex] = useState(0)
  const [selectedTracks, setSelectedTracks] = useState<Set<string>>(
    () => buildInitialState(tracks).selected
  )
  const [retryingTrack, setRetryingTrack] = useState<BatchPreviewItem | null>(null)

  // Re-initialize when the `tracks` prop changes after mount, using the
  // render-time prev-deps comparison (avoids react-hooks/set-state-in-effect).
  const [prevTracks, setPrevTracks] = useState(tracks)
  if (prevTracks !== tracks) {
    setPrevTracks(tracks)
    const { states, selected } = buildInitialState(tracks)
    setTrackStates(states)
    setSelectedTracks(selected)
    setCurrentEnrichingIndex(0)
  }

  // Notify parent of selection changes
  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange(selectedTracks)
    }
  }, [selectedTracks, onSelectionChange])

  // Enrichment mutation
  const enrichMutation = useMutation({
    mutationFn: enrichSpotifyTrack,
    onSuccess: (data, variables) => {
      const trackId = variables.spotify_track_id
      setTrackStates((prev) => {
        const newStates = new Map(prev)
        const currentState = newStates.get(trackId)
        if (currentState) {
          // Consider it a match if either MusicBrainz or IMVDb found something
          const hasMatch = data.imvdb.match_found || data.musicbrainz.confident_match
          newStates.set(trackId, {
            ...currentState,
            enrichmentStatus: hasMatch ? 'success' : 'no_match',
            enrichmentData: data,
          })
        }
        return newStates
      })

      // Call enrichment complete callback with track and enrichment data
      const track = tracks.find((t) => {
        const id = t.spotify_track_id || `${t.artist}-${t.title}`
        return id === trackId
      })
      if (track && onEnrichmentComplete) {
        onEnrichmentComplete(track, data)
      }

      // Move to next track only after this one completes
      setCurrentEnrichingIndex((prev) => prev + 1)
    },
    onError: (error: Error, variables) => {
      const trackId = variables.spotify_track_id
      setTrackStates((prev) => {
        const newStates = new Map(prev)
        const currentState = newStates.get(trackId)
        if (currentState) {
          newStates.set(trackId, {
            ...currentState,
            enrichmentStatus: 'error',
          })
        }
        return newStates
      })
      toast.error('Enrichment failed', { description: error.message })

      // Move to next track even on error
      setCurrentEnrichingIndex((prev) => prev + 1)
    },
  })

  // Sequential enrichment is a deliberate state machine: the effect kicks
  // off the next track whenever `currentEnrichingIndex` advances. The setState
  // calls inside (skip already_exists, skip non-pending, mark loading) are
  // intentional cascading transitions, so we wrap the body in useEffectEvent
  // to satisfy react-hooks/set-state-in-effect without changing behavior.
  const advanceEnrichment = useEffectEvent(() => {
    // Wait for track states to be initialized
    if (trackStates.size === 0) {
      return
    }

    // Don't start new enrichment if one is already in progress
    if (enrichMutation.isPending) {
      return
    }

    if (currentEnrichingIndex >= tracks.length) {
      // All tracks enriched
      return
    }

    const track = tracks[currentEnrichingIndex]
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
    const state = trackStates.get(trackId)

    // Skip tracks that already exist in library
    if (track.already_exists) {
      setTrackStates((prev) => {
        const newStates = new Map(prev)
        newStates.set(trackId, {
          enrichmentStatus: 'success',
          selected: false,
          enrichmentData: undefined,
        })
        return newStates
      })
      setCurrentEnrichingIndex((prev) => prev + 1)
      return
    }

    if (!state || state.enrichmentStatus !== 'pending') {
      // Skip if already processed
      setCurrentEnrichingIndex((prev) => prev + 1)
      return
    }

    if (!track.spotify_track_id) {
      // Skip if no Spotify track ID
      setCurrentEnrichingIndex((prev) => prev + 1)
      return
    }

    // Mark as loading
    setTrackStates((prev) => {
      const newStates = new Map(prev)
      newStates.set(trackId, {
        ...state,
        enrichmentStatus: 'loading',
      })
      return newStates
    })

    // Start enrichment (will move to next track in onSuccess/onError)
    enrichMutation.mutate({
      spotify_track_id: track.spotify_track_id,
      artist: track.artist,
      track_title: track.title,
      isrc: track.isrc || undefined,
      album: track.album || undefined,
      artist_genres: track.artist_genres || undefined,
    })
  })

  // Mount-only kickoff; subsequent enrichments are chained via the mutation
  // onSuccess/onError callbacks (which advance `currentEnrichingIndex`) and
  // via the `tracks`-change prev-deps reset block above. This is a
  // deliberately cascading sequential state machine with a bounded
  // termination (`currentEnrichingIndex >= tracks.length`), exactly the case
  // the rule's "derived event pattern" suggestion does not cleanly apply to
  // (skip-walk over already_exists rows must be synchronous).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    advanceEnrichment()
  }, [currentEnrichingIndex, tracks, trackStates.size, enrichMutation.isPending])

  // Selection handlers
  const handleSelectTrack = (trackId: string, selected: boolean) => {
    setSelectedTracks((prev) => {
      const newSet = new Set(prev)
      if (selected) {
        newSet.add(trackId)
      } else {
        newSet.delete(trackId)
      }
      return newSet
    })
  }

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      const allIds = tracks
        .filter((t) => !t.already_exists)
        .map((t) => t.spotify_track_id || `${t.artist}-${t.title}`)
      setSelectedTracks(new Set(allIds))

      // Update all track states
      setTrackStates((prev) => {
        const newStates = new Map(prev)
        allIds.forEach((id) => {
          const state = newStates.get(id)
          if (state) {
            newStates.set(id, { ...state, selected: true })
          }
        })
        return newStates
      })
    } else {
      setSelectedTracks(new Set())

      // Update all track states
      setTrackStates((prev) => {
        const newStates = new Map(prev)
        newStates.forEach((state, id) => {
          newStates.set(id, { ...state, selected: false })
        })
        return newStates
      })
    }
  }

  const handlePreviewYouTube = (youtubeId: string) => {
    window.open(`https://youtube.com/watch?v=${youtubeId}`, '_blank')
  }

  const handleRetryIMVDb = (track: BatchPreviewItem, artist: string, trackTitle: string) => {
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`

    // Mark as loading
    setTrackStates((prev) => {
      const newStates = new Map(prev)
      const currentState = newStates.get(trackId)
      if (currentState) {
        newStates.set(trackId, {
          ...currentState,
          enrichmentStatus: 'loading',
        })
      }
      return newStates
    })

    // Call enrichment with modified search terms
    enrichMutation.mutate({
      spotify_track_id: track.spotify_track_id || trackId,
      artist,
      track_title: trackTitle,
      isrc: track.isrc || undefined,
      album: track.album || undefined,
      artist_genres: track.artist_genres || undefined,
    })

    setRetryingTrack(null)
  }

  // Calculate progress
  const enrichedCount = tracks.filter((t) => {
    const trackId = t.spotify_track_id || `${t.artist}-${t.title}`
    const state = trackStates.get(trackId)
    return state && state.enrichmentStatus !== 'pending' && state.enrichmentStatus !== 'loading'
  }).length

  const allSelected = tracks.filter((t) => !t.already_exists).length === selectedTracks.size && selectedTracks.size > 0

  return (
    <div className="importTrackTable">
      {/* Progress */}
      {enrichedCount < tracks.length && (
        <div className="importTrackTableProgress">
          Enriching tracks: {enrichedCount}/{tracks.length}
        </div>
      )}

      {/* Header */}
      <div className="importTrackTableHeader">
        <div className="importTrackTableHeaderCheckbox">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={(e) => handleSelectAll(e.target.checked)}
            title="Select all new tracks"
          />
        </div>
        <div className="importTrackTableHeaderLabel">Track</div>
        <div className="importTrackTableHeaderLabel">Enrichment</div>
        <div className="importTrackTableHeaderLabel">YouTube</div>
        <div className="importTrackTableHeaderLabel">Actions</div>
      </div>

      {/* Rows */}
      <div className="importTrackTableBody">
        {tracks.map((track) => {
          const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
          const state = trackStates.get(trackId) || {
            enrichmentStatus: 'pending' as const,
            selected: false,
          }
          const override = metadataOverrides.get(trackId)

          return (
            <TrackRow
              key={trackId}
              track={track}
              state={state}
              metadataOverride={override}
              onSelect={(selected) => {
                handleSelectTrack(trackId, selected)
                setTrackStates((prev) => {
                  const newStates = new Map(prev)
                  newStates.set(trackId, { ...state, selected })
                  return newStates
                })
              }}
              onEdit={() => onEditTrack(track, state)}
              onSearchYouTube={(artist, trackTitle) => onSearchYouTube(track, artist, trackTitle)}
              onPreviewYouTube={handlePreviewYouTube}
              onRetryIMVDb={() => setRetryingTrack(track)}
            />
          )
        })}
      </div>

      {/* Selection summary */}
      <div className="importTrackTableFooter">
        <span className="importTrackTableSelection">
          {selectedTracks.size} track{selectedTracks.size !== 1 ? 's' : ''} selected
        </span>
      </div>

      {/* Retry Modal */}
      {retryingTrack && (
        <IMVDbRetryModal
          track={retryingTrack}
          onRetry={(artist, trackTitle) => handleRetryIMVDb(retryingTrack, artist, trackTitle)}
          onCancel={() => setRetryingTrack(null)}
        />
      )}
    </div>
  )
}

// Export state and metadata types for parent components
export type { TrackRowState, TrackMetadata }
