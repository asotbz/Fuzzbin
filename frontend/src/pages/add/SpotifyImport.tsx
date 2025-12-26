import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { addPreviewBatch, addSpotifyImport } from '../../lib/api/endpoints/add'
import { getJob } from '../../lib/api/endpoints/jobs'
import { jobsKeys, videosKeys } from '../../lib/api/queryKeys'
import { useAuthTokens } from '../../auth/useAuthTokens'
import { useJobWebSocket } from '../../lib/ws/useJobWebSocket'
import type { BatchPreviewResponse, SpotifyImportResponse, GetJobResponse } from '../../lib/api/types'
import './SpotifyImport.css'

function isTerminalJobStatus(status: unknown): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

export default function SpotifyImport() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const tokens = useAuthTokens()

  const [playlistId, setPlaylistId] = useState('')
  const [skipExisting, setSkipExisting] = useState(true)
  const [initialStatus, setInitialStatus] = useState<'discovered' | 'imported'>('discovered')
  const [preview, setPreview] = useState<BatchPreviewResponse | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)

  const jobWs = useJobWebSocket(jobId, tokens.accessToken)

  const previewMutation = useMutation({
    mutationFn: () =>
      addPreviewBatch({
        mode: 'spotify',
        spotify_playlist_id: playlistId.trim(),
        skip_existing: skipExisting,
        recursive: true,
      }),
    onSuccess: (data) => {
      setPreview(data)
      toast.success('Preview loaded', {
        description: `Found ${data.total_count} tracks (${data.new_count} new, ${data.existing_count} existing)`,
      })
    },
    onError: (error: Error) => {
      toast.error('Preview failed', { description: error.message })
    },
  })

  const importMutation = useMutation<SpotifyImportResponse, Error, { playlist_id: string; skip_existing: boolean; initial_status: string }>({
    mutationFn: (req) => addSpotifyImport(req),
    onSuccess: (resp) => {
      setJobId(resp.job_id)
      toast.success('Import started!', {
        description: `Job ID: ${resp.job_id}`,
      })
    },
    onError: (error: Error) => {
      toast.error('Import failed', { description: error.message })
    },
  })

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

  // Update job data from WebSocket
  useEffect(() => {
    if (!jobId) return
    const update = jobWs.lastUpdate
    if (!update) return

    queryClient.setQueryData<GetJobResponse>(jobsKeys.byId(jobId), (prev) => {
      if (!prev) return prev
      return {
        ...prev,
        status: update.status as GetJobResponse['status'],
        progress: update.progress,
        current_step: update.current_step,
        processed_items: update.processed_items,
        total_items: update.total_items,
        error: (update.error ?? null) as GetJobResponse['error'],
        result: (update.result ?? null) as GetJobResponse['result'],
      }
    })
  }, [jobId, jobWs.lastUpdate, queryClient])

  // Invalidate videos when job completes
  useEffect(() => {
    if (!jobId) return
    const wsStatus = jobWs.lastUpdate?.status
    const status = wsStatus ?? jobQuery.data?.status
    if (!status || !isTerminalJobStatus(status)) return

    if (status === 'completed') {
      toast.success('Import completed!', {
        action: {
          label: 'View Library',
          onClick: () => navigate('/library'),
        },
      })
    } else if (status === 'failed') {
      toast.error('Import failed', {
        description: jobQuery.data?.error || 'Unknown error',
      })
    }

    queryClient.invalidateQueries({ queryKey: videosKeys.all })
  }, [jobId, jobQuery.data?.status, jobWs.lastUpdate?.status, queryClient, navigate])

  const handlePreview = (e: React.FormEvent) => {
    e.preventDefault()
    if (!playlistId.trim()) {
      toast.error('Please enter a playlist ID or URL')
      return
    }
    previewMutation.mutate()
  }

  const handleImport = () => {
    if (!playlistId.trim()) {
      toast.error('Please enter a playlist ID or URL')
      return
    }

    importMutation.mutate({
      playlist_id: playlistId.trim(),
      skip_existing: skipExisting,
      initial_status: initialStatus,
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
        <div className="spotifyImportCard">
          <h2 className="spotifyImportCardTitle">Playlist Configuration</h2>

          <form onSubmit={handlePreview} className="spotifyImportForm">
            <div className="spotifyImportFormGroup">
              <label className="spotifyImportLabel">Spotify Playlist ID or URL</label>
              <input
                type="text"
                className="spotifyImportInput"
                value={playlistId}
                onChange={(e) => setPlaylistId(e.target.value)}
                placeholder="Enter Spotify playlist ID or URL"
              />
            </div>

            <div className="spotifyImportFormGroup">
              <label className="spotifyImportLabel">Initial Status</label>
              <select
                className="spotifyImportSelect"
                value={initialStatus}
                onChange={(e) => setInitialStatus(e.target.value as 'discovered' | 'imported')}
              >
                <option value="discovered">Discovered</option>
                <option value="imported">Imported</option>
              </select>
            </div>

            <div className="spotifyImportFormGroup">
              <label className="spotifyImportCheckbox">
                <input
                  type="checkbox"
                  checked={skipExisting}
                  onChange={(e) => setSkipExisting(e.target.checked)}
                />
                <span>Skip existing items</span>
              </label>
            </div>

            <div className="spotifyImportActions">
              <button
                type="submit"
                className="spotifyImportButton"
                disabled={previewMutation.isPending}
              >
                {previewMutation.isPending ? 'Loading...' : 'Preview'}
              </button>
              <button
                type="button"
                className="spotifyImportButtonPrimary"
                onClick={handleImport}
                disabled={importMutation.isPending || !playlistId.trim()}
              >
                {importMutation.isPending ? 'Importing...' : 'Import'}
              </button>
            </div>
          </form>
        </div>

        {/* Preview Results */}
        {preview && (
          <div className="spotifyImportCard">
            <h2 className="spotifyImportCardTitle">Preview</h2>
            <div className="spotifyImportStats">
              <div className="spotifyImportStat">
                <div className="spotifyImportStatValue">{preview.total_count}</div>
                <div className="spotifyImportStatLabel">Total Tracks</div>
              </div>
              <div className="spotifyImportStat">
                <div className="spotifyImportStatValue">{preview.new_count}</div>
                <div className="spotifyImportStatLabel">New</div>
              </div>
              <div className="spotifyImportStat">
                <div className="spotifyImportStatValue">{preview.existing_count}</div>
                <div className="spotifyImportStatLabel">Existing</div>
              </div>
            </div>

            {preview.items && preview.items.length > 0 && (
              <div className="spotifyImportPreviewList">
                <h3 className="spotifyImportPreviewTitle">Tracks (showing first 100)</h3>
                {preview.items.slice(0, 100).map((item, index) => (
                  <div key={index} className={`spotifyImportPreviewItem ${item.already_exists ? 'spotifyImportPreviewItemExists' : ''}`}>
                    <div className="spotifyImportPreviewItemInfo">
                      <div className="spotifyImportPreviewItemTitle">{item.title}</div>
                      <div className="spotifyImportPreviewItemArtist">{item.artist}</div>
                    </div>
                    {item.already_exists && (
                      <span className="spotifyImportPreviewItemBadge">Exists</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Job Progress */}
        {jobId && (
          <div className="spotifyImportCard">
            <h2 className="spotifyImportCardTitle">Import Progress</h2>
            <div className="spotifyImportJobStatus">
              <div className="spotifyImportJobStatusHeader">
                <span className={`spotifyImportJobStatusBadge spotifyImportJobStatusBadge${latestJobStatus}`}>
                  {latestJobStatus}
                </span>
                <span className="spotifyImportJobId">Job ID: {jobId}</span>
              </div>

              {currentStep && (
                <div className="spotifyImportJobStep">{currentStep}</div>
              )}

              {typeof progress === 'number' && (
                <div className="spotifyImportJobProgress">
                  <div className="spotifyImportJobProgressBar" style={{ width: `${progress * 100}%` }} />
                </div>
              )}

              {jobWs.state === 'connected' && (
                <div className="spotifyImportJobLive">Live updates connected</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
