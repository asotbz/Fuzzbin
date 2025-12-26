import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { enrichSpotifyTrack } from '../../../lib/api/endpoints/spotify'
import TrackRow, { type TrackRowState } from './TrackRow'
import type { BatchPreviewItem, SpotifyTrackEnrichResponse } from '../../../lib/api/types'
import './SpotifyTrackTable.css'

interface TrackMetadata {
  title: string
  artist: string
  year: number | null
  album: string | null
  label: string | null
  directors: string | null
  youtubeId: string | null
}

interface SpotifyTrackTableProps {
  tracks: BatchPreviewItem[]
  onEnrichmentComplete?: () => void
  onEditTrack: (track: BatchPreviewItem, state: TrackRowState) => void
  onSearchYouTube: (track: BatchPreviewItem) => void
  onSelectionChange?: (selectedIds: Set<string>) => void
}

export default function SpotifyTrackTable({
  tracks,
  onEnrichmentComplete,
  onEditTrack,
  onSearchYouTube,
  onSelectionChange,
}: SpotifyTrackTableProps) {
  // Track states map
  const [trackStates, setTrackStates] = useState<Map<string, TrackRowState>>(new Map())
  const [currentEnrichingIndex, setCurrentEnrichingIndex] = useState(0)
  const [selectedTracks, setSelectedTracks] = useState<Set<string>>(new Set())

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

  // Sequential enrichment effect
  useEffect(() => {
    // Don't start new enrichment if one is already in progress
    if (enrichMutation.isPending) {
      return
    }

    if (currentEnrichingIndex >= tracks.length) {
      // All tracks enriched
      if (onEnrichmentComplete) {
        onEnrichmentComplete()
      }
      return
    }

    const track = tracks[currentEnrichingIndex]
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
    const state = trackStates.get(trackId)

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
    })
  }, [currentEnrichingIndex, tracks, trackStates, enrichMutation, onEnrichmentComplete])

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

  // Calculate progress
  const enrichedCount = tracks.filter((t) => {
    const trackId = t.spotify_track_id || `${t.artist}-${t.title}`
    const state = trackStates.get(trackId)
    return state && state.enrichmentStatus !== 'pending' && state.enrichmentStatus !== 'loading'
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

          return (
            <TrackRow
              key={trackId}
              track={track}
              state={state}
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
    </div>
  )
}

// Export state and metadata types for parent components
export type { TrackRowState, TrackMetadata }
