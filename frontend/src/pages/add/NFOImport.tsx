import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { addPreviewBatch, addNFOScan } from '../../lib/api/endpoints/add'
import { getJob } from '../../lib/api/endpoints/jobs'
import { jobsKeys, videosKeys } from '../../lib/api/queryKeys'
import { useAuthTokens } from '../../auth/useAuthTokens'
import { useJobWebSocket } from '../../lib/ws/useJobWebSocket'
import type { BatchPreviewResponse, NFOScanResponse, GetJobResponse } from '../../lib/api/types'
import './NFOImport.css'

function isTerminalJobStatus(status: unknown): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

export default function NFOImport() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const tokens = useAuthTokens()

  const [directory, setDirectory] = useState('')
  const [mode, setMode] = useState<'full' | 'discovery'>('full')
  const [recursive, setRecursive] = useState(true)
  const [skipExisting, setSkipExisting] = useState(true)
  const [preview, setPreview] = useState<BatchPreviewResponse | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)

  const jobWs = useJobWebSocket(jobId, tokens.accessToken)

  const previewMutation = useMutation({
    mutationFn: () =>
      addPreviewBatch({
        mode: 'nfo',
        nfo_directory: directory.trim(),
        recursive: recursive,
        skip_existing: skipExisting,
      }),
    onSuccess: (data) => {
      setPreview(data)
      toast.success('Preview loaded', {
        description: `Found ${data.total_count} NFO files (${data.new_count} new, ${data.existing_count} existing)`,
      })
    },
    onError: (error: Error) => {
      toast.error('Preview failed', { description: error.message })
    },
  })

  const importMutation = useMutation<NFOScanResponse, Error, { directory: string; mode: 'full' | 'discovery'; recursive: boolean; skip_existing: boolean; update_file_paths: boolean }>({
    mutationFn: (req) => addNFOScan(req),
    onSuccess: (resp) => {
      setJobId(resp.job_id)
      toast.success('Scan started!', {
        description: `Job ID: ${resp.job_id}`,
      })
    },
    onError: (error: Error) => {
      toast.error('Scan failed', { description: error.message })
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
      toast.success('Scan completed!', {
        action: {
          label: 'View Library',
          onClick: () => navigate('/library'),
        },
      })
    } else if (status === 'failed') {
      toast.error('Scan failed', {
        description: jobQuery.data?.error || 'Unknown error',
      })
    }

    queryClient.invalidateQueries({ queryKey: videosKeys.all })
  }, [jobId, jobQuery.data?.status, jobWs.lastUpdate?.status, queryClient, navigate])

  const handlePreview = (e: React.FormEvent) => {
    e.preventDefault()
    if (!directory.trim()) {
      toast.error('Please enter a directory path')
      return
    }
    previewMutation.mutate()
  }

  const handleScan = () => {
    if (!directory.trim()) {
      toast.error('Please enter a directory path')
      return
    }

    importMutation.mutate({
      directory: directory.trim(),
      mode: mode,
      recursive: recursive,
      skip_existing: skipExisting,
      update_file_paths: false,
    })
  }

  const latestJobStatus = (jobWs.lastUpdate?.status ?? jobQuery.data?.status) as string | undefined
  const progress = jobWs.lastUpdate?.progress ?? jobQuery.data?.progress ?? 0
  const currentStep = jobWs.lastUpdate?.current_step ?? jobQuery.data?.current_step

  return (
    <div className="nfoImport">
      <div className="nfoImportHeader">
        <h1 className="nfoImportTitle">NFO Directory Scan</h1>
        <Link to="/add" className="nfoImportBackLink">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Back to Hub
        </Link>
      </div>

      <div className="nfoImportContent">
        <div className="nfoImportCard">
          <h2 className="nfoImportCardTitle">Scan Configuration</h2>

          <form onSubmit={handlePreview} className="nfoImportForm">
            <div className="nfoImportFormGroup">
              <label className="nfoImportLabel">Directory Path</label>
              <input
                type="text"
                className="nfoImportInput"
                value={directory}
                onChange={(e) => setDirectory(e.target.value)}
                placeholder="Enter directory path (e.g., /path/to/videos)"
              />
            </div>

            <div className="nfoImportFormGroup">
              <label className="nfoImportLabel">Scan Mode</label>
              <select
                className="nfoImportSelect"
                value={mode}
                onChange={(e) => setMode(e.target.value as 'full' | 'discovery')}
              >
                <option value="full">Full</option>
                <option value="discovery">Discovery</option>
              </select>
              <p className="nfoImportHint">
                Full mode imports all metadata. Discovery mode creates records without downloading.
              </p>
            </div>

            <div className="nfoImportFormGroup">
              <label className="nfoImportCheckbox">
                <input
                  type="checkbox"
                  checked={recursive}
                  onChange={(e) => setRecursive(e.target.checked)}
                />
                <span>Scan subdirectories recursively</span>
              </label>
            </div>

            <div className="nfoImportFormGroup">
              <label className="nfoImportCheckbox">
                <input
                  type="checkbox"
                  checked={skipExisting}
                  onChange={(e) => setSkipExisting(e.target.checked)}
                />
                <span>Skip existing items</span>
              </label>
            </div>

            <div className="nfoImportActions">
              <button
                type="submit"
                className="nfoImportButton"
                disabled={previewMutation.isPending}
              >
                {previewMutation.isPending ? 'Loading...' : 'Preview'}
              </button>
              <button
                type="button"
                className="nfoImportButtonPrimary"
                onClick={handleScan}
                disabled={importMutation.isPending || !directory.trim()}
              >
                {importMutation.isPending ? 'Scanning...' : 'Scan & Import'}
              </button>
            </div>
          </form>
        </div>

        {/* Preview Results */}
        {preview && (
          <div className="nfoImportCard">
            <h2 className="nfoImportCardTitle">Preview</h2>
            <div className="nfoImportStats">
              <div className="nfoImportStat">
                <div className="nfoImportStatValue">{preview.total_count}</div>
                <div className="nfoImportStatLabel">Total NFO Files</div>
              </div>
              <div className="nfoImportStat">
                <div className="nfoImportStatValue">{preview.new_count}</div>
                <div className="nfoImportStatLabel">New</div>
              </div>
              <div className="nfoImportStat">
                <div className="nfoImportStatValue">{preview.existing_count}</div>
                <div className="nfoImportStatLabel">Existing</div>
              </div>
            </div>

            {preview.items && preview.items.length > 0 && (
              <div className="nfoImportPreviewList">
                <h3 className="nfoImportPreviewTitle">NFO Files (showing first 100)</h3>
                {preview.items.slice(0, 100).map((item, index) => (
                  <div key={index} className={`nfoImportPreviewItem ${item.already_exists ? 'nfoImportPreviewItemExists' : ''}`}>
                    <div className="nfoImportPreviewItemInfo">
                      <div className="nfoImportPreviewItemTitle">{item.title}</div>
                      <div className="nfoImportPreviewItemArtist">{item.artist}</div>
                      {item.nfo_path && (
                        <div className="nfoImportPreviewItemPath">{item.nfo_path}</div>
                      )}
                    </div>
                    {item.already_exists && (
                      <span className="nfoImportPreviewItemBadge">Exists</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Job Progress */}
        {jobId && (
          <div className="nfoImportCard">
            <h2 className="nfoImportCardTitle">Scan Progress</h2>
            <div className="nfoImportJobStatus">
              <div className="nfoImportJobStatusHeader">
                <span className={`nfoImportJobStatusBadge nfoImportJobStatusBadge${latestJobStatus}`}>
                  {latestJobStatus}
                </span>
                <span className="nfoImportJobId">Job ID: {jobId}</span>
              </div>

              {currentStep && (
                <div className="nfoImportJobStep">{currentStep}</div>
              )}

              {typeof progress === 'number' && (
                <div className="nfoImportJobProgress">
                  <div className="nfoImportJobProgressBar" style={{ width: `${progress * 100}%` }} />
                </div>
              )}

              {jobWs.state === 'connected' && (
                <div className="nfoImportJobLive">Live updates connected</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
