/* eslint-disable @typescript-eslint/no-explicit-any -- Artist import wizard handles dynamic API responses */
import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  searchArtists,
  previewArtistVideos,
  enrichImvdbVideo,
  importArtistVideos,
} from '../../lib/api/endpoints/add'
import { getJob } from '../../lib/api/endpoints/jobs'
import { jobsKeys, searchKeys, videosKeys } from '../../lib/api/queryKeys'
import { useAuthTokens } from '../../auth/useAuthTokens'
import { useJobEvents } from '../../lib/ws/useJobEvents'
import PageHeader from '../../components/layout/PageHeader'
import MetadataEditor, { type EditedMetadata, extractYouTubeId } from './components/MetadataEditor'
import YouTubeSearchModal from './components/YouTubeSearchModal'
import ArtistVideoTable from './components/ArtistVideoTable'
import type {
  ArtistSearchResultItem,
  ArtistVideoPreviewItem,
  ArtistVideosPreviewResponse,
  ArtistBatchImportResponse,
  GetJobResponse,
} from '../../lib/api/types'
import './SpotifyImport.css' // Reuse Spotify import styles

function isTerminalJobStatus(status: unknown): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

interface VideoMetadataOverride {
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

interface EnrichedVideoData {
  title?: string
  artist?: string
  year?: number | null
  album?: string | null
  label?: string | null
  directors?: string | null
  featuredArtists?: string | null
  youtube_ids?: string[]  // Use snake_case to match backend response
  imvdbUrl?: string | null
  genre?: string | null
  thumbnailUrl?: string | null
  enrichmentStatus?: 'success' | 'partial' | 'not_found'
}

type WizardStep = 'search' | 'select-artist' | 'select-videos' | 'enrich'

export default function ArtistImport() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const tokens = useAuthTokens()

  // Wizard state
  const [step, setStep] = useState<WizardStep>('search')
  const [artistName, setArtistName] = useState('')
  const [artistResults, setArtistResults] = useState<ArtistSearchResultItem[]>([])
  const [selectedArtist, setSelectedArtist] = useState<ArtistSearchResultItem | null>(null)

  // Video selection state
  const [videoPages, setVideoPages] = useState<ArtistVideosPreviewResponse[]>([])
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<number>>(new Set())
  const [loadingMoreVideos, setLoadingMoreVideos] = useState(false)

  // Enrichment state
  const [enrichmentData, setEnrichmentData] = useState<Map<number, EnrichedVideoData>>(new Map())
  const [enrichmentStatus, setEnrichmentStatus] = useState<Map<number, 'pending' | 'loading' | 'done'>>(new Map())
  const [metadataOverrides, setMetadataOverrides] = useState<Map<number, VideoMetadataOverride>>(new Map())

  // Configuration
  const [autoDownload, setAutoDownload] = useState(true)

  // Modal state
  const [editingVideo, setEditingVideo] = useState<{ video: ArtistVideoPreviewItem; enrichment?: EnrichedVideoData } | null>(null)
  const [searchingVideo, setSearchingVideo] = useState<{
    video: ArtistVideoPreviewItem
    artist: string
    trackTitle: string
  } | null>(null)

  // Job state
  const [jobId, setJobId] = useState<string | null>(null)

  // WebSocket job events
  const jobIds = useMemo(() => (jobId ? [jobId] : null), [jobId])
  const { connectionState: wsState, getJob: getJobFromWs } = useJobEvents(tokens.accessToken, {
    jobIds,
    includeActiveState: true,
    autoConnect: Boolean(jobId),
  })
  const wsJobData = jobId ? getJobFromWs(jobId) : null

  // Artist search mutation
  const searchMutation = useMutation({
    mutationFn: () => searchArtists({ artist_name: artistName.trim(), per_page: 25 }),
    onSuccess: (data) => {
      if (data.results.length === 0) {
        toast.error('No artists found', { description: 'Try a different search term' })
        return
      }
      if (data.results.length === 1) {
        // Auto-select if only one result
        handleSelectArtist(data.results[0])
      } else {
        setArtistResults(data.results)
        setStep('select-artist')
      }
    },
    onError: (error: Error) => {
      toast.error('Search failed', { description: error.message })
    },
  })

