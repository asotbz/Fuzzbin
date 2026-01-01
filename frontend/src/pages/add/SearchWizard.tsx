/* eslint-disable @typescript-eslint/no-explicit-any -- Wizard handles dynamic API responses */
import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { addSearch, addPreview, addImport, checkVideoExists, getYouTubeMetadata } from '../../lib/api/endpoints/add'
import { addKeys } from '../../lib/api/queryKeys'
import { useSearchWizard } from '../../hooks/add/useSearchWizard'
import WizardStepper from '../../components/add/wizard/WizardStepper'
import SourceComparison, { type ComparisonField } from '../../components/add/metadata/SourceComparison'
import type { AddSingleImportRequest } from '../../lib/api/types'
import './SearchWizard.css'

const STEPS = ['Search', 'Select', 'Edit', 'Submit']

export default function SearchWizard() {
  const navigate = useNavigate()
  const wizard = useSearchWizard()
  const [artist, setArtist] = useState('')
  const [trackTitle, setTrackTitle] = useState('')
  const [discogsResults, setDiscogsResults] = useState<any>(null)
  const [selectedDiscogsFields, setSelectedDiscogsFields] = useState<Record<string, 'imvdb' | 'discogs'>>({})
  const [showYouTubeSearch, setShowYouTubeSearch] = useState(false)
  const [youtubeSearchResults, setYoutubeSearchResults] = useState<any>(null)

  // Initialize local form state from wizard state (if returning to earlier step)
  useEffect(() => {
    if (wizard.searchQuery.artist) {
       
      setArtist(wizard.searchQuery.artist)
    }
    if (wizard.searchQuery.trackTitle) {
       
      setTrackTitle(wizard.searchQuery.trackTitle)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Only run on mount
  }, [])

  // Reset wizard on unmount to ensure clean state for next visit
  useEffect(() => {
    return () => {
      // Cleanup: reset wizard when component unmounts
      wizard.resetWizard()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Only run on unmount
  }, [])

  // Step 1: Search mutation
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
      wizard.setSearchResults(data)
      wizard.setSearchQuery(artist, trackTitle)
      wizard.nextStep()
    },
    onError: (error: Error) => {
      toast.error('Search failed', { description: error.message })
    },
  })

  // Step 2-3: Preview query
  const previewQuery = useQuery({
    queryKey: wizard.selectedSource
      ? addKeys.preview(wizard.selectedSource.source, wizard.selectedSource.id)
      : addKeys.preview('none', 'none'),
    enabled: Boolean(wizard.selectedSource),
    queryFn: async () => {
      if (!wizard.selectedSource) throw new Error('No selection')
      const data = await addPreview(wizard.selectedSource.source, wizard.selectedSource.id)
      wizard.setPreviewData(data)

      // If IMVDb source, automatically fetch Discogs data to fill in gaps
      let discogsData = null
      if (wizard.selectedSource.source === 'imvdb') {
        try {
          const results = await addSearch({
            artist: wizard.searchQuery.artist,
            track_title: wizard.searchQuery.trackTitle,
            include_sources: ['discogs_master', 'discogs_release'],
            imvdb_per_page: 1,
            discogs_per_page: 10,
            youtube_max_results: 1,
          })

          if (results.results && results.results.length > 0) {
            const firstResult = results.results[0]

            // If master, fetch the main release for detailed data
            if (firstResult.source === 'discogs_master') {
              const masterPreview = await addPreview(firstResult.source, firstResult.id)
              const masterData = masterPreview.data as any

              if (masterData.main_release) {
                const releasePreview = await addPreview('discogs_release', masterData.main_release.toString())
                discogsData = releasePreview.data
                // Store for comparison UI
                setDiscogsResults({
                  ...results,
                  results: [{
                    ...firstResult,
                    source: 'discogs_release',
                    id: masterData.main_release.toString(),
                    data: releasePreview.data,
                  }]
                })
              } else {
                discogsData = masterPreview.data
                setDiscogsResults(results)
              }
            } else {
              // Direct release result
              const releasePreview = await addPreview(firstResult.source, firstResult.id)
              discogsData = releasePreview.data
              setDiscogsResults(results)
            }
          }
        } catch (error) {
          console.warn('Could not fetch Discogs data for enrichment:', error)
        }
      }

      // Auto-populate metadata from preview (with Discogs enrichment if available)
      populateMetadataFromPreview(data, discogsData)

      return data
    },
  })

  // Populate metadata from preview data (and merge with Discogs if available)
  const populateMetadataFromPreview = (data: any, discogsData?: any) => {
    const videoData = data.data as any
    const extra = data.extra as any

    let title = ''
    let artist = ''
    let year: number | null = null
    let album: string | null = null
    let directors: string | null = null
    let label: string | null = null
    let youtubeId: string | null = null

    // Extract based on source
    if (wizard.selectedSource?.source === 'imvdb') {
      // IMVDb data (preferred for fields that exist in both)
      title = videoData.song_title || ''
      artist = videoData.artists?.[0]?.name || ''
      year = videoData.year || null
      album = videoData.album || null

      // Extract directors (IMVDb only)
      if (videoData.directors && Array.isArray(videoData.directors)) {
        directors = videoData.directors.map((d: any) => d.entity_name).filter(Boolean).join(', ')
      }

      // Extract YouTube IDs from extra.youtube_ids (IMVDb only)
      if (extra?.youtube_ids && Array.isArray(extra.youtube_ids) && extra.youtube_ids.length > 0) {
        youtubeId = extra.youtube_ids[0]
        // Store all available YouTube sources
        wizard.setAvailableYouTubeSources(extra.youtube_ids)
        // Check availability of first YouTube ID
        checkYouTubeAvailability(extra.youtube_ids[0])
      }

      // Fill in missing data from Discogs if available
      if (discogsData) {
        // If IMVDb doesn't have album, use Discogs title
        if (!album && discogsData.title) {
          album = discogsData.title
        }

        // Always use Discogs label (IMVDb doesn't have this)
        // Take only the first label (parent/main label, not imprints)
        if (discogsData.labels && Array.isArray(discogsData.labels) && discogsData.labels.length > 0) {
          label = discogsData.labels[0].name || null
        }
      }
    } else if (wizard.selectedSource?.source.startsWith('discogs')) {
      title = videoData.title || ''

      // Extract artist from artists array
      if (videoData.artists && Array.isArray(videoData.artists)) {
        artist = videoData.artists.map((a: any) => a.name).join(', ')
      }

      year = videoData.year || null

      // Extract label from labels array (first label is parent/main label)
      if (videoData.labels && Array.isArray(videoData.labels) && videoData.labels.length > 0) {
        label = videoData.labels[0].name || null
      }
    } else if (wizard.selectedSource?.source === 'youtube') {
      title = videoData.title || ''
      artist = videoData.channel || ''
      youtubeId = videoData.id || wizard.selectedSource.id
      // Check availability
      if (youtubeId) {
        checkYouTubeAvailability(youtubeId)
      }
    }

    wizard.setMetadata({
      title,
      artist,
      year,
      album,
      directors,
      label,
      youtubeId,
      initialStatus: 'discovered',
      skipExisting: true,
      autoDownload: true,  // Default to auto-download enabled
    })
  }

  // Check YouTube video availability
  const checkYouTubeAvailability = async (youtubeId: string) => {
    try {
      const response = await getYouTubeMetadata({ youtube_id: youtubeId })
      wizard.setYouTubeSourceInfo({
        youtube_id: response.youtube_id,
        available: response.available,
        view_count: response.view_count,
        duration: response.duration,
        channel: response.channel,
        title: response.title,
        error: response.error,
      })
    } catch (error) {
      console.error('Failed to check YouTube availability:', error)
      wizard.setYouTubeSourceInfo({
        youtube_id: youtubeId,
        available: false,
        view_count: null,
        duration: null,
        channel: null,
        title: null,
        error: 'Failed to check availability',
      })
    }
  }

  // Step 4: Import mutation
  const importMutation = useMutation({
    mutationFn: (request: AddSingleImportRequest) => addImport(request),
    onSuccess: (data) => {
      toast.success('Import started!', {
        description: `Job ID: ${data.job_id}`,
        duration: 5000,
      })
      // Navigate back to library after submission
      navigate('/library')
    },
    onError: (error: Error) => {
      toast.error('Import failed', { description: error.message })
    },
  })

  // YouTube search mutation
  const youtubeSearchMutation = useMutation({
    mutationFn: () =>
      addSearch({
        artist: wizard.editedMetadata.artist,
        track_title: wizard.editedMetadata.title,
        include_sources: ['youtube'],
        imvdb_per_page: 1,
        discogs_per_page: 1,
        youtube_max_results: 10,
      }),
    onSuccess: (data) => {
      setYoutubeSearchResults(data)
      setShowYouTubeSearch(true)
    },
    onError: (error: Error) => {
      toast.error('YouTube search failed', { description: error.message })
    },
  })

  // Initialize selected fields when Discogs data is loaded
  useEffect(() => {
    if (discogsResults && discogsResults.results?.length > 0 && wizard.previewData) {
      const discogsData = discogsResults.results[0]?.data || {}
      const imvdbData = wizard.previewData?.data as any || {}

      // Automatically select the source that has data for each field
      const selections: Record<string, 'imvdb' | 'discogs'> = {}

      // Title
      const imvdbTitle = imvdbData.song_title || null
      const discogsTitle = discogsData.title || null
      if (imvdbTitle && !discogsTitle) {
        selections.title = 'imvdb'
      } else if (!imvdbTitle && discogsTitle) {
        selections.title = 'discogs'
      } else {
        // Both have data or both don't - prefer IMVDb
        selections.title = 'imvdb'
      }

      // Artist
      const imvdbArtist = imvdbData.artists?.[0]?.name || null
      const discogsArtist = discogsData.artists?.map((a: any) => a.name).join(', ') || null
      if (imvdbArtist && !discogsArtist) {
        selections.artist = 'imvdb'
      } else if (!imvdbArtist && discogsArtist) {
        selections.artist = 'discogs'
      } else {
        selections.artist = 'imvdb'
      }

      // Year
      const imvdbYear = imvdbData.year || null
      const discogsYear = discogsData.year || null
      if (imvdbYear && !discogsYear) {
        selections.year = 'imvdb'
      } else if (!imvdbYear && discogsYear) {
        selections.year = 'discogs'
      } else {
        selections.year = 'imvdb'
      }

       
      setSelectedDiscogsFields(selections)
    }
  }, [discogsResults, wizard.previewData])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!artist.trim() || !trackTitle.trim()) {
      toast.error('Please enter both artist and track title')
      return
    }
    searchMutation.mutate()
  }

  const handleSelectResult = async (source: string, id: string) => {
    // Check if video already exists in library
    try {
      const checkParams: { imvdb_id?: string; youtube_id?: string } = {}

      if (source === 'imvdb') {
        checkParams.imvdb_id = id
      } else if (source === 'youtube') {
        checkParams.youtube_id = id
      }

      // Only check for IMVDb and YouTube sources
      if (checkParams.imvdb_id || checkParams.youtube_id) {
        const existsResult = await checkVideoExists(checkParams)

        if (existsResult.exists) {
          toast.warning('Video already exists in library', {
            description: `${existsResult.title || 'Unknown title'} by ${existsResult.artist || 'Unknown artist'}`,
            duration: 8000,
          })
        }
      }
    } catch (error) {
      // Don't block selection if check fails
      console.error('Failed to check if video exists:', error)
    }

    wizard.selectSource(source, id)
    wizard.nextStep()
  }

  const handleImportSubmit = () => {
    if (!wizard.selectedSource) {
      toast.error('No source selected')
      return
    }

    // Build pre-fetched metadata from wizard state and preview data
    // This allows the backend to skip redundant API calls
    const previewVideoData = wizard.previewData?.data as any || {}
    const previewExtra = wizard.previewData?.extra as any || {}

    // Build metadata object based on source type
    const metadata: Record<string, unknown> = {
      title: wizard.editedMetadata.title || undefined,
      artist: wizard.editedMetadata.artist || undefined,
      year: wizard.editedMetadata.year || undefined,
      album: wizard.editedMetadata.album || undefined,
      director: wizard.editedMetadata.directors || undefined,
      label: wizard.editedMetadata.label || undefined,
      youtube_id: wizard.editedMetadata.youtubeId || undefined,
    }

    // Add source-specific fields from preview data
    if (wizard.selectedSource.source === 'imvdb') {
      // IMVDb-specific fields
      if (previewVideoData.directors?.length) {
        metadata.director = previewVideoData.directors.map((d: any) => d.entity_name).filter(Boolean).join(', ')
      }
      if (previewVideoData.featured_artists?.length) {
        metadata.featured_artists = previewVideoData.featured_artists.map((a: any) => a.name).filter(Boolean)
      }
      if (previewExtra.youtube_ids?.length) {
        metadata.youtube_id = previewExtra.youtube_ids[0]
      }

      // Add Discogs genre/label data if available (from IMVDb + Discogs comparison)
      if (discogsResults?.results?.length > 0) {
        const discogsData = discogsResults.results[0]?.data || {}
        if (discogsData.genres?.length) {
          metadata.genre = discogsData.genres[0]
        }
        if (discogsData.labels?.length && !metadata.label) {
          metadata.label = discogsData.labels[0].name
        }
      }
    } else if (wizard.selectedSource.source.startsWith('discogs')) {
      // Discogs-specific fields from preview
      if (previewVideoData.genres?.length) {
        metadata.genre = previewVideoData.genres[0]
      }
      if (previewVideoData.styles?.length) {
        metadata.styles = previewVideoData.styles
      }
      if (previewVideoData.labels?.length) {
        metadata.label = previewVideoData.labels[0].name
      }
      if (previewVideoData.artists?.length) {
        metadata.artist = previewVideoData.artists.map((a: any) => a.name).join(', ')
      }
    } else if (wizard.selectedSource.source === 'youtube') {
      // YouTube-specific fields
      metadata.youtube_id = previewVideoData.id || wizard.selectedSource.id
      metadata.title = previewVideoData.title || wizard.editedMetadata.title
      metadata.artist = previewVideoData.channel || wizard.editedMetadata.artist
      if (previewVideoData.duration) {
        metadata.duration = previewVideoData.duration
      }
    }

    // Clean undefined values
    Object.keys(metadata).forEach(key => {
      if (metadata[key] === undefined) {
        delete metadata[key]
      }
    })

    const request: AddSingleImportRequest = {
      source: wizard.selectedSource.source as any,
      id: wizard.selectedSource.id,
      youtube_id: wizard.editedMetadata.youtubeId || undefined,
      metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      initial_status: wizard.editedMetadata.initialStatus,
      skip_existing: wizard.editedMetadata.skipExisting,
      auto_download: wizard.editedMetadata.autoDownload,
    }

    importMutation.mutate(request)
  }

  const getSourceBadgeClass = (source: string) => {
    if (source === 'imvdb') return 'searchResultBadgeImvdb'
    if (source.startsWith('discogs')) return 'searchResultBadgeDiscogs'
    if (source === 'youtube') return 'searchResultBadgeYoutube'
    return ''
  }

  const getSourceLabel = (source: string) => {
    if (source === 'imvdb') return 'IMVDb'
    if (source === 'discogs_master') return 'Discogs Master'
    if (source === 'discogs_release') return 'Discogs Release'
    if (source === 'youtube') return 'YouTube'
    return source
  }

  // Build comparison fields for IMVDb vs Discogs
  const comparisonFields: ComparisonField[] = []
  if (wizard.compareWithDiscogs && discogsResults && discogsResults.results?.length > 0) {
    const discogsData = discogsResults.results[0]?.data || {}
    const imvdbData = wizard.previewData?.data as any || {}

    comparisonFields.push(
      {
        key: 'title',
        label: 'Title',
        imvdbValue: imvdbData.song_title || null,
        discogsValue: discogsData.title || null,
      },
      {
        key: 'artist',
        label: 'Artist',
        imvdbValue: imvdbData.artists?.[0]?.name || null,
        discogsValue: discogsData.artists?.map((a: any) => a.name).join(', ') || null,
      },
      {
        key: 'year',
        label: 'Year',
        imvdbValue: imvdbData.year?.toString() || null,
        discogsValue: discogsData.year?.toString() || null,
      }
    )
  }

  const handleFieldSelect = (fieldKey: string, source: 'imvdb' | 'discogs') => {
    setSelectedDiscogsFields((prev) => ({ ...prev, [fieldKey]: source }))

    // Update metadata based on selection
    if (discogsResults && discogsResults.results?.length > 0) {
      const discogsData = discogsResults.results[0]?.data || {}
      const imvdbData = wizard.previewData?.data as any || {}

      const updates: Partial<typeof wizard.editedMetadata> = {}

      if (fieldKey === 'title') {
        updates.title = source === 'imvdb' ? imvdbData.song_title : discogsData.title
      } else if (fieldKey === 'artist') {
        updates.artist = source === 'imvdb'
          ? imvdbData.artists?.[0]?.name
          : discogsData.artists?.map((a: any) => a.name).join(', ')
      } else if (fieldKey === 'year') {
        updates.year = source === 'imvdb' ? imvdbData.year : discogsData.year
      }

      wizard.updateMetadata(updates)
    }
  }

  const handleSelectYouTubeVideo = (youtubeId: string) => {
    wizard.updateMetadata({ youtubeId })
    setShowYouTubeSearch(false)
    toast.success('YouTube video selected', { description: youtubeId })
  }

  const handleCancelYouTubeSearch = () => {
    setShowYouTubeSearch(false)
    setYoutubeSearchResults(null)
  }

  return (
    <div className="searchWizard">
      <WizardStepper steps={STEPS} currentStep={wizard.currentStep} onStepClick={wizard.goToStep} />

      <div className="searchWizardContent">
        <div className="searchWizardHeader">
          <h1 className="searchWizardTitle">Artist/Title Search</h1>
          <Link to="/add" className="searchWizardBackLink">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Back to Hub
          </Link>
        </div>

        {/* Step 0: Search */}
        {wizard.currentStep === 0 && (
          <div className="searchWizardStep">
            <h2 className="searchWizardStepTitle">Search for a Video</h2>
            <p className="searchWizardStepDescription">
              Search across IMVDb, Discogs, and YouTube to find the music video you want to import.
            </p>

            <form onSubmit={handleSearch} className="searchWizardForm">
              <div className="searchWizardFormGroup">
                <label className="searchWizardLabel">Artist</label>
                <input
                  type="text"
                  className="searchWizardInput"
                  value={artist}
                  onChange={(e) => setArtist(e.target.value)}
                  placeholder="Enter artist name"
                />
              </div>

              <div className="searchWizardFormGroup">
                <label className="searchWizardLabel">Track Title</label>
                <input
                  type="text"
                  className="searchWizardInput"
                  value={trackTitle}
                  onChange={(e) => setTrackTitle(e.target.value)}
                  placeholder="Enter track title"
                />
              </div>

              <button
                type="submit"
                className="searchWizardButton"
                disabled={searchMutation.isPending}
              >
                {searchMutation.isPending ? 'Searching...' : 'Search'}
              </button>
            </form>
          </div>
        )}

        {/* Step 1: Select Source */}
        {wizard.currentStep === 1 && wizard.searchResults && (
          <div className="searchWizardStep">
            <h2 className="searchWizardStepTitle">Select a Source</h2>
            <p className="searchWizardStepDescription">
              Choose the result that best matches your video. Click to view details and proceed.
            </p>

            <div className="searchResultsList">
              {wizard.searchResults.results?.map((result, index) => (
                <button
                  key={index}
                  type="button"
                  className="searchResultCard"
                  onClick={() => handleSelectResult(result.source, result.id)}
                >
                  <div className="searchResultCardHeader">
                    <span className={`searchResultBadge ${getSourceBadgeClass(result.source)}`}>
                      {getSourceLabel(result.source)}
                    </span>
                  </div>

                  {result.thumbnail && (
                    <img src={result.thumbnail} alt="" className="searchResultThumbnail" />
                  )}

                  <div className="searchResultInfo">
                    <h3 className="searchResultTitle">{result.title}</h3>
                    <p className="searchResultArtist">{result.artist}</p>
                    {result.year && <p className="searchResultYear">{result.year}</p>}
                  </div>
                </button>
              ))}
            </div>

            <div className="searchWizardActions">
              <button type="button" className="searchWizardButtonSecondary" onClick={wizard.prevStep}>
                Back
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Edit Metadata */}
        {wizard.currentStep === 2 && (
          <div className="searchWizardStep">
            <h2 className="searchWizardStepTitle">Review & Edit Metadata</h2>
            <p className="searchWizardStepDescription">
              Review the metadata and make any necessary edits before importing.
            </p>

            {previewQuery.isLoading && <div className="searchWizardLoading">Loading preview...</div>}

            {previewQuery.data && (
              <div className="metadataEditor">
                <div className="metadataEditorSection">
                  <h3 className="metadataEditorSectionTitle">Basic Information</h3>

                  <div className="metadataEditorFormGroup">
                    <label className="metadataEditorLabel">Title</label>
                    <input
                      type="text"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.title}
                      onChange={(e) => wizard.updateMetadata({ title: e.target.value })}
                    />
                  </div>

                  <div className="metadataEditorFormGroup">
                    <label className="metadataEditorLabel">Artist</label>
                    <input
                      type="text"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.artist}
                      onChange={(e) => wizard.updateMetadata({ artist: e.target.value })}
                    />
                  </div>

                  <div className="metadataEditorFormGroup">
                    <label className="metadataEditorLabel">Year</label>
                    <input
                      type="number"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.year || ''}
                      onChange={(e) => wizard.updateMetadata({ year: e.target.value ? parseInt(e.target.value) : null })}
                    />
                  </div>
                </div>

                <div className="metadataEditorSection">
                  <h3 className="metadataEditorSectionTitle">Extended Metadata</h3>

                  <div className="metadataEditorFormGroup">
                    <label className="metadataEditorLabel">Album</label>
                    <input
                      type="text"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.album || ''}
                      onChange={(e) => wizard.updateMetadata({ album: e.target.value })}
                    />
                  </div>

                  <div className="metadataEditorFormGroup">
                    <label className="metadataEditorLabel">Director(s)</label>
                    <input
                      type="text"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.directors || ''}
                      onChange={(e) => wizard.updateMetadata({ directors: e.target.value })}
                      placeholder={wizard.selectedSource?.source === 'imvdb' ? 'From IMVDb' : 'Enter director name(s)'}
                    />
                  </div>

                  <div className="metadataEditorFormGroup">
                    <label className="metadataEditorLabel">Record Label</label>
                    <input
                      type="text"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.label || ''}
                      onChange={(e) => wizard.updateMetadata({ label: e.target.value })}
                    />
                  </div>
                </div>

                {/* Source Comparison (only for IMVDb) */}
                {wizard.selectedSource?.source === 'imvdb' && discogsResults && (
                  <div className="metadataEditorSection">
                    <label className="metadataEditorCheckbox">
                      <input
                        type="checkbox"
                        checked={wizard.compareWithDiscogs}
                        onChange={(e) => wizard.setCompareWithDiscogs(e.target.checked)}
                      />
                      <span>Show source comparison (Discogs data already merged)</span>
                    </label>

                    {wizard.compareWithDiscogs && comparisonFields.length > 0 && (
                      <SourceComparison
                        fields={comparisonFields}
                        selectedFields={selectedDiscogsFields}
                        onFieldSelect={handleFieldSelect}
                      />
                    )}
                  </div>
                )}

                {/* Video Sources (YouTube IDs) */}
                {wizard.previewData?.extra && (wizard.previewData.extra as any).youtube_ids?.length > 0 && (
                  <div className="metadataEditorSection">
                    <h3 className="metadataEditorSectionTitle">Video Sources</h3>
                    <p className="metadataEditorSectionDescription">
                      Select the video source to use for this import.
                    </p>

                    {/* Availability status banner */}
                    {wizard.youtubeSourceInfo && !wizard.youtubeSourceInfo.available && (
                      <div className="youtubeUnavailableBanner">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="bannerIcon">
                          <circle cx="12" cy="12" r="10" />
                          <line x1="12" y1="8" x2="12" y2="12" />
                          <line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                        <span className="bannerText">
                          Selected video is unavailable: {wizard.youtubeSourceInfo.error || 'Video not accessible'}
                        </span>
                      </div>
                    )}

                    {/* Availability info for selected video */}
                    {wizard.youtubeSourceInfo?.available && (
                      <div className="youtubeAvailableInfo">
                        <span className="availableChannel">{wizard.youtubeSourceInfo.channel}</span>
                        <span className="availableDuration">
                          {wizard.youtubeSourceInfo.duration
                            ? `${Math.floor(wizard.youtubeSourceInfo.duration / 60)}:${String(wizard.youtubeSourceInfo.duration % 60).padStart(2, '0')}`
                            : ''}
                        </span>
                        <span className="availableViews">
                          {wizard.youtubeSourceInfo.view_count
                            ? `${(wizard.youtubeSourceInfo.view_count / 1000000).toFixed(1)}M views`
                            : ''}
                        </span>
                      </div>
                    )}

                    <div className="videoSourcesList">
                      {((wizard.previewData.extra as any).youtube_ids as string[]).map((ytId) => (
                        <label key={ytId} className="videoSourceOption">
                          <input
                            type="radio"
                            name="youtubeId"
                            value={ytId}
                            checked={wizard.editedMetadata.youtubeId === ytId}
                            onChange={() => {
                              wizard.updateMetadata({ youtubeId: ytId })
                              checkYouTubeAvailability(ytId)
                            }}
                          />
                          <span className="videoSourceId">{ytId}</span>
                          {wizard.youtubeSourceInfo?.youtube_id === ytId && (
                            <span className={`videoSourceStatus ${wizard.youtubeSourceInfo.available ? 'available' : 'unavailable'}`}>
                              {wizard.youtubeSourceInfo.available ? '✓ Available' : '✗ Unavailable'}
                            </span>
                          )}
                          <button
                            type="button"
                            className="videoSourcePreview"
                            onClick={() => window.open(`https://youtube.com/watch?v=${ytId}`, '_blank')}
                          >
                            Preview
                          </button>
                        </label>
                      ))}
                    </div>

                    {/* Search YouTube button */}
                    <div className="videoSourcesActions">
                      <button
                        type="button"
                        className="searchWizardButtonSecondary"
                        onClick={() => youtubeSearchMutation.mutate()}
                        disabled={youtubeSearchMutation.isPending}
                      >
                        {youtubeSearchMutation.isPending ? 'Searching...' : 'Search YouTube for Alternate'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="searchWizardActions">
              <button type="button" className="searchWizardButtonSecondary" onClick={wizard.prevStep}>
                Back
              </button>
              <button type="button" className="searchWizardButton" onClick={wizard.nextStep}>
                Continue to Review
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Review & Submit */}
        {wizard.currentStep === 3 && (
          <div className="searchWizardStep">
            <h2 className="searchWizardStepTitle">Review & Submit</h2>
            <p className="searchWizardStepDescription">
              Review your metadata and configure import settings before submitting.
            </p>

            <div className="reviewSummary">
              <div className="reviewSummarySection">
                <h3 className="reviewSummaryTitle">Metadata</h3>
                <dl className="reviewSummaryList">
                  <dt>Title</dt>
                  <dd>{wizard.editedMetadata.title}</dd>
                  <dt>Artist</dt>
                  <dd>{wizard.editedMetadata.artist}</dd>
                  {wizard.editedMetadata.year && (
                    <>
                      <dt>Year</dt>
                      <dd>{wizard.editedMetadata.year}</dd>
                    </>
                  )}
                  {wizard.editedMetadata.album && (
                    <>
                      <dt>Album</dt>
                      <dd>{wizard.editedMetadata.album}</dd>
                    </>
                  )}
                  {wizard.editedMetadata.directors && (
                    <>
                      <dt>Director(s)</dt>
                      <dd>{wizard.editedMetadata.directors}</dd>
                    </>
                  )}
                  {wizard.editedMetadata.label && (
                    <>
                      <dt>Record Label</dt>
                      <dd>{wizard.editedMetadata.label}</dd>
                    </>
                  )}
                </dl>
              </div>

              <div className="reviewSummarySection">
                <h3 className="reviewSummaryTitle">Source</h3>
                <dl className="reviewSummaryList">
                  <dt>Source</dt>
                  <dd>{getSourceLabel(wizard.selectedSource?.source || '')}</dd>
                  <dt>ID</dt>
                  <dd>{wizard.selectedSource?.id}</dd>
                </dl>
              </div>
            </div>

            <div className="configureForm">
              <div className="configureFormGroup">
                <label className="configureLabel">YouTube ID (Optional Override)</label>
                <div className="youtubeIdInputGroup">
                  <input
                    type="text"
                    className="configureInput"
                    value={wizard.editedMetadata.youtubeId || ''}
                    onChange={(e) => wizard.updateMetadata({ youtubeId: e.target.value })}
                    placeholder="Enter YouTube video ID"
                  />
                  <button
                    type="button"
                    className="searchWizardButtonSecondary youtubeSearchButton"
                    onClick={() => youtubeSearchMutation.mutate()}
                    disabled={youtubeSearchMutation.isPending}
                  >
                    {youtubeSearchMutation.isPending ? 'Searching...' : 'Search YouTube'}
                  </button>
                </div>
                <p className="configureHint">
                  Override the YouTube video ID if needed. Leave blank to use the automatically detected ID.
                </p>
              </div>

              <div className="configureFormGroup">
                <label className="configureLabel">Initial Status</label>
                <select
                  className="configureSelect"
                  value={wizard.editedMetadata.initialStatus}
                  onChange={(e) => wizard.updateMetadata({ initialStatus: e.target.value as 'discovered' | 'imported' })}
                >
                  <option value="discovered">Discovered</option>
                  <option value="imported">Imported</option>
                </select>
              </div>

              <div className="configureFormGroup">
                <label className="configureCheckbox">
                  <input
                    type="checkbox"
                    checked={wizard.editedMetadata.skipExisting}
                    onChange={(e) => wizard.updateMetadata({ skipExisting: e.target.checked })}
                  />
                  <span>Skip if already exists</span>
                </label>
              </div>

              <div className="configureFormGroup">
                <label className="configureCheckbox">
                  <input
                    type="checkbox"
                    checked={wizard.editedMetadata.autoDownload}
                    onChange={(e) => wizard.updateMetadata({ autoDownload: e.target.checked })}
                  />
                  <span>Download video upon import</span>
                </label>
                <p className="configureHint">
                  When enabled, the video will be automatically downloaded from YouTube after import.
                </p>
              </div>
            </div>

            <div className="searchWizardActions">
              <button type="button" className="searchWizardButtonSecondary" onClick={wizard.prevStep}>
                Back
              </button>
              <button
                type="button"
                className="searchWizardButton"
                onClick={handleImportSubmit}
                disabled={importMutation.isPending}
              >
                {importMutation.isPending ? 'Submitting...' : 'Submit Import'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* YouTube Search Modal */}
      {showYouTubeSearch && youtubeSearchResults && (
        <div className="youtubeSearchModal">
          <div className="youtubeSearchModalOverlay" onClick={handleCancelYouTubeSearch} />
          <div className="youtubeSearchModalContent">
            <div className="youtubeSearchModalHeader">
              <h2 className="youtubeSearchModalTitle">Select YouTube Video</h2>
              <button
                type="button"
                className="youtubeSearchModalClose"
                onClick={handleCancelYouTubeSearch}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="youtubeSearchModalBody">
              {youtubeSearchResults.results && youtubeSearchResults.results.length > 0 ? (
                <div className="youtubeSearchResults">
                  {youtubeSearchResults.results.map((result: any, index: number) => (
                    <div key={index} className="youtubeSearchResultCard">
                      {result.thumbnail && (
                        <img
                          src={result.thumbnail}
                          alt={result.title}
                          className="youtubeSearchResultThumbnail"
                        />
                      )}
                      <div className="youtubeSearchResultInfo">
                        <h3 className="youtubeSearchResultTitle">{result.title}</h3>
                        <p className="youtubeSearchResultId">ID: {result.id}</p>
                        {result.extra?.channel && (
                          <p className="youtubeSearchResultChannel">{result.extra.channel}</p>
                        )}
                        {result.extra?.duration && (
                          <p className="youtubeSearchResultDuration">
                            Duration: {Math.floor(result.extra.duration / 60)}:{String(result.extra.duration % 60).padStart(2, '0')}
                          </p>
                        )}
                      </div>
                      <div className="youtubeSearchResultActions">
                        <button
                          type="button"
                          className="youtubeSearchResultPreview"
                          onClick={() => window.open(`https://youtube.com/watch?v=${result.id}`, '_blank')}
                        >
                          Preview
                        </button>
                        <button
                          type="button"
                          className="youtubeSearchResultSelect"
                          onClick={() => handleSelectYouTubeVideo(result.id)}
                        >
                          Select
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="youtubeSearchNoResults">
                  <p>No YouTube results found.</p>
                </div>
              )}
            </div>

            <div className="youtubeSearchModalFooter">
              <button
                type="button"
                className="searchWizardButtonSecondary"
                onClick={handleCancelYouTubeSearch}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
