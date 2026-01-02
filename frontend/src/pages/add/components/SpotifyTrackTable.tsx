import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { enrichSpotifyTrack, enrichSpotifyTrackDiscogs } from '../../../lib/api/endpoints/spotify'
import TrackRow, { type TrackRowState } from './TrackRow'
import IMVDbRetryModal from './IMVDbRetryModal'
import type { BatchPreviewItem, SpotifyTrackEnrichResponse } from '../../../lib/api/types'
import './SpotifyTrackTable.css'

interface TrackMetadata {
  title: string
  artist: string
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  featuredArtists: string | null
  youtubeId: string | null
  genre: string | null
}

interface SpotifyTrackTableProps {
  tracks: BatchPreviewItem[]
  metadataOverrides: Map<string, TrackMetadata>
  onEnrichmentComplete?: (
    track: BatchPreviewItem,
    enrichment: SpotifyTrackEnrichResponse
  ) => void
  onDiscogsEnrichmentComplete?: (
    track: BatchPreviewItem,
    enrichment: {
      match_found: boolean
      album?: string | null
      label?: string | null
      genre?: string | null
      year?: number | null
    }
  ) => void
  onEditTrack: (track: BatchPreviewItem, state: TrackRowState) => void
  onSearchYouTube: (track: BatchPreviewItem) => void
  onSelectionChange?: (selectedIds: Set<string>) => void
}

