import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { addImport, addNFOScan, addPreview, addPreviewBatch, addSearch, addSpotifyImport } from '../lib/api/endpoints/add'
import { getJob } from '../lib/api/endpoints/jobs'
import { addKeys, jobsKeys, videosKeys } from '../lib/api/queryKeys'
import { useAuthTokens } from '../auth/useAuthTokens'
import { useJobWebSocket } from '../lib/ws/useJobWebSocket'
import type {
  AddPreviewResponse,
  AddSearchResponse,
  AddSingleImportRequest,
  AddSingleImportResponse,
  BatchPreviewResponse,
  NFOScanResponse,
  SpotifyImportResponse,
  GetJobResponse,
} from '../lib/api/types'
import './Add.css'

function isTerminalJobStatus(status: unknown): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

function safeString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function safeNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export default function AddPage() {
  const queryClient = useQueryClient()
  const tokens = useAuthTokens()

  const [artist, setArtist] = useState('')
  const [trackTitle, setTrackTitle] = useState('')

  const [searchData, setSearchData] = useState<AddSearchResponse | null>(null)
  const [selected, setSelected] = useState<{ source: string; id: string } | null>(null)

  const [youtubeId, setYoutubeId] = useState('')
  const [initialStatus, setInitialStatus] = useState<'discovered' | 'imported'>('discovered')
  const [skipExisting, setSkipExisting] = useState(true)

  const [spotifyPlaylistId, setSpotifyPlaylistId] = useState('')
  const [spotifySkipExisting, setSpotifySkipExisting] = useState(true)
  const [spotifyInitialStatus, setSpotifyInitialStatus] = useState<'discovered' | 'imported'>('discovered')
  const [spotifyPreview, setSpotifyPreview] = useState<BatchPreviewResponse | null>(null)

  const [nfoDirectory, setNfoDirectory] = useState('')
  const [nfoRecursive, setNfoRecursive] = useState(true)
  const [nfoSkipExisting, setNfoSkipExisting] = useState(true)
  const [nfoMode, setNfoMode] = useState<'full' | 'discovery'>('full')
  const [nfoPreview, setNfoPreview] = useState<BatchPreviewResponse | null>(null)

  const [jobId, setJobId] = useState<string | null>(null)
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set())

  const jobWs = useJobWebSocket(jobId, tokens.accessToken)

  const searchMutation = useMutation({
    mutationFn: () =>
      addSearch({
        artist: artist.trim(),
        track_title: trackTitle.trim(),
        imvdb_per_page: 10,
        discogs_per_page: 10,
        youtube_max_results: 5,
      }),
    onSuccess: (data) => {
      setSearchData(data)
      setSelected(null)
      setYoutubeId('')
      setJobId(null)
    },
  })

  const previewQuery = useQuery<AddPreviewResponse>({
    queryKey: selected ? addKeys.preview(selected.source, selected.id) : addKeys.preview('none', 'none'),
    enabled: Boolean(selected),
    queryFn: async () => {
      if (!selected) throw new Error('No selection')
      return addPreview(selected.source, selected.id)
    },
  })

  useEffect(() => {
    const extra = previewQuery.data?.extra as unknown
    if (youtubeId.trim().length > 0) return
    if (!extra || typeof extra !== 'object') return

    const ids = (extra as Record<string, unknown>).youtube_ids
    if (!Array.isArray(ids) || ids.length === 0) return
    const first = ids.find((x) => typeof x === 'string' && x.length > 0)
    if (typeof first === 'string') setYoutubeId(first)
  }, [previewQuery.data, youtubeId])

  const importMutation = useMutation<AddSingleImportResponse, Error, AddSingleImportRequest>({
    mutationFn: (req) => addImport(req),
    onSuccess: (resp) => {
      setJobId(resp.job_id)
    },
  })

  const spotifyPreviewMutation = useMutation({
    mutationFn: () =>
      addPreviewBatch({
        mode: 'spotify',
        spotify_playlist_id: spotifyPlaylistId.trim(),
        skip_existing: spotifySkipExisting,
        recursive: true,
      }),
    onSuccess: (resp) => {
      setSpotifyPreview(resp)
    },
  })

  const spotifyImportMutation = useMutation<SpotifyImportResponse, Error, { playlist_id: string; skip_existing: boolean; initial_status: string }>({
    mutationFn: (req) => addSpotifyImport(req),
    onSuccess: (resp) => {
      setJobId(resp.job_id)
    },
  })

  const nfoPreviewMutation = useMutation({
    mutationFn: () =>
      addPreviewBatch({
        mode: 'nfo',
        nfo_directory: nfoDirectory.trim(),
        recursive: nfoRecursive,
        skip_existing: nfoSkipExisting,
      }),
    onSuccess: (resp) => {
      setNfoPreview(resp)
    },
  })

  const nfoScanMutation = useMutation<NFOScanResponse, Error, { directory: string; mode: 'full' | 'discovery'; recursive: boolean; skip_existing: boolean; update_file_paths: boolean }>({
    mutationFn: (req) => addNFOScan(req),
    onSuccess: (resp) => {
      setJobId(resp.job_id)
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
      // When live updates are connected, don't poll; keep the cached data updated via WS.
      if (jobWs.state === 'connected') return false
      return 1000
    },
  })

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

  useEffect(() => {
    if (!jobId) return
    const wsStatus = jobWs.lastUpdate?.status
    const status = wsStatus ?? jobQuery.data?.status
    if (!status || !isTerminalJobStatus(status)) return
    queryClient.invalidateQueries({ queryKey: videosKeys.all })
  }, [jobId, jobQuery.data?.status, jobWs.lastUpdate?.status, queryClient])

  const results = useMemo(() => {
    const any = searchData as unknown as Record<string, unknown> | null
    const items = any && Array.isArray(any.results) ? (any.results as Array<Record<string, unknown>>) : []
    return items
      .map((r) => {
        const source = safeString(r.source)
        const id = safeString(r.id)
        const title = safeString(r.title)
        const artistName = safeString(r.artist)
        const year = safeNumber(r.year)
        const url = safeString(r.url)
        const thumbnail = safeString(r.thumbnail)
        return source && id ? { source, id, title, artist: artistName, year, url, thumbnail, rawData: r } : null
      })
      .filter((x): x is { source: string; id: string; title: string; artist: string; year: number | null; url: string; thumbnail: string; rawData: Record<string, unknown> } => Boolean(x))
      .sort((a, b) => {
        // IMVDb first, then others
        if (a.source === 'imvdb' && b.source !== 'imvdb') return -1
        if (a.source !== 'imvdb' && b.source === 'imvdb') return 1
        return 0
      })
  }, [searchData])

  const skipped = useMemo(() => {
    const any = searchData as unknown as Record<string, unknown> | null
    const list = any && Array.isArray(any.skipped) ? (any.skipped as Array<Record<string, unknown>>) : []
    return list
      .map((s) => {
        const source = safeString(s.source)
        const reason = safeString(s.reason)
        return source && reason ? { source, reason } : null
      })
      .filter((x): x is { source: string; reason: string } => Boolean(x))
  }, [searchData])

  const canSearch = artist.trim().length > 0 && trackTitle.trim().length > 0

  const viewInLibrarySearch = useMemo(() => {
    const a = artist.trim()
    const t = trackTitle.trim()
    const q = [a, t].filter(Boolean).join(' ').trim()
    return q
  }, [artist, trackTitle])

  const latestJobStatus = (jobWs.lastUpdate?.status ?? jobQuery.data?.status) as unknown
  const canViewInLibrary = latestJobStatus === 'completed' && viewInLibrarySearch.length > 0

  async function onSubmitSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!canSearch || searchMutation.isPending) return
    await searchMutation.mutateAsync()
  }

  async function onSubmitImport() {
    if (!selected) return

    const payload: AddSingleImportRequest = {
      source: selected.source as AddSingleImportRequest['source'],
      id: selected.id,
      initial_status: initialStatus,
      skip_existing: skipExisting,
    }

    if (youtubeId.trim().length > 0) payload.youtube_id = youtubeId.trim()

    await importMutation.mutateAsync(payload)
  }

  const previewDataText = useMemo(() => {
    const data = (previewQuery.data?.data ?? null) as unknown
    if (!data) return ''
    try {
      return JSON.stringify(data, null, 2)
    } catch {
      return String(data)
    }
  }, [previewQuery.data])

  const jobJsonText = useMemo(() => {
    if (jobQuery.data) return JSON.stringify(jobQuery.data as GetJobResponse, null, 2)
    return ''
  }, [jobWs.lastUpdate, jobQuery.data])

  const spotifyPreviewText = useMemo(() => {
    if (!spotifyPreview) return ''
    try {
      return JSON.stringify(spotifyPreview, null, 2)
    } catch {
      return String(spotifyPreview)
    }
  }, [spotifyPreview])

  const nfoPreviewText = useMemo(() => {
    if (!nfoPreview) return ''
    try {
      return JSON.stringify(nfoPreview, null, 2)
    } catch {
      return String(nfoPreview)
    }
  }, [nfoPreview])

  return (
    <div className="addPage">
      <header className="addHeader">
        <h1 className="addTitle">Import Hub</h1>
        <p className="addSubtitle">Search and batch-import into your library.</p>

        <div className="addHeaderLinks">
          <Link className="addButton" to="/library" aria-label="Back to Library">
            Back to Library
          </Link>
        </div>

        <form className="addForm" onSubmit={onSubmitSearch}>
          <input
            className="addInput"
            value={artist}
            onChange={(e) => setArtist(e.target.value)}
            placeholder="Artist"
            aria-label="Artist"
          />
          <input
            className="addInput"
            value={trackTitle}
            onChange={(e) => setTrackTitle(e.target.value)}
            placeholder="Track title"
            aria-label="Track title"
          />
          <button className="addButton" type="submit" disabled={!canSearch || searchMutation.isPending}>
            {searchMutation.isPending ? 'Searching…' : 'Search'}
          </button>
        </form>

        {searchMutation.isError ? <div className="addError">Search failed: {searchMutation.error?.message}</div> : null}
      </header>

      <main className="addMain">
        <section className="addCard" aria-label="Spotify playlist">
          <h2 className="addSectionTitle">Spotify Playlist</h2>

          <div className="addFormRow">
            <label className="addLabel">
              Playlist ID / URL
              <input
                className="addInput"
                value={spotifyPlaylistId}
                onChange={(e) => setSpotifyPlaylistId(e.target.value)}
                placeholder="spotify:playlist:... or https://open.spotify.com/playlist/..."
                aria-label="Spotify playlist id"
              />
            </label>

            <label className="addLabel">
              Initial status
              <select
                className="addSelect"
                value={spotifyInitialStatus}
                onChange={(e) => setSpotifyInitialStatus(e.target.value === 'imported' ? 'imported' : 'discovered')}
                aria-label="Spotify initial status"
              >
                <option value="discovered">discovered</option>
                <option value="imported">imported</option>
              </select>
            </label>

            <label className="addCheckbox">
              <input
                type="checkbox"
                checked={spotifySkipExisting}
                onChange={(e) => setSpotifySkipExisting(e.target.checked)}
              />
              Skip existing
            </label>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
            <button
              className="addButton"
              type="button"
              disabled={spotifyPreviewMutation.isPending || spotifyPlaylistId.trim().length === 0}
              onClick={() => {
                setSpotifyPreview(null)
                void spotifyPreviewMutation.mutateAsync()
              }}
            >
              {spotifyPreviewMutation.isPending ? 'Previewing…' : 'Preview'}
            </button>

            <button
              className="addButton"
              type="button"
              disabled={spotifyImportMutation.isPending || spotifyPlaylistId.trim().length === 0}
              onClick={() =>
                void spotifyImportMutation.mutateAsync({
                  playlist_id: spotifyPlaylistId.trim(),
                  skip_existing: spotifySkipExisting,
                  initial_status: spotifyInitialStatus,
                })
              }
            >
              {spotifyImportMutation.isPending ? 'Submitting…' : 'Submit Import'}
            </button>
          </div>

          {spotifyPreviewMutation.isError ? (
            <div className="addError">Preview failed: {spotifyPreviewMutation.error?.message}</div>
          ) : null}
          {spotifyImportMutation.isError ? (
            <div className="addError">Import submit failed: {spotifyImportMutation.error?.message}</div>
          ) : null}

          {spotifyPreview ? (
            <pre className="addJson" aria-label="Spotify preview JSON">
              {spotifyPreviewText}
            </pre>
          ) : null}
        </section>

        <section className="addCard" aria-label="NFO directory">
          <h2 className="addSectionTitle">NFO Directory</h2>

          <div className="addFormRow">
            <label className="addLabel">
              Directory
              <input
                className="addInput"
                value={nfoDirectory}
                onChange={(e) => setNfoDirectory(e.target.value)}
                placeholder="/path/to/videos"
                aria-label="NFO directory"
              />
            </label>

            <label className="addLabel">
              Mode
              <select
                className="addSelect"
                value={nfoMode}
                onChange={(e) => setNfoMode(e.target.value === 'discovery' ? 'discovery' : 'full')}
                aria-label="NFO mode"
              >
                <option value="full">full</option>
                <option value="discovery">discovery</option>
              </select>
            </label>

            <label className="addCheckbox">
              <input type="checkbox" checked={nfoRecursive} onChange={(e) => setNfoRecursive(e.target.checked)} />
              Recursive
            </label>
          </div>

          <div className="addFormRow" style={{ gridTemplateColumns: '1fr' }}>
            <label className="addCheckbox">
              <input
                type="checkbox"
                checked={nfoSkipExisting}
                onChange={(e) => setNfoSkipExisting(e.target.checked)}
              />
              Skip existing
            </label>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
            <button
              className="addButton"
              type="button"
              disabled={nfoPreviewMutation.isPending || nfoDirectory.trim().length === 0}
              onClick={() => {
                setNfoPreview(null)
                void nfoPreviewMutation.mutateAsync()
              }}
            >
              {nfoPreviewMutation.isPending ? 'Previewing…' : 'Preview'}
            </button>

            <button
              className="addButton"
              type="button"
              disabled={nfoScanMutation.isPending || nfoDirectory.trim().length === 0}
              onClick={() =>
                void nfoScanMutation.mutateAsync({
                  directory: nfoDirectory.trim(),
                  mode: nfoMode,
                  recursive: nfoRecursive,
                  skip_existing: nfoSkipExisting,
                  update_file_paths: true,
                })
              }
            >
              {nfoScanMutation.isPending ? 'Submitting…' : 'Submit Scan'}
            </button>
          </div>

          {nfoPreviewMutation.isError ? <div className="addError">Preview failed: {nfoPreviewMutation.error?.message}</div> : null}
          {nfoScanMutation.isError ? <div className="addError">Scan submit failed: {nfoScanMutation.error?.message}</div> : null}

          {nfoPreview ? (
            <pre className="addJson" aria-label="NFO preview JSON">
              {nfoPreviewText}
            </pre>
          ) : null}
        </section>

        <section className="addCard" aria-label="Search results">
          <h2 className="addSectionTitle">Results</h2>

          {results.length === 0 && !searchMutation.isPending ? <div className="addStatus">No results yet</div> : null}

          {results.length > 0 ? (
            <div className="addResults">
              {results.map((r) => {
                const isSelected = selected?.source === r.source && selected?.id === r.id
                const resultKey = `${r.source}:${r.id}`
                const isExpanded = expandedResults.has(resultKey)
                return (
                  <div key={resultKey} className="addResultWrapper">
                    <button
                      type="button"
                      className={`addResultItem ${isSelected ? 'addResultItemActive' : ''}`}
                      onClick={() => {
                        setSelected({ source: r.source, id: r.id })
                        setJobId(null)
                        setYoutubeId('')
                      }}
                    >
                      {r.thumbnail ? (
                        <div className="addResultThumbnail">
                          <img src={r.thumbnail} alt={r.title} loading="lazy" />
                        </div>
                      ) : null}
                      <div className="addResultContent">
                        <div className="addResultTop">
                          <div className="addResultTitle">{r.title || r.id}</div>
                          <div className="addBadge">{r.source}</div>
                        </div>
                        <div className="addResultMeta">
                          <span>{r.artist || '—'}</span>
                          {r.year ? <span>· {r.year}</span> : null}
                          {r.url ? (
                            <span className="addResultUrl" title={r.url}>
                              · {r.url}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </button>
                    <button
                      type="button"
                      className="addExpandButton"
                      onClick={() => {
                        setExpandedResults((prev) => {
                          const next = new Set(prev)
                          if (next.has(resultKey)) {
                            next.delete(resultKey)
                          } else {
                            next.add(resultKey)
                          }
                          return next
                        })
                      }}
                      aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
                    >
                      {isExpanded ? '▼' : '▶'}
                    </button>
                    {isExpanded ? (
                      <pre className="addResultJson">{JSON.stringify(r.rawData, null, 2)}</pre>
                    ) : null}
                  </div>
                )
              })}
            </div>
          ) : null}

          {skipped.length > 0 ? (
            <div className="addSkipped">
              <h3 className="addSectionTitle">Skipped</h3>
              {skipped.map((s) => (
                <div key={`${s.source}:${s.reason}`} className="addStatus">
                  {s.source}: {s.reason}
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <section className="addCard" aria-label="Preview">
          <h2 className="addSectionTitle">Preview</h2>

          {!selected ? <div className="addStatus">Select a result to preview</div> : null}

          {selected && previewQuery.isLoading ? <div className="addStatus">Loading preview…</div> : null}
          {selected && previewQuery.isError ? <div className="addError">Preview failed</div> : null}

          {selected && previewQuery.data ? (
            <>
              {(() => {
                const extra = previewQuery.data?.extra as unknown
                const thumbnail = extra && typeof extra === 'object' ? (extra as Record<string, unknown>).thumbnail : null
                return thumbnail && typeof thumbnail === 'string' ? (
                  <div className="addPreviewThumbnail">
                    <img src={thumbnail} alt="Preview thumbnail" />
                  </div>
                ) : null
              })()}

              <div className="addFormRow">
                <label className="addLabel">
                  YouTube ID (optional)
                  <input
                    className="addInput"
                    value={youtubeId}
                    onChange={(e) => setYoutubeId(e.target.value)}
                    placeholder="e.g. dQw4w9WgXcQ"
                    aria-label="YouTube ID"
                  />
                </label>

                <label className="addLabel">
                  Initial status
                  <select
                    className="addSelect"
                    value={initialStatus}
                    onChange={(e) => setInitialStatus(e.target.value === 'imported' ? 'imported' : 'discovered')}
                    aria-label="Initial status"
                  >
                    <option value="discovered">discovered</option>
                    <option value="imported">imported</option>
                  </select>
                </label>

                <label className="addCheckbox">
                  <input type="checkbox" checked={skipExisting} onChange={(e) => setSkipExisting(e.target.checked)} />
                  Skip existing
                </label>
              </div>

              <button
                className="addButton"
                type="button"
                disabled={importMutation.isPending}
                onClick={() => void onSubmitImport()}
              >
                {importMutation.isPending ? 'Submitting…' : 'Import'}
              </button>

              {importMutation.isError ? <div className="addError">Import submit failed: {importMutation.error?.message}</div> : null}

              <pre className="addJson" aria-label="Preview JSON">
                {previewDataText}
              </pre>
            </>
          ) : null}
        </section>

        <section className="addCard" aria-label="Job status">
          <h2 className="addSectionTitle">Job</h2>

          {!jobId ? <div className="addStatus">No job submitted</div> : null}

          {jobId && jobWs.state === 'connecting' ? <div className="addStatus">Connecting live updates…</div> : null}
          {jobId && jobWs.state === 'connected' ? <div className="addStatus">Live updates connected</div> : null}
          {jobId && jobWs.state === 'error' ? <div className="addError">Live updates failed{jobWs.lastError ? `: ${jobWs.lastError}` : ''}</div> : null}
          {jobId && jobQuery.isLoading ? <div className="addStatus">Loading job…</div> : null}
          {jobId && jobQuery.isError ? <div className="addError">Job lookup failed</div> : null}

          {jobId && (jobWs.lastUpdate || jobQuery.data) ? (
            <>
              <div className="addStatus">Job ID: {jobId}</div>
              <div className="addStatus">
                Status: <strong>{String(jobWs.lastUpdate?.status ?? jobQuery.data?.status)}</strong>
              </div>
              {jobWs.lastUpdate?.current_step || jobQuery.data?.current_step ? (
                <div className="addStatus">{jobWs.lastUpdate?.current_step ?? jobQuery.data?.current_step}</div>
              ) : null}

              {(() => {
                const result = (jobWs.lastUpdate?.result ?? jobQuery.data?.result) as unknown
                if (!result || typeof result !== 'object') return null
                const resultObj = result as Record<string, unknown>
                const downloadJobId = resultObj.download_job_id
                const organizeJobId = resultObj.organize_job_id
                const nfoJobId = resultObj.nfo_job_id

                return (downloadJobId || organizeJobId || nfoJobId) ? (
                  <div className="addWorkflowProgress">
                    <div className="addStatus">
                      <strong>Workflow Progress:</strong>
                    </div>
                    <div className="addWorkflowSteps">
                      <div className="addWorkflowStep">
                        ✓ Import metadata
                      </div>
                      {downloadJobId ? (
                        <div className="addWorkflowStep">
                          → Download video
                        </div>
                      ) : null}
                      {organizeJobId ? (
                        <div className="addWorkflowStep">
                          → Organize files
                        </div>
                      ) : null}
                      {nfoJobId ? (
                        <div className="addWorkflowStep">
                          → Generate NFO
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null
              })()}

              {canViewInLibrary ? (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <Link
                    className="addButton"
                    to={`/library?search=${encodeURIComponent(viewInLibrarySearch)}`}
                    aria-label="View in Library"
                  >
                    View in Library
                  </Link>
                </div>
              ) : null}

              <pre className="addJson" aria-label="Job JSON">
                {jobJsonText}
              </pre>
            </>
          ) : null}
        </section>
      </main>
    </div>
  )
}
