/* eslint-disable @typescript-eslint/no-explicit-any -- Import wizard handles dynamic API responses */
import { useState, useEffect, useRef, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { addPreviewBatch } from '../../lib/api/endpoints/add'
import { importSelectedTracks } from '../../lib/api/endpoints/spotify'
import { getJob } from '../../lib/api/endpoints/jobs'
import { jobsKeys, videosKeys } from '../../lib/api/queryKeys'
import { useAuthTokens } from '../../auth/useAuthTokens'
import { useJobEvents } from '../../lib/ws/useJobEvents'
import SpotifyTrackTable, { type TrackRowState } from './components/SpotifyTrackTable'
import MetadataEditor, { type EditedMetadata, extractYouTubeId } from './components/MetadataEditor'
import YouTubeSearchModal from './components/YouTubeSearchModal'
import type {
  BatchPreviewResponse,
  BatchPreviewItem,
  SpotifyBatchImportResponse,
  GetJobResponse,
} from '../../lib/api/types'
import './SpotifyImport.css'

function isTerminalJobStatus(status: unknown): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
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
  genre: string | null
}

interface EnrichedMetadata {
  title?: string
  artist?: string
  year?: number | null
  album?: string | null
  label?: string | null
  directors?: string | null
  featuredArtists?: string | null
  youtubeIds?: string[]
  imvdbId?: number | null
  imvdbUrl?: string | null
  genre?: string | null
  genreNormalized?: string | null
  sourceGenres?: string[] | null
  thumbnailUrl?: string | null
}

