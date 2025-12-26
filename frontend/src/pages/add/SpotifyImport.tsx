import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { addPreviewBatch } from '../../lib/api/endpoints/add'
import { importSelectedTracks } from '../../lib/api/endpoints/spotify'
import { getJob } from '../../lib/api/endpoints/jobs'
import { jobsKeys, videosKeys } from '../../lib/api/queryKeys'
import { useAuthTokens } from '../../auth/useAuthTokens'
import { useJobWebSocket } from '../../lib/ws/useJobWebSocket'
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
  youtubeId: string | null
}

export default function SpotifyImport() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const tokens = useAuthTokens()

  // Configuration state
  const [playlistId, setPlaylistId] = useState('')
  const [initialStatus, setInitialStatus] = useState<'discovered' | 'imported'>('discovered')
  const [autoDownload, setAutoDownload] = useState(false)

  // Preview/table state
  const [preview, setPreview] = useState<BatchPreviewResponse | null>(null)
  const [metadataOverrides, setMetadataOverrides] = useState<Map<string, TrackMetadataOverride>>(new Map())
  const [selectedTrackIds, setSelectedTrackIds] = useState<Set<string>>(new Set())

  // Modal state
  const [editingTrack, setEditingTrack] = useState<{ track: BatchPreviewItem; state: TrackRowState } | null>(null)
  const [searchingTrack, setSearchingTrack] = useState<BatchPreviewItem | null>(null)

  // Job state
  const [jobId, setJobId] = useState<string | null>(null)

  const jobWs = useJobWebSocket(jobId, tokens.accessToken)

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
      if (jobWs.state === 'connected') return false
      return 1000
    },
  })

  // WebSocket updates
  if (jobId && jobWs.lastUpdate) {
    queryClient.setQueryData<GetJobResponse>(jobsKeys.byId(jobId), (prev) => {
      if (!prev) return prev
      return {
        ...prev,
        status: jobWs.lastUpdate!.status as GetJobResponse['status'],
        progress: jobWs.lastUpdate!.progress,
        current_step: jobWs.lastUpdate!.current_step,
        processed_items: jobWs.lastUpdate!.processed_items,
        total_items: jobWs.lastUpdate!.total_items,
        error: (jobWs.lastUpdate!.error ?? null) as GetJobResponse['error'],
        result: (jobWs.lastUpdate!.result ?? null) as GetJobResponse['result'],
      }
    })
  }

  // Job completion handling
  if (jobId) {
    const wsStatus = jobWs.lastUpdate?.status
    const status = wsStatus ?? jobQuery.data?.status
    if (status && isTerminalJobStatus(status)) {
      if (status === 'completed') {
        const result = jobQuery.data?.result as any
        const downloadJobs = result?.download_jobs || 0

        toast.success('Import completed!', {
          description: `Imported ${result?.imported || 0} tracks${downloadJobs > 0 ? `. ${downloadJobs} download jobs queued.` : ''}`,
          action: {
            label: 'View Library',
            onClick: () => navigate('/library'),
          },
        })
        queryClient.invalidateQueries({ queryKey: videosKeys.all })
      } else if (status === 'failed') {
        toast.error('Import failed', {
          description: jobQuery.data?.error || 'Unknown error',
        })
      }
    }
  }

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
        youtubeId,
      })
      return newMap
    })

    setEditingTrack(null)
    toast.success('Metadata updated')
  }

  const handleYouTubeSelect = (track: BatchPreviewItem, youtubeId: string, youtubeUrl: string) => {
    const trackId = track.spotify_track_id || `${track.artist}-${track.title}`

    setMetadataOverrides((prev) => {
      const newMap = new Map(prev)
      const existing = newMap.get(trackId) || {
        title: track.title,
        artist: track.artist,
        year: track.year,
        album: track.album,
        label: track.label,
        directors: null,
        youtubeId: null,
      }
      newMap.set(trackId, { ...existing, youtubeId })
      return newMap
    })

    setSearchingTrack(null)
    toast.success('YouTube video selected')
  }

  const handleImport = () => {
    if (!preview || selectedTrackIds.size === 0) {
      toast.error('Please select tracks to import')
      return
    }

    // Build tracks array with metadata overrides
    const tracks = preview.items
      .filter((track) => {
        const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
        return selectedTrackIds.has(trackId)
      })
      .map((track) => {
        const trackId = track.spotify_track_id || `${track.artist}-${track.title}`
        const override = metadataOverrides.get(trackId)

        return {
          spotify_track_id: track.spotify_track_id || trackId,
          metadata: {
            title: override?.title || track.title,
            artist: override?.artist || track.artist,
            year: override?.year || track.year,
            album: override?.album || track.album,
            label: override?.label || track.label,
            directors: override?.directors || null,
          },
          imvdb_id: null, // Will be set by enrichment
          youtube_id: override?.youtubeId || null,
          youtube_url: override?.youtubeId ? `https://youtube.com/watch?v=${override.youtubeId}` : null,
        }
      })

    importMutation.mutate({
      playlist_id: playlistId.trim(),
      tracks,
      initial_status: initialStatus,
      auto_download: autoDownload,
    })
  }

  const latestJobStatus = (jobWs.lastUpdate?.status ?? jobQuery.data?.status) as string | undefined
  const progress = jobWs.lastUpdate?.progress ?? jobQuery.data?.progress ?? 0
  const currentStep = jobWs.lastUpdate?.current_step ?? jobQuery.data?.current_step

  return (
    <div className="spotifyImport">
      <div className="spotifyImportHeader">
        <h1 className="spotifyImportTitle">Spotify Playlist Import</h1>
        <Link to="/add" className="spotifyImportBackLink">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back to Hub
        </Link>
      </div>

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
              <label className="spotifyImportLabel">Initial Status</label>
              <select
                className="spotifyImportSelect"
                value={initialStatus}
                onChange={(e) => setInitialStatus(e.target.value as 'discovered' | 'imported')}
                disabled={!!preview}
              >
                <option value="discovered">Discovered</option>
                <option value="imported">Imported</option>
              </select>
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
                tracks={preview.items}
                onEditTrack={(track, state) => setEditingTrack({ track, state })}
                onSearchYouTube={(track) => setSearchingTrack(track)}
                onSelectionChange={(selectedIds) => setSelectedTrackIds(selectedIds)}
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

              {jobWs.state === 'connected' && (
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
          onSave={(metadata) => handleSaveMetadata(editingTrack.track, metadata)}
          onCancel={() => setEditingTrack(null)}
        />
      )}

      {searchingTrack && (
        <YouTubeSearchModal
          artist={searchingTrack.artist}
          trackTitle={searchingTrack.title}
          onSelect={(youtubeId, youtubeUrl) => handleYouTubeSelect(searchingTrack, youtubeId, youtubeUrl)}
          onCancel={() => setSearchingTrack(null)}
        />
      )}
    </div>
  )
}
