import { useState, useEffect, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { enrichImvdbVideo } from '../../../lib/api/endpoints/add'
import ArtistVideoRow, { type VideoRowState } from './ArtistVideoRow'
import type { ArtistVideoPreviewItem, ArtistVideoEnrichResponse } from '../../../lib/api/types'
import '../components/SpotifyTrackTable.css'

interface VideoMetadata {
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

interface ArtistVideoTableProps {
  videos: ArtistVideoPreviewItem[]
  artistName: string
  metadataOverrides: Map<number, VideoMetadata>
  onEnrichmentComplete?: (
    video: ArtistVideoPreviewItem,
    enrichment: ArtistVideoEnrichResponse
  ) => void
  onEditVideo: (video: ArtistVideoPreviewItem, state: VideoRowState) => void
  onSearchYouTube: (video: ArtistVideoPreviewItem, artist: string, trackTitle: string) => void
  onSelectionChange?: (selectedIds: Set<number>) => void
  onPreviewYouTube: (youtubeId: string) => void
}

export default function ArtistVideoTable({
  videos,
  artistName,
  metadataOverrides,
  onEnrichmentComplete,
  onEditVideo,
  onSearchYouTube,
  onSelectionChange,
  onPreviewYouTube,
}: ArtistVideoTableProps) {
  // Video states map
  const [videoStates, setVideoStates] = useState<Map<number, VideoRowState>>(new Map())
  const [currentEnrichingIndex, setCurrentEnrichingIndex] = useState(0)
  const [selectedVideos, setSelectedVideos] = useState<Set<number>>(new Set())
  const initializedKeyRef = useRef<string | null>(null)

  // Initialize video states only once
  useEffect(() => {
    const key = videos.map((video) => video.id).join(',')
    if (initializedKeyRef.current === key) return

    initializedKeyRef.current = key
    const initialStates = new Map<number, VideoRowState>()
    videos.forEach((video) => {
      initialStates.set(video.id, {
        enrichmentStatus: 'pending',
        selected: !video.already_exists, // Auto-select new videos
      })
    })
    setVideoStates(initialStates)

    // Auto-select new videos
    const newVideoIds = videos
      .filter((v) => !v.already_exists)
      .map((v) => v.id)
    setSelectedVideos(new Set(newVideoIds))
    setCurrentEnrichingIndex(0)
  }, [videos])

  // Notify parent of selection changes
  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange(selectedVideos)
    }
  }, [selectedVideos, onSelectionChange])

  // Enrichment mutation
  const enrichMutation = useMutation({
    mutationFn: enrichImvdbVideo,
    onSuccess: (data, variables) => {
      const videoId = variables.imvdb_id
      setVideoStates((prev) => {
        const newStates = new Map(prev)
        const currentState = newStates.get(videoId)
        if (currentState) {
          // Consider it success if enrichment completed (even if partial/not_found)
          newStates.set(videoId, {
            ...currentState,
            enrichmentStatus: 'success',
            enrichmentData: data,
          })
        }
        return newStates
      })

      // Call enrichment complete callback
      const video = videos.find((v) => v.id === videoId)
      if (video && onEnrichmentComplete) {
        onEnrichmentComplete(video, data)
      }

      // Move to next video
      setCurrentEnrichingIndex((prev) => prev + 1)
    },
    onError: (error: Error, variables) => {
      const videoId = variables.imvdb_id
      setVideoStates((prev) => {
        const newStates = new Map(prev)
        const currentState = newStates.get(videoId)
        if (currentState) {
          newStates.set(videoId, {
            ...currentState,
            enrichmentStatus: 'error',
          })
        }
        return newStates
      })
      toast.error(`Enrichment failed: ${error.message}`)
      // Move to next video even on error
      setCurrentEnrichingIndex((prev) => prev + 1)
    },
  })

  // Start enrichment when index changes
  useEffect(() => {
    if (currentEnrichingIndex >= videos.length) {
      return
    }

    const video = videos[currentEnrichingIndex]
    
    // Skip if already exists
    if (video.already_exists) {
      setCurrentEnrichingIndex((prev) => prev + 1)
      return
    }

    // Check if already loading or done
    const currentState = videoStates.get(video.id)
    if (currentState && (currentState.enrichmentStatus === 'loading' || currentState.enrichmentStatus === 'success')) {
      return
    }

    // Update state to loading
    setVideoStates((prev) => {
      const newStates = new Map(prev)
      const state = newStates.get(video.id)
      if (state) {
        newStates.set(video.id, {
          ...state,
          enrichmentStatus: 'loading',
        })
      }
      return newStates
    })

    // Start enrichment
    enrichMutation.mutate({
      imvdb_id: video.id,
      artist: artistName,
      track_title: video.song_title || '',
      year: video.year,
      thumbnail_url: video.thumbnail_url,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentEnrichingIndex])

  // Handle selection toggle
  const handleToggleSelection = (videoId: number, selected: boolean) => {
    setSelectedVideos((prev) => {
      const newSet = new Set(prev)
      if (selected) {
        newSet.add(videoId)
      } else {
        newSet.delete(videoId)
      }
      return newSet
    })

    setVideoStates((prev) => {
      const newStates = new Map(prev)
      const currentState = newStates.get(videoId)
      if (currentState) {
        newStates.set(videoId, {
          ...currentState,
          selected,
        })
      }
      return newStates
    })
  }

  // Handle retry enrichment
  const handleRetryEnrichment = (video: ArtistVideoPreviewItem) => {
    setVideoStates((prev) => {
      const newStates = new Map(prev)
      const currentState = newStates.get(video.id)
      if (currentState) {
        newStates.set(video.id, {
          ...currentState,
          enrichmentStatus: 'loading',
        })
      }
      return newStates
    })

    enrichMutation.mutate({
      imvdb_id: video.id,
      artist: artistName,
      track_title: video.song_title || '',
      year: video.year,
      thumbnail_url: video.thumbnail_url,
    })
  }

  const enrichedCount = Array.from(videoStates.values()).filter(
    (s) => s.enrichmentStatus === 'success' || s.enrichmentStatus === 'error'
  ).length
  const allEnriched = enrichedCount >= videos.filter(v => !v.already_exists).length

  return (
    <div className="spotifyTrackTable">
      {!allEnriched && (
        <div className="spotifyTrackTableProgress">
          Enriching {enrichedCount} / {videos.filter(v => !v.already_exists).length} videos...
        </div>
      )}

      <div className="spotifyTrackTableHeader">
        <div className="spotifyTrackTableHeaderCheckbox">
          <input
            type="checkbox"
            checked={selectedVideos.size === videos.filter(v => !v.already_exists).length}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              const newSelected = new Set<number>()
              if (e.target.checked) {
                videos.filter(v => !v.already_exists).forEach(v => newSelected.add(v.id))
              }
              setSelectedVideos(newSelected)
              
              setVideoStates((prev) => {
                const newStates = new Map(prev)
                videos.forEach((video) => {
                  const currentState = newStates.get(video.id)
                  if (currentState && !video.already_exists) {
                    newStates.set(video.id, {
                      ...currentState,
                      selected: e.target.checked,
                    })
                  }
                })
                return newStates
              })
            }}
            disabled={videos.filter(v => !v.already_exists).length === 0}
          />
        </div>
        <div className="spotifyTrackTableHeaderLabel">Track Info</div>
        <div className="spotifyTrackTableHeaderLabel">Match Status</div>
        <div className="spotifyTrackTableHeaderLabel">YouTube</div>
        <div className="spotifyTrackTableHeaderLabel">Actions</div>
      </div>

      <div className="spotifyTrackTableBody">
        {videos.map((video) => {
          const state = videoStates.get(video.id) || {
            enrichmentStatus: 'pending' as const,
            selected: false,
          }

          return (
            <ArtistVideoRow
              key={video.id}
              video={video}
              state={state}
              metadataOverride={metadataOverrides.get(video.id)}
              artistName={artistName}
              onSelect={(selected) => handleToggleSelection(video.id, selected)}
              onEdit={() => onEditVideo(video, state)}
              onSearchYouTube={(artist, title) => onSearchYouTube(video, artist, title)}
              onPreviewYouTube={onPreviewYouTube}
              onRetryEnrichment={() => handleRetryEnrichment(video)}
            />
          )
        })}
      </div>
    </div>
  )
}