export default function SpotifyImport() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const tokens = useAuthTokens()

  // Configuration state
  const [playlistId, setPlaylistId] = useState('')
  const [autoDownload, setAutoDownload] = useState(true)

  // Preview/table state
  const [preview, setPreview] = useState<BatchPreviewResponse | null>(null)
  const [metadataOverrides, setMetadataOverrides] = useState<Map<string, TrackMetadataOverride>>(new Map())
  const [enrichmentData, setEnrichmentData] = useState<Map<string, EnrichedMetadata>>(new Map())
  const [selectedTrackIds, setSelectedTrackIds] = useState<Set<string>>(new Set())

  // Modal state
  const [editingTrack, setEditingTrack] = useState<{ track: BatchPreviewItem; state: TrackRowState } | null>(null)
  const [searchingTrack, setSearchingTrack] = useState<BatchPreviewItem | null>(null)

  // Job state
  const [jobId, setJobId] = useState<string | null>(null)

  // Subscribe to job events for the active job
  const jobIds = useMemo(() => (jobId ? [jobId] : null), [jobId])
  const { connectionState: wsState, getJob: getJobFromWs } = useJobEvents(tokens.accessToken, {
    jobIds,
    includeActiveState: true,
    autoConnect: Boolean(jobId),
  })
  const wsJobData = jobId ? getJobFromWs(jobId) : null

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: () =>
      addPreviewBatch({
        mode: 'spotify',
        spotify_playlist_id: playlistId.trim(),
        skip_existing: false, // Show all tracks in table
        recursive: true,
      }),
    onSuccess: (data) => {
      setPreview(data)
      toast.success('Playlist loaded', {
        description: `Found ${data.total_count} tracks (${data.new_count} new, ${data.existing_count} existing)`,
      })
    },
    onError: (error: Error) => {
      toast.error('Failed to load playlist', { description: error.message })
    },
  })

  // Import mutation
  const importMutation = useMutation<
    SpotifyBatchImportResponse,
    Error,
    { tracks: any[]; playlist_id: string; initial_status: string; auto_download: boolean }
  >({
    mutationFn: (req) => importSelectedTracks(req),
    onSuccess: (resp) => {
      setJobId(resp.job_id)
      toast.success('Import started!', {
        description: `Importing ${resp.track_count} tracks. ${resp.auto_download ? 'Downloads will be queued automatically.' : ''}`,
      })
    },
    onError: (error: Error) => {
      toast.error('Import failed', { description: error.message })
    },
  })

  // Job query
  const jobQuery = useQuery<GetJobResponse>({
    queryKey: jobId ? jobsKeys.byId(jobId) : jobsKeys.byId('none'),
    enabled: Boolean(jobId),
    queryFn: async () => {
      if (!jobId) throw new Error('No job')
      return getJob(jobId)
    },
    refetchInterval: (query) => {
      const status = (query.state.data as GetJobResponse | undefined)?.status
      if (status && isTerminalJobStatus(status)) return false
      if (wsState === 'connected') return false
      return 1000
    },
  })

  // WebSocket updates
  useEffect(() => {
    if (jobId && wsJobData) {
      queryClient.setQueryData<GetJobResponse>(jobsKeys.byId(jobId), (prev) => {
        if (!prev) return prev
        return {
          ...prev,
          status: wsJobData.status as GetJobResponse['status'],
          progress: wsJobData.progress,
          current_step: wsJobData.current_step,
          processed_items: wsJobData.processed_items,
          total_items: wsJobData.total_items,
          error: (wsJobData.error ?? null) as GetJobResponse['error'],
          result: (wsJobData.result ?? null) as GetJobResponse['result'],
        }
      })
    }
  }, [jobId, wsJobData, queryClient])

  // Job completion handling
  const hasShownToastRef = useRef(false)

  useEffect(() => {
    if (!jobId) {
      hasShownToastRef.current = false
      return
    }

    const wsStatus = wsJobData?.status
    const status = wsStatus ?? jobQuery.data?.status

    if (status && isTerminalJobStatus(status) && !hasShownToastRef.current) {
      hasShownToastRef.current = true

      if (status === 'completed') {
        const result = jobQuery.data?.result as any
        const downloadJobs = result?.download_jobs || 0

        toast.success('Import completed!', {
          description: `Imported ${result?.imported || 0} tracks${downloadJobs > 0 ? `. ${downloadJobs} download jobs queued.` : ''}`,
        })
        queryClient.invalidateQueries({ queryKey: videosKeys.all })
        navigate('/library')
      } else if (status === 'failed') {
        toast.error('Import failed', {
          description: jobQuery.data?.error || 'Unknown error',
        })
      }
    }
  }, [jobId, wsJobData?.status, jobQuery.data?.status, jobQuery.data?.result, jobQuery.data?.error, navigate, queryClient])

  const handleLoadPlaylist = (e: React.FormEvent) => {
    e.preventDefault()
    if (!playlistId.trim()) {
      toast.error('Please enter a playlist ID or URL')
      return
    }
    previewMutation.mutate()
  }

  const handleSaveMetadata = (track: BatchPreviewItem, metadata: EditedMetadata) => {
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`

    // Extract YouTube ID from URL if provided
    const youtubeId = metadata.youtubeUrl ? extractYouTubeId(metadata.youtubeUrl) : null

    setMetadataOverrides((prev) => {
      const newMap = new Map(prev)
      newMap.set(trackId, {
        title: metadata.title,
        artist: metadata.artist,
        year: metadata.year,
        album: metadata.album,
        label: metadata.label,
        directors: metadata.directors,
        featuredArtists: metadata.featuredArtists,
        youtubeId,
        genre: metadata.genre,
      })
      return newMap
    })

    setEditingTrack(null)
    toast.success('Metadata updated')
  }

  const handleYouTubeSelect = (track: BatchPreviewItem, youtubeId: string) => {
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`

    setMetadataOverrides((prev) => {
      const newMap = new Map(prev)
      const existing = newMap.get(trackId) || {
        title: track.title,
        artist: track.artist,
        year: track.year ?? null,
        album: track.album ?? null,
        label: track.label ?? null,
        directors: null,
        featuredArtists: null,
        youtubeId: null,
        genre: null,
      }
      newMap.set(trackId, { ...existing, youtubeId })
      return newMap
    })

    setSearchingTrack(null)
    toast.success('YouTube video selected')
  }

  const handleEnrichmentComplete = (
    track: BatchPreviewItem,
    enrichment: {
      metadata?: {
        title?: string
        artist?: string
        year?: number | null
        album?: string | null
        label?: string | null
        directors?: string | null
        featured_artists?: string | null
        genre?: string | null
        genre_normalized?: string | null
      }
      youtube_ids?: string[]
      imvdb_id?: number | null
      imvdb_url?: string | null
      genre?: string | null
      genre_normalized?: string | null
      source_genres?: string[] | null
      thumbnail_url?: string | null
    }
  ) => {
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`

    setEnrichmentData((prev) => {
      const newMap = new Map(prev)
      newMap.set(trackId, {
        title: enrichment.metadata?.title,
        artist: enrichment.metadata?.artist,
        year: enrichment.metadata?.year,
        album: enrichment.metadata?.album,
        label: enrichment.metadata?.label,
        directors: enrichment.metadata?.directors,
        featuredArtists: enrichment.metadata?.featured_artists,
        youtubeIds: enrichment.youtube_ids,
        imvdbId: enrichment.imvdb_id,
        imvdbUrl: enrichment.imvdb_url,
        genre: enrichment.genre,
        genreNormalized: enrichment.genre_normalized,
        sourceGenres: enrichment.source_genres,
        thumbnailUrl: enrichment.thumbnail_url,
      })
      return newMap
    })
  }

  const handleImport = () => {
    if (!preview || selectedTrackIds.size === 0) {
      toast.error('Please select tracks to import')
      return
    }

    // Build tracks array with metadata from three sources (priority: override > enrichment > original)
    const tracks = (preview.items ?? [])
      .filter((track) => {
        const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
        return selectedTrackIds.has(trackId)
      })
      .map((track) => {
        const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
        const override = metadataOverrides.get(trackId)
        const enrichment = enrichmentData.get(trackId)

        // Priority: User override > Enrichment data > Original Spotify data
        // For genre: prefer normalized version from enrichment (maps to primary categories like Rock, Pop, etc.)
        const finalMetadata = {
          title: override?.title ?? enrichment?.title ?? track.title,
          artist: override?.artist ?? enrichment?.artist ?? track.artist,
          year: override?.year ?? enrichment?.year ?? track.year,
          album: override?.album ?? enrichment?.album ?? track.album,
          label: override?.label ?? enrichment?.label ?? track.label,
          directors: override?.directors ?? enrichment?.directors ?? null,
          featured_artists: override?.featuredArtists ?? enrichment?.featuredArtists ?? null,
          genre: override?.genre ?? enrichment?.genreNormalized ?? enrichment?.genre ?? null,
          genre_normalized: enrichment?.genreNormalized ?? null,
        }

        // For YouTube ID, prefer user override, then enrichment (first available ID)
        const youtubeId =
          override?.youtubeId ??
          (enrichment?.youtubeIds && enrichment.youtubeIds.length > 0
            ? enrichment.youtubeIds[0]
            : null)

        return {
          spotify_track_id: track.spotify_track_id || trackId,
          metadata: finalMetadata,
          imvdb_id: enrichment?.imvdbId ?? null,
          imvdb_url: enrichment?.imvdbUrl ?? null,
          youtube_id: youtubeId,
          youtube_url: youtubeId ? `https://youtube.com/watch?v=${youtubeId}` : null,
          thumbnail_url: enrichment?.thumbnailUrl ?? null,
        }
      })

    importMutation.mutate({
      playlist_id: playlistId.trim(),
      tracks,
      initial_status: 'discovered',
      auto_download: autoDownload,
    })
  }

  const latestJobStatus = (wsJobData?.status ?? jobQuery.data?.status) as string | undefined
  const progress = wsJobData?.progress ?? jobQuery.data?.progress ?? 0
  const currentStep = wsJobData?.current_step ?? jobQuery.data?.current_step

  return (
    <div className="spotifyImport">
      <header className="spotifyImportHeader">
        <div className="spotifyImportHeaderTop">
          <div className="spotifyImportTitleContainer">
            <img src="/fuzzbin-icon.png" alt="Fuzzbin" className="spotifyImportIcon" />
            <h1 className="spotifyImportTitle">Spotify Playlist Import</h1>
          </div>
        </div>

        <nav className="spotifyImportNav">
          <Link to="/add" className="primaryButton">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: '16px', height: '16px' }}>
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Back to Hub
          </Link>
          <Link to="/library" className="primaryButton">
            Video Library
          </Link>
        </nav>
      </header>

      <div className="spotifyImportContent">
        {/* Configuration Card */}
        <div className="spotifyImportCard">
          <h2 className="spotifyImportCardTitle">Playlist Configuration</h2>

          <form onSubmit={handleLoadPlaylist} className="spotifyImportForm">
            <div className="spotifyImportFormGroup">
              <label className="spotifyImportLabel">Spotify Playlist ID or URL</label>
              <input
                type="text"
                className="spotifyImportInput"
                value={playlistId}
                onChange={(e) => setPlaylistId(e.target.value)}
                placeholder="Enter Spotify playlist ID or URL"
                disabled={!!preview}
              />
            </div>

            <div className="spotifyImportFormGroup">
              <label className="spotifyImportCheckbox">
                <input
                  type="checkbox"
                  checked={autoDownload}
                  onChange={(e) => setAutoDownload(e.target.checked)}
                  disabled={!!preview}
                />
                <span>Auto-download videos after import</span>
              </label>
            </div>

            {!preview && (
              <button
                type="submit"
                className="spotifyImportButtonPrimary"
                disabled={previewMutation.isPending || !playlistId.trim()}
              >
                {previewMutation.isPending ? 'Loading...' : 'Load Playlist'}
              </button>
            )}

            {preview && (
              <button
                type="button"
                className="spotifyImportButton"
                onClick={() => {
                  setPreview(null)
                  setMetadataOverrides(new Map())
                  setSelectedTrackIds(new Set())
                }}
              >
                Start Over
              </button>
            )}
          </form>
        </div>

        {/* Interactive Table */}
        {preview && (
          <>
            <div className="spotifyImportCard">
              <h2 className="spotifyImportCardTitle">Playlist Tracks</h2>
              <SpotifyTrackTable
                tracks={preview.items ?? []}
                metadataOverrides={metadataOverrides}
                onEditTrack={(track, state) => setEditingTrack({ track, state })}
                onSearchYouTube={(track) => setSearchingTrack(track)}
                onSelectionChange={(selectedIds) => setSelectedTrackIds(selectedIds)}
                onEnrichmentComplete={handleEnrichmentComplete}
              />
            </div>

            {/* Import Actions */}
            <div className="spotifyImportCard">
              <div className="spotifyImportActions">
                <button
                  type="button"
                  className="spotifyImportButtonPrimary"
                  onClick={handleImport}
                  disabled={importMutation.isPending || selectedTrackIds.size === 0}
                >
                  {importMutation.isPending
                    ? 'Importing...'
                    : `Import Selected Tracks (${selectedTrackIds.size})`}
                </button>
              </div>
            </div>
          </>
        )}

        {/* Job Progress */}
        {jobId && (
          <div className="spotifyImportCard">
            <h2 className="spotifyImportCardTitle">Import Progress</h2>
            <div className="spotifyImportJobStatus">
              <div className="spotifyImportJobStatusHeader">
                <span
                  className={`spotifyImportJobStatusBadge spotifyImportJobStatusBadge${latestJobStatus}`}
                >
                  {latestJobStatus}
                </span>
                <span className="spotifyImportJobId">Job ID: {jobId}</span>
              </div>

              {currentStep && <div className="spotifyImportJobStep">{currentStep}</div>}

              {typeof progress === 'number' && (
                <div className="spotifyImportJobProgress">
                  <div
                    className="spotifyImportJobProgressBar"
                    style={{ width: `${progress * 100}%` }}
                  />
                </div>
              )}

              {wsState === 'connected' && (
                <div className="spotifyImportJobLive">Live updates connected</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      {editingTrack && (
        <MetadataEditor
          track={editingTrack.track}
          state={editingTrack.state}
          currentOverride={metadataOverrides.get(
            editingTrack.track.spotify_track_id || `${editingTrack.track.artist}-${editingTrack.track.title}`
          )}
          onSave={(metadata) => handleSaveMetadata(editingTrack.track, metadata)}
          onCancel={() => setEditingTrack(null)}
        />
      )}

      {searchingTrack && (
        <YouTubeSearchModal
          artist={searchingTrack.artist}
          trackTitle={searchingTrack.title}
          onSelect={(youtubeId) => handleYouTubeSelect(searchingTrack, youtubeId)}
          onCancel={() => setSearchingTrack(null)}
        />
      )}
    </div>
  )
}