  // Import mutation
  const importMutation = useMutation<ArtistBatchImportResponse, Error, any>({
    mutationFn: (req) => importArtistVideos(req),
    onSuccess: (resp) => {
      setJobId(resp.job_id)
      toast.success('Import started!', {
        description: `Importing ${resp.video_count} videos. ${resp.auto_download ? 'Downloads will be queued automatically.' : ''}`,
      })
      navigate('/library')
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
          description: `Imported ${result?.imported || 0} videos${downloadJobs > 0 ? `. ${downloadJobs} download jobs queued.` : ''}`,
        })
        queryClient.invalidateQueries({ queryKey: videosKeys.all })
        queryClient.invalidateQueries({ queryKey: searchKeys.all })
        navigate('/library')
      } else if (status === 'failed') {
        toast.error('Import failed', {
          description: jobQuery.data?.error || 'Unknown error',
        })
      }
    }
  }, [jobId, wsJobData?.status, jobQuery.data?.status, jobQuery.data?.result, jobQuery.data?.error, navigate, queryClient])

  // Get all videos from all loaded pages
  const allVideos = useMemo(() => {
    return videoPages.flatMap((page) => page.videos)
  }, [videoPages])

  // Check if there are more videos to load
  const hasMoreVideos = useMemo(() => {
    if (videoPages.length === 0) return false
    const lastPage = videoPages[videoPages.length - 1]
    return lastPage.has_more
  }, [videoPages])

  // Total video count
  const totalVideoCount = useMemo(() => {
    if (videoPages.length === 0) return 0
    return videoPages[0].total_videos
  }, [videoPages])

  // Handle artist selection
  const handleSelectArtist = useCallback(async (artist: ArtistSearchResultItem) => {
    setSelectedArtist(artist)
    setStep('select-videos')

    // Load first page of videos
    try {
      const firstPage = await previewArtistVideos(artist.id, 1, 50)
      setVideoPages([firstPage])

      // Auto-select non-duplicate videos
      const newSelected = new Set<number>()
      firstPage.videos.forEach((v) => {
        if (!v.already_exists) {
          newSelected.add(v.id)
        }
      })
      setSelectedVideoIds(newSelected)

      toast.success(`Found ${firstPage.total_videos} videos`, {
        description: `${firstPage.new_count} new, ${firstPage.existing_count} already in library`,
      })
    } catch (error) {
      toast.error('Failed to load videos', { description: (error as Error).message })
    }
  }, [])

  // Load more videos
  const handleLoadMore = useCallback(async () => {
    if (!selectedArtist || loadingMoreVideos || !hasMoreVideos) return

    const nextPage = videoPages.length + 1
    setLoadingMoreVideos(true)

    try {
      const page = await previewArtistVideos(selectedArtist.id, nextPage, 50)
      setVideoPages((prev) => [...prev, page])

      // Auto-select non-duplicate videos from new page
      page.videos.forEach((v) => {
        if (!v.already_exists) {
          setSelectedVideoIds((prev) => new Set([...prev, v.id]))
        }
      })
    } catch (error) {
      toast.error('Failed to load more videos', { description: (error as Error).message })
    } finally {
      setLoadingMoreVideos(false)
    }
  }, [selectedArtist, loadingMoreVideos, hasMoreVideos, videoPages.length])

  // Handle video selection toggle
  const handleVideoSelect = useCallback((videoId: number, selected: boolean) => {
    setSelectedVideoIds((prev) => {
      const newSet = new Set(prev)
      if (selected) {
        newSet.add(videoId)
      } else {
        newSet.delete(videoId)
      }
      return newSet
    })
  }, [])

  // Proceed to enrichment step
  const handleProceedToEnrich = useCallback(() => {
    if (selectedVideoIds.size === 0) {
      toast.error('Please select at least one video')
      return
    }

    // Initialize enrichment status for selected videos
    const newStatus = new Map<number, 'pending' | 'loading' | 'done'>()
    selectedVideoIds.forEach((id) => {
      newStatus.set(id, 'pending')
    })
    setEnrichmentStatus(newStatus)
    setStep('enrich')
  }, [selectedVideoIds])

  // Sequential enrichment effect
  useEffect(() => {
    if (step !== 'enrich') return

    const runEnrichment = async () => {
      const pendingIds = Array.from(enrichmentStatus.entries())
        .filter(([, status]) => status === 'pending')
        .map(([id]) => id)

      if (pendingIds.length === 0) return

      // Process one at a time (sequential)
      const videoId = pendingIds[0]
      const video = allVideos.find((v) => v.id === videoId)
      if (!video) return

      // Mark as loading
      setEnrichmentStatus((prev) => new Map(prev).set(videoId, 'loading'))

      try {
        const result = await enrichImvdbVideo({
          imvdb_id: video.id,
          artist: selectedArtist?.name || selectedArtist?.slug || 'Unknown',
          track_title: video.song_title || 'Unknown',
          year: video.year,
          thumbnail_url: video.thumbnail_url,
        })

        setEnrichmentData((prev) => {
          const newMap = new Map(prev)
          newMap.set(videoId, {
            title: result.title,
            artist: result.artist,
            year: result.year,
            album: result.album,
            label: result.label,
            directors: result.directors,
            featuredArtists: result.featured_artists,
            youtube_ids: result.youtube_ids,  // Use snake_case to match backend and MetadataEditor
            imvdbUrl: result.imvdb_url,
            genre: result.genre,
            thumbnailUrl: result.thumbnail_url,
            enrichmentStatus: result.enrichment_status,
          })
          return newMap
        })
      } catch (error) {
        console.error('Enrichment failed for video', videoId, error)
        // Set minimal enrichment data from IMVDb
        setEnrichmentData((prev) => {
          const newMap = new Map(prev)
          newMap.set(videoId, {
            title: video.song_title || 'Unknown',
            artist: selectedArtist?.name || selectedArtist?.slug || 'Unknown',
            year: video.year,
            thumbnailUrl: video.thumbnail_url,
            enrichmentStatus: 'not_found',
          })
          return newMap
        })
      }

      setEnrichmentStatus((prev) => new Map(prev).set(videoId, 'done'))
    }

    runEnrichment()
  }, [step, enrichmentStatus, allVideos, selectedArtist])

  // Handle metadata save from editor
  const handleSaveMetadata = (video: ArtistVideoPreviewItem, metadata: EditedMetadata) => {
    const youtubeId = metadata.youtubeUrl ? extractYouTubeId(metadata.youtubeUrl) : null

    setMetadataOverrides((prev) => {
      const newMap = new Map(prev)
      newMap.set(video.id, {
        title: metadata.title,
        artist: metadata.artist,
        isrc: null, // Artist import doesn't have ISRCs
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

    setEditingVideo(null)
    toast.success('Metadata updated')
  }

  // Handle YouTube selection
  const handleYouTubeSelect = (video: ArtistVideoPreviewItem, youtubeId: string) => {
    const enrichment = enrichmentData.get(video.id)

    setMetadataOverrides((prev) => {
      const newMap = new Map(prev)
      const existing = newMap.get(video.id) || {
        title: enrichment?.title ?? video.song_title ?? '',
        artist: enrichment?.artist ?? selectedArtist?.name ?? '',
        isrc: null, // Artist import doesn't have ISRCs
        year: enrichment?.year ?? video.year ?? null,
        album: enrichment?.album ?? null,
        label: enrichment?.label ?? null,
        directors: enrichment?.directors ?? null,
        featuredArtists: enrichment?.featuredArtists ?? null,
        youtubeId: null,
        genre: enrichment?.genre ?? null,
      }
      newMap.set(video.id, { ...existing, youtubeId })
      return newMap
    })

    setSearchingVideo(null)
    toast.success('YouTube video selected')
  }

  // Handle import submission
  const handleImport = () => {
    const selectedVideos = allVideos.filter((v) => selectedVideoIds.has(v.id))

    const videosToImport = selectedVideos.map((video) => {
      const enrichment = enrichmentData.get(video.id)
      const override = metadataOverrides.get(video.id)

      const title = override?.title || enrichment?.title || video.song_title || 'Unknown'
      const artist = override?.artist || enrichment?.artist || selectedArtist?.name || 'Unknown'
      const year = override?.year ?? enrichment?.year ?? video.year
      const album = override?.album ?? enrichment?.album
      const label = override?.label ?? enrichment?.label
      const directors = override?.directors ?? enrichment?.directors
      const featuredArtists = override?.featuredArtists ?? enrichment?.featuredArtists
      const genre = override?.genre ?? enrichment?.genre

      const youtubeId =
        override?.youtubeId ||
        (enrichment?.youtube_ids && enrichment.youtube_ids.length > 0 ? enrichment.youtube_ids[0] : null)

      return {
        imvdb_id: video.id,
        metadata: {
          title,
          artist,
          year,
          album,
          label,
          directors,
          featured_artists: featuredArtists,
          genre,
        },
        imvdb_url: enrichment?.imvdbUrl,
        youtube_id: youtubeId,
        youtube_url: youtubeId ? `https://youtube.com/watch?v=${youtubeId}` : null,
        thumbnail_url: enrichment?.thumbnailUrl || video.thumbnail_url,
      }
    })

    importMutation.mutate({
      entity_id: selectedArtist?.id,
      entity_name: selectedArtist?.name || selectedArtist?.slug,
      videos: videosToImport,
      initial_status: 'discovered',
      auto_download: autoDownload,
    })
  }

  // Handle search form submit
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!artistName.trim()) {
      toast.error('Please enter an artist name')
      return
    }
    searchMutation.mutate()
  }

  // Reset wizard
  const handleStartOver = () => {
    setStep('search')
    setArtistName('')
    setArtistResults([])
    setSelectedArtist(null)
    setVideoPages([])
    setSelectedVideoIds(new Set())
    setEnrichmentData(new Map())
    setEnrichmentStatus(new Map())
    setMetadataOverrides(new Map())
    setJobId(null)
  }

  // Get job progress info
  const latestJobStatus = wsJobData?.status ?? jobQuery.data?.status ?? 'pending'
  const progress = wsJobData?.progress ?? jobQuery.data?.progress
  const currentStep = wsJobData?.current_step ?? jobQuery.data?.current_step

  return (
    <div className="spotifyImport">
      <PageHeader
        title="Artist Video Import"
        iconSrc="/fuzzbin-icon.png"
        iconAlt="Fuzzbin"
        accent="var(--channel-import)"
        navItems={[
          { label: 'Library', to: '/library' },
          { label: 'Import', to: '/import' },
          { label: 'Activity', to: '/activity' },
          { label: 'Settings', to: '/settings' },
        ]}
        subNavLabel="Import workflows"
        subNavItems={[
          { label: 'Search', to: '/import', end: true },
          { label: 'Spotify Playlist', to: '/import/spotify' },
          { label: 'Artist Videos', to: '/import/artist' },
          { label: 'NFO Scan', to: '/import/nfo' },
        ]}
      />

      <div className="spotifyImportContent">
        {/* Step 1: Search */}
        {step === 'search' && (
          <div className="spotifyImportCard">
            <h2 className="spotifyImportCardTitle">Search for Artist</h2>

            <form onSubmit={handleSearch} className="spotifyImportForm">
              <div className="spotifyImportFormGroup">
                <label className="spotifyImportLabel">Artist Name</label>
                <input
                  type="text"
                  className="spotifyImportInput"
                  value={artistName}
                  onChange={(e) => setArtistName(e.target.value)}
                  placeholder="Enter artist name to search IMVDb"
                />
              </div>

              <button
                type="submit"
                className="spotifyImportButtonPrimary"
                disabled={searchMutation.isPending || !artistName.trim()}
              >
                {searchMutation.isPending ? 'Searching...' : 'Search Artists'}
              </button>
            </form>
          </div>
        )}

        {/* Step 2: Select Artist (disambiguation) */}
        {step === 'select-artist' && (
          <div className="spotifyImportCard">
            <h2 className="spotifyImportCardTitle">Select Artist</h2>
            <p className="spotifyImportDescription">
              Found {artistResults.length} artists matching "{artistName}". Select one to view their videos.
            </p>

            <div className="artistResultsGrid">
              {artistResults.map((artist) => (
                <div
                  key={artist.id}
                  className="artistResultCard"
                  onClick={() => handleSelectArtist(artist)}
                >
                  {artist.image && artist.image !== 'https://imvdb.com/' && (
                    <img src={artist.image} alt={artist.name || artist.slug || ''} className="artistResultImage" />
                  )}
                  <div className="artistResultInfo">
                    <div className="artistResultName">{artist.name || artist.slug}</div>
                    <div className="artistResultVideoCount">{artist.artist_video_count} videos</div>
                    {artist.sample_tracks && artist.sample_tracks.length > 0 && (
                      <div className="artistResultSampleTracks">
                        {artist.sample_tracks.map((track: string, idx: number) => (
                          <div key={idx} className="artistResultTrack">
                            • {track}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <button type="button" className="spotifyImportButton" onClick={handleStartOver}>
              Back to Search
            </button>
          </div>
        )}

        {/* Step 3: Select Videos */}
        {step === 'select-videos' && selectedArtist && (
          <>
            <div className="spotifyImportCard">
              <h2 className="spotifyImportCardTitle">
                {selectedArtist.name || selectedArtist.slug} - Select Videos
              </h2>
              <div className="videoSelectionHeader">
                <p className="spotifyImportDescription">
                  Showing {allVideos.length} of {totalVideoCount} videos.
                  Selected: {selectedVideoIds.size}
                </p>
                <div className="videoSelectionActions">
                  <button
                    type="button"
                    className="videoSelectionActionButton"
                    onClick={() => {
                      const selectableVideos = allVideos.filter(v => !v.already_exists)
                      const newSelected = new Set<number>()
                      selectableVideos.forEach(v => newSelected.add(v.id))
                      setSelectedVideoIds(newSelected)
                    }}
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    className="videoSelectionActionButton"
                    onClick={() => setSelectedVideoIds(new Set())}
                  >
                    Select None
                  </button>
                </div>
              </div>

              <div className="videoSelectionGrid">
                {allVideos.map((video) => (
                  <div
                    key={video.id}
                    className={`videoSelectionCard ${selectedVideoIds.has(video.id) ? 'selected' : ''} ${video.already_exists ? 'exists' : ''}`}
                    onClick={() => !video.already_exists && handleVideoSelect(video.id, !selectedVideoIds.has(video.id))}
                  >
                    <div className="videoSelectionCheckbox">
                      <input
                        type="checkbox"
                        checked={selectedVideoIds.has(video.id)}
                        onChange={(e) => {
                          e.stopPropagation()
                          handleVideoSelect(video.id, e.target.checked)
                        }}
                        disabled={video.already_exists}
                      />
                    </div>
                    {video.thumbnail_url ? (
                      <img
                        src={video.thumbnail_url}
                        alt={video.song_title || 'Video thumbnail'}
                        className="videoSelectionThumbnail"
                      />
                    ) : (
                      <div className="videoSelectionNoThumbnail">No Image</div>
                    )}
                    <div className="videoSelectionInfo">
                      <div className="videoSelectionTitle">{video.song_title || 'Unknown'}</div>
                      {video.year && <div className="videoSelectionYear">{video.year}</div>}
                      {video.already_exists && (
                        <div className="videoSelectionDupeBadge">Already in library</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {hasMoreVideos && (
                <button
                  type="button"
                  className="spotifyImportButton"
                  onClick={handleLoadMore}
                  disabled={loadingMoreVideos}
                >
                  {loadingMoreVideos ? 'Loading...' : 'Load More Videos'}
                </button>
              )}
            </div>

            <div className="spotifyImportCard">
              <div className="spotifyImportActions">
                <button type="button" className="spotifyImportButton" onClick={handleStartOver}>
                  Start Over
                </button>
                <button
                  type="button"
                  className="spotifyImportButtonPrimary"
                  onClick={handleProceedToEnrich}
                  disabled={selectedVideoIds.size === 0}
                >
                  Continue with {selectedVideoIds.size} Videos
                </button>
              </div>
            </div>
          </>
        )}

        {/* Step 4: Enrichment Table */}
        {step === 'enrich' && selectedArtist && (
          <>
            <div className="spotifyImportCard">
              <h2 className="spotifyImportCardTitle">Enrich & Review</h2>

              <div className="spotifyImportFormGroup">
                <label className="spotifyImportCheckbox">
                  <input
                    type="checkbox"
                    checked={autoDownload}
                    onChange={(e) => setAutoDownload(e.target.checked)}
                  />
                  <span>Auto-download videos after import</span>
                </label>
              </div>

              <ArtistVideoTable
                videos={allVideos.filter((v) => selectedVideoIds.has(v.id))}
                artistName={selectedArtist.name || selectedArtist.slug || ''}
                metadataOverrides={metadataOverrides}
                onEnrichmentComplete={(video: any, enrichment: any) => {
                  setEnrichmentData((prev) => {
                    const newMap = new Map(prev)
                    newMap.set(video.id, enrichment)
                    return newMap
                  })
                  setEnrichmentStatus((prev) => {
                    const newMap = new Map(prev)
                    newMap.set(video.id, 'done')
                    return newMap
                  })
                }}
                onEditVideo={(video: any, state: any) => {
                  setEditingVideo({ video, enrichment: state.enrichmentData })
                }}
                onSearchYouTube={(video: any, artist: string, trackTitle: string) => {
                  setSearchingVideo({ video, artist, trackTitle })
                }}
                onSelectionChange={(selectedIds: Set<number>) => {
                  setSelectedVideoIds(selectedIds)
                }}
                onPreviewYouTube={(youtubeId: string) => {
                  window.open(`https://www.youtube.com/watch?v=${youtubeId}`, '_blank')
                }}
              />
            </div>

            <div className="spotifyImportCard">
              <div className="spotifyImportActions">
                <button type="button" className="spotifyImportButton" onClick={() => setStep('select-videos')}>
                  Back
                </button>
                <button
                  type="button"
                  className="spotifyImportButtonPrimary"
                  onClick={handleImport}
                  disabled={importMutation.isPending || Array.from(enrichmentStatus.values()).some((s) => s !== 'done')}
                >
                  {importMutation.isPending
                    ? 'Importing...'
                    : `Import ${selectedVideoIds.size} Videos`}
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
                <span className={`spotifyImportJobStatusBadge spotifyImportJobStatusBadge${latestJobStatus}`}>
                  {latestJobStatus}
                </span>
                <span className="spotifyImportJobId">Job ID: {jobId}</span>
              </div>

              {currentStep && <div className="spotifyImportJobStep">{currentStep}</div>}

              {typeof progress === 'number' && (
                <div className="spotifyImportJobProgress">
                  <div className="spotifyImportJobProgressBar" style={{ width: `${progress * 100}%` }} />
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
      {editingVideo && (
        <MetadataEditor
          track={{
            title: editingVideo.video.song_title || '',
            artist: selectedArtist?.name || selectedArtist?.slug || '',
            album: editingVideo.enrichment?.album || null,
            year: editingVideo.enrichment?.year ?? editingVideo.video.year ?? null,
            label: editingVideo.enrichment?.label || null,
            isrc: null,
            already_exists: editingVideo.video.already_exists,
            kind: 'imvdb',
          }}
          state={{
            enrichmentStatus: 'success',
            enrichmentData: {
              title: editingVideo.enrichment?.title || editingVideo.video.song_title || '',
              artist: editingVideo.enrichment?.artist || selectedArtist?.name || '',
              year: editingVideo.enrichment?.year ?? editingVideo.video.year,
              album: editingVideo.enrichment?.album,
              label: editingVideo.enrichment?.label,
              directors: editingVideo.enrichment?.directors,
              featured_artists: editingVideo.enrichment?.featuredArtists,
              youtube_ids: editingVideo.enrichment?.youtube_ids || [],
              genre: editingVideo.enrichment?.genre,
              thumbnail_url: editingVideo.enrichment?.thumbnailUrl || editingVideo.video.thumbnail_url,
            } as any,
            selected: true,
          }}
          currentOverride={metadataOverrides.get(editingVideo.video.id)}
          onSave={(metadata) => handleSaveMetadata(editingVideo.video, metadata)}
          onCancel={() => setEditingVideo(null)}
          showSpotifyColumn={false}
        />
      )}

      {searchingVideo && (
        <YouTubeSearchModal
          artist={searchingVideo.artist}
          trackTitle={searchingVideo.trackTitle}
          onSelect={(youtubeId) => handleYouTubeSelect(searchingVideo.video, youtubeId)}
          onCancel={() => setSearchingVideo(null)}
        />
      )}

      <style>{`
        .artistResultsGrid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: 1rem;
          margin-bottom: 1rem;
        }

        .artistResultCard {
          background: var(--bg-secondary);
          border: 2px solid var(--border);
          border-radius: 8px;
          padding: 1rem;
          cursor: pointer;
          transition: all 0.2s;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .artistResultCard:hover {
          border-color: var(--channel-import);
          background: var(--bg-tertiary);
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
          transform: translateY(-2px);
        }

        .artistResultImage {
          width: 100%;
          aspect-ratio: 1;
          object-fit: cover;
          border-radius: 4px;
          margin-bottom: 0.5rem;
        }

        .artistResultName {
          font-weight: 600;
          color: var(--text-primary);
        }

        .artistResultVideoCount {
          font-size: 0.875rem;
          color: var(--text-secondary);
          margin-top: 0.25rem;
        }

        .artistResultSampleTracks {
          margin-top: 0.5rem;
          padding-top: 0.5rem;
          border-top: 1px solid var(--border);
        }

        .artistResultTrack {
          font-size: 0.75rem;
          color: var(--text-tertiary);
          margin-top: 0.25rem;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .videoSelectionHeader {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1rem;
        }

        .videoSelectionActions {
          display: flex;
          gap: 0.5rem;
        }

        .videoSelectionActionButton {
          padding: 0.5rem 1rem;
          font-size: 0.875rem;
          border: 1px solid var(--border);
          border-radius: 4px;
          background: var(--bg-tertiary);
          color: var(--text-primary);
          cursor: pointer;
          transition: all 0.2s;
        }

        .videoSelectionActionButton:hover {
          background: var(--bg-secondary);
          border-color: var(--channel-import);
          color: var(--channel-import);
        }

        .videoSelectionGrid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: 1rem;
          margin-bottom: 1rem;
        }

        .videoSelectionCard {
          background: var(--bg-secondary);
          border: 2px solid var(--border);
          border-radius: 8px;
          overflow: hidden;
          cursor: pointer;
          transition: all 0.2s;
          position: relative;
        }

        .videoSelectionCard.selected {
          border-color: var(--channel-import);
        }

        .videoSelectionCard.exists {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .videoSelectionCheckbox {
          position: absolute;
          top: 0.5rem;
          left: 0.5rem;
          z-index: 1;
        }

        .videoSelectionCheckbox input {
          width: 20px;
          height: 20px;
        }

        .videoSelectionThumbnail {
          width: 100%;
          aspect-ratio: 16/9;
          object-fit: cover;
        }

        .videoSelectionNoThumbnail {
          width: 100%;
          aspect-ratio: 16/9;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary);
          font-size: 0.75rem;
        }

        .videoSelectionInfo {
          padding: 0.5rem;
        }

        .videoSelectionTitle {
          font-weight: 500;
          font-size: 0.875rem;
          color: var(--text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .videoSelectionYear {
          font-size: 0.75rem;
          color: var(--text-secondary);
        }

        .videoSelectionDupeBadge {
          font-size: 0.75rem;
          color: var(--text-warning);
          font-style: italic;
        }

        .spotifyImportDescription {
          color: var(--text-secondary);
          margin-bottom: 1rem;
        }
      `}</style>
    </div>
  )
}