export default function SpotifyTrackTable({
  tracks,
  metadataOverrides,
  onEnrichmentComplete,
  onDiscogsEnrichmentComplete,
  onEditTrack,
  onSearchYouTube,
  onSelectionChange,
}: SpotifyTrackTableProps) {
  // Track states map
  const [trackStates, setTrackStates] = useState<Map<string, TrackRowState>>(new Map())
  const [currentEnrichingIndex, setCurrentEnrichingIndex] = useState(0)
  const [currentDiscogsEnrichingIndex, setCurrentDiscogsEnrichingIndex] = useState(0)
  const [isDiscogsEnrichmentActive, setIsDiscogsEnrichmentActive] = useState(false)
  const [selectedTracks, setSelectedTracks] = useState<Set<string>>(new Set())
  const [retryingTrack, setRetryingTrack] = useState<BatchPreviewItem | null>(null)

  // Initialize track states
  useEffect(() => {
    const initialStates = new Map<string, TrackRowState>()
    tracks.forEach((track) => {
      const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
      initialStates.set(trackId, {
        enrichmentStatus: 'pending',
        selected: !track.already_exists, // Auto-select new tracks
      })
    })
    setTrackStates(initialStates)

    // Auto-select new tracks
    const newTrackIds = tracks
      .filter((t) => !t.already_exists)
      .map((t) => t.spotify_track_id || `${t.artist}-${t.title}`)
    setSelectedTracks(new Set(newTrackIds))
  }, [tracks])

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
          newStates.set(trackId, {
            ...currentState,
            enrichmentStatus: data.match_found ? 'success' : 'no_match',
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

  // Discogs enrichment mutation
  const discogsEnrichMutation = useMutation({
    mutationFn: enrichSpotifyTrackDiscogs,
    onSuccess: (data, variables) => {
      const trackId = variables.spotify_track_id
      setTrackStates((prev) => {
        const newStates = new Map(prev)
        const currentState = newStates.get(trackId)
        if (currentState) {
          newStates.set(trackId, {
            ...currentState,
            discogsEnrichmentStatus: data.match_found ? 'success' : 'no_match',
            discogsEnrichmentData: data,
          })
        }
        return newStates
      })

      // Call enrichment complete callback with track and Discogs data
      const track = tracks.find((t) => {
        const id = t.spotify_track_id || `${t.artist}-${t.title}`
        return id === trackId
      })
      if (track && onDiscogsEnrichmentComplete) {
        onDiscogsEnrichmentComplete(track, {
          match_found: data.match_found,
          album: data.album,
          label: data.label,
          genre: data.genre,
          year: data.year,
        })
      }

      // Move to next track
      setCurrentDiscogsEnrichingIndex((prev) => prev + 1)
    },
    onError: (error: Error, variables) => {
      const trackId = variables.spotify_track_id
      setTrackStates((prev) => {
        const newStates = new Map(prev)
        const currentState = newStates.get(trackId)
        if (currentState) {
          newStates.set(trackId, {
            ...currentState,
            discogsEnrichmentStatus: 'error',
          })
        }
        return newStates
      })
      toast.error('Discogs enrichment failed', { description: error.message })

      // Move to next track even on error
      setCurrentDiscogsEnrichingIndex((prev) => prev + 1)
    },
  })

  // Sequential enrichment effect
  useEffect(() => {
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
      artist: track.artist,
      track_title: track.title,
      spotify_track_id: track.spotify_track_id,
      album: track.album || undefined,
      year: track.year || undefined,
      label: track.label || undefined,
      artist_genres: track.artist_genres || undefined,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentEnrichingIndex, tracks, trackStates.size])

  // Sequential Discogs enrichment effect (runs only when activated)
  useEffect(() => {
    if (!isDiscogsEnrichmentActive) {
      return
    }

    if (trackStates.size === 0) {
      return
    }

    if (discogsEnrichMutation.isPending) {
      return
    }

    if (currentDiscogsEnrichingIndex >= tracks.length) {
      // All tracks processed
      setIsDiscogsEnrichmentActive(false)
      toast.success('Discogs enrichment complete')
      return
    }

    const track = tracks[currentDiscogsEnrichingIndex]
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
    const state = trackStates.get(trackId)

    // Skip tracks that don't have successful IMVDb enrichment or already exist
    if (track.already_exists || !state || state.enrichmentStatus !== 'success' || !state.enrichmentData) {
      setCurrentDiscogsEnrichingIndex((prev) => prev + 1)
      return
    }

    // Skip if already enriched with Discogs
    if (state.discogsEnrichmentStatus && state.discogsEnrichmentStatus !== 'pending') {
      setCurrentDiscogsEnrichingIndex((prev) => prev + 1)
      return
    }

    // Mark as loading
    setTrackStates((prev) => {
      const newStates = new Map(prev)
      newStates.set(trackId, {
        ...state,
        discogsEnrichmentStatus: 'loading',
      })
      return newStates
    })

    // Get normalized artist and track from IMVDb enrichment data
    const normalizedArtist = (state.enrichmentData.metadata?.artist as string) || track.artist
    const normalizedTrack = (state.enrichmentData.metadata?.title as string) || track.title
    const discogsArtistId = state.enrichmentData.discogs_artist_id

    // Start Discogs enrichment
    discogsEnrichMutation.mutate({
      spotify_track_id: track.spotify_track_id || trackId,
      track_title: normalizedTrack,
      artist_name: normalizedArtist,
      discogs_artist_id: discogsArtistId || undefined,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDiscogsEnrichingIndex, isDiscogsEnrichmentActive, tracks, trackStates.size])

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
      artist,
      track_title: trackTitle,
      spotify_track_id: track.spotify_track_id || trackId,
      album: track.album || undefined,
      year: track.year || undefined,
      label: track.label || undefined,
      artist_genres: track.artist_genres || undefined,
    })

    setRetryingTrack(null)
  }

  const handleEnrichDiscogs = (track: BatchPreviewItem) => {
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
    const state = trackStates.get(trackId)

    if (!state || !state.enrichmentData) {
      return
    }

    // Mark as loading
    setTrackStates((prev) => {
      const newStates = new Map(prev)
      newStates.set(trackId, {
        ...state,
        discogsEnrichmentStatus: 'loading',
      })
      return newStates
    })

    // Get normalized artist and track from IMVDb enrichment data
    const normalizedArtist = (state.enrichmentData.metadata?.artist as string) || track.artist
    const normalizedTrack = (state.enrichmentData.metadata?.title as string) || track.title
    const discogsArtistId = state.enrichmentData.discogs_artist_id

    // Enrich single track
    discogsEnrichMutation.mutate({
      spotify_track_id: track.spotify_track_id || trackId,
      track_title: normalizedTrack,
      artist_name: normalizedArtist,
      discogs_artist_id: discogsArtistId || undefined,
    })
  }

  const handleEnrichAllDiscogs = () => {
    setCurrentDiscogsEnrichingIndex(0)
    setIsDiscogsEnrichmentActive(true)
  }

  // Calculate progress
  const enrichedCount = tracks.filter((t) => {
    const trackId = t.spotify_track_id || `${t.artist}-${t.title}`
    const state = trackStates.get(trackId)
    return state && state.enrichmentStatus !== 'pending' && state.enrichmentStatus !== 'loading'
  }).length

  const discogsEnrichedCount = tracks.filter((t) => {
    const trackId = t.spotify_track_id || `${t.artist}-${t.title}`
    const state = trackStates.get(trackId)
    return state && state.discogsEnrichmentStatus === 'success'
  }).length

  const eligibleForDiscogs = tracks.filter((t) => {
    const trackId = t.spotify_track_id || `${t.artist}-${t.title}`
    const state = trackStates.get(trackId)
    return !t.already_exists && state && state.enrichmentStatus === 'success'
  }).length

  const allSelected = tracks.filter((t) => !t.already_exists).length === selectedTracks.size && selectedTracks.size > 0

  return (
    <div className="spotifyTrackTable">
      {/* Progress */}
      {enrichedCount < tracks.length && (
        <div className="spotifyTrackTableProgress">
          Enriching tracks: {enrichedCount}/{tracks.length}
        </div>
      )}
      {isDiscogsEnrichmentActive && (
        <div className="spotifyTrackTableProgress">
          Enriching with Discogs: {discogsEnrichedCount}/{eligibleForDiscogs}
        </div>
      )}

      {/* Discogs Enrich All Button */}
      {enrichedCount >= tracks.length && eligibleForDiscogs > 0 && (
        <div className="spotifyTrackTableActions">
          <button
            type="button"
            className="spotifyTrackTableButton"
            onClick={handleEnrichAllDiscogs}
            disabled={isDiscogsEnrichmentActive}
          >
            {isDiscogsEnrichmentActive ? 'Enriching with Discogs...' : 'Enrich All with Discogs'}
          </button>
        </div>
      )}

      {/* Header */}
      <div className="spotifyTrackTableHeader">
        <div className="spotifyTrackTableHeaderCheckbox">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={(e) => handleSelectAll(e.target.checked)}
            title="Select all new tracks"
          />
        </div>
        <div className="spotifyTrackTableHeaderLabel">Track</div>
        <div className="spotifyTrackTableHeaderLabel">IMVDb Match</div>
        <div className="spotifyTrackTableHeaderLabel">YouTube</div>
        <div className="spotifyTrackTableHeaderLabel">Actions</div>
      </div>

      {/* Rows */}
      <div className="spotifyTrackTableBody">
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
              onSearchYouTube={() => onSearchYouTube(track)}
              onPreviewYouTube={handlePreviewYouTube}
              onRetryIMVDb={() => setRetryingTrack(track)}
              onEnrichDiscogs={() => handleEnrichDiscogs(track)}
            />
          )
        })}
      </div>

      {/* Selection summary */}
      <div className="spotifyTrackTableFooter">
        <span className="spotifyTrackTableSelection">
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
