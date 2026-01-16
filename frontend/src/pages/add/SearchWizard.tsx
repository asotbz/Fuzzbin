/* eslint-disable @typescript-eslint/no-explicit-any -- Wizard handles dynamic API responses */
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { addSearch, addPreview, addImport, checkVideoExists, getYouTubeMetadata } from '../../lib/api/endpoints/add'
import { addKeys, searchKeys, videosKeys } from '../../lib/api/queryKeys'
import { useSearchWizard } from '../../hooks/add/useSearchWizard'
import PageHeader from '../../components/layout/PageHeader'
import SourceComparison, { type ComparisonField } from '../../components/add/metadata/SourceComparison'
import type { AddSingleImportRequest } from '../../lib/api/types'
import './SearchWizard.css'

export default function SearchWizard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
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

  // Eagerly fetch YouTube metadata for all available sources when they become available
  useEffect(() => {
    const youtubeIds = wizard.availableYouTubeSources
    if (youtubeIds.length === 0) return

    // Fetch metadata for each YouTube ID that isn't already in cache
    youtubeIds.forEach(async (ytId) => {
      if (wizard.youtubeMetadataCache[ytId]) return // Already fetched

      try {
        const response = await getYouTubeMetadata({ youtube_id: ytId })
        wizard.updateYouTubeMetadataCache(ytId, {
          youtube_id: response.youtube_id,
          available: response.available,
          view_count: response.view_count,
          duration: response.duration,
          channel: response.channel,
          title: response.title,
          error: response.error,
        })
      } catch (error) {
        console.error(`Failed to fetch YouTube metadata for ${ytId}:`, error)
        wizard.updateYouTubeMetadataCache(ytId, {
          youtube_id: ytId,
          available: false,
          view_count: null,
          duration: null,
          channel: null,
          title: null,
          error: 'Failed to fetch metadata',
        })
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Only run when availableYouTubeSources changes
  }, [wizard.availableYouTubeSources])

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
    let genre: string | null = null
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
        // If IMVDb doesn't have album, use Discogs title (which is the album name)
        if (!album && discogsData.title) {
          album = discogsData.title
        }

        // Always use Discogs label (IMVDb doesn't have this)
        // Take only the first label (parent/main label, not imprints)
        if (discogsData.labels && Array.isArray(discogsData.labels) && discogsData.labels.length > 0) {
          label = discogsData.labels[0].name || null
        }

        // Extract genre from Discogs (IMVDb doesn't have genres)
        if (discogsData.genres && Array.isArray(discogsData.genres) && discogsData.genres.length > 0) {
          genre = discogsData.genres[0]
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

      // Extract genre from Discogs
      if (videoData.genres && Array.isArray(videoData.genres) && videoData.genres.length > 0) {
        genre = videoData.genres[0]
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
      genre,
      youtubeId,
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
      // Invalidate videos query so library shows new video
      queryClient.invalidateQueries({ queryKey: videosKeys.all })
      queryClient.invalidateQueries({ queryKey: searchKeys.all })
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

      // Album
      const imvdbAlbum = imvdbData.album || null
      const discogsAlbum = discogsData.title || null
      if (imvdbAlbum && !discogsAlbum) {
        selections.album = 'imvdb'
      } else if (!imvdbAlbum && discogsAlbum) {
        selections.album = 'discogs'
      } else if (imvdbAlbum && discogsAlbum) {
        selections.album = 'imvdb'
      }

      // Label (only Discogs has this)
      const discogsLabel = discogsData.labels?.[0]?.name || null
      if (discogsLabel) {
        selections.label = 'discogs'
      }

      // Genre (only Discogs has this)
      const discogsGenre = discogsData.genres?.[0] || null
      if (discogsGenre) {
        selections.genre = 'discogs'
      }

      // Director (only IMVDb has this)
      const imvdbDirectors = imvdbData.directors?.map((d: any) => d.entity_name).filter(Boolean).join(', ') || null
      if (imvdbDirectors) {
        selections.director = 'imvdb'
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

    // Build pre-fetched metadata from wizard state (user-edited values take priority)
    // This allows the backend to skip redundant API calls
    const previewVideoData = wizard.previewData?.data as any || {}
    const previewExtra = wizard.previewData?.extra as any || {}

    // Build metadata object from edited metadata (user edits have priority)
    const metadata: Record<string, unknown> = {
      title: wizard.editedMetadata.title || undefined,
      artist: wizard.editedMetadata.artist || undefined,
      year: wizard.editedMetadata.year || undefined,
      album: wizard.editedMetadata.album || undefined,
      director: wizard.editedMetadata.directors || undefined,
      label: wizard.editedMetadata.label || undefined,
      genre: wizard.editedMetadata.genre || undefined,
      youtube_id: wizard.editedMetadata.youtubeId || undefined,
    }

    // Add source-specific fields from preview data (only if not already set by user)
    if (wizard.selectedSource.source === 'imvdb') {
      // IMVDb-specific fields
      if (!metadata.director && previewVideoData.directors?.length) {
        metadata.director = previewVideoData.directors.map((d: any) => d.entity_name).filter(Boolean).join(', ')
      }
      if (previewVideoData.featured_artists?.length) {
        metadata.featured_artists = previewVideoData.featured_artists.map((a: any) => a.name).filter(Boolean)
      }
      if (!metadata.youtube_id && previewExtra.youtube_ids?.length) {
        metadata.youtube_id = previewExtra.youtube_ids[0]
      }
      // Include IMVDb URL for proper link generation
      if (previewVideoData.url) {
        metadata.imvdb_url = previewVideoData.url
      }

      // Add Discogs genre/label data if available (from IMVDb + Discogs comparison)
      if (discogsResults?.results?.length > 0) {
        const discogsData = discogsResults.results[0]?.data || {}
        if (!metadata.genre && discogsData.genres?.length) {
          metadata.genre = discogsData.genres[0]
        }
        if (!metadata.label && discogsData.labels?.length) {
          metadata.label = discogsData.labels[0].name
        }
      }
    } else if (wizard.selectedSource.source.startsWith('discogs')) {
      // Discogs-specific fields from preview (only if not set by user)
      if (!metadata.genre && previewVideoData.genres?.length) {
        metadata.genre = previewVideoData.genres[0]
      }
      if (previewVideoData.styles?.length) {
        metadata.styles = previewVideoData.styles
      }
      if (!metadata.label && previewVideoData.labels?.length) {
        metadata.label = previewVideoData.labels[0].name
      }
      if (!metadata.artist && previewVideoData.artists?.length) {
        metadata.artist = previewVideoData.artists.map((a: any) => a.name).join(', ')
      }
    } else if (wizard.selectedSource.source === 'youtube') {
      // YouTube-specific fields
      if (!metadata.youtube_id) {
        metadata.youtube_id = previewVideoData.id || wizard.selectedSource.id
      }
      if (!metadata.title) {
        metadata.title = previewVideoData.title
      }
      if (!metadata.artist) {
        metadata.artist = previewVideoData.channel
      }
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
      initial_status: 'discovered',  // Always use discovered status
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

  // Build comparison fields for IMVDb vs Discogs (always show when Discogs data available)
  const comparisonFields: ComparisonField[] = []
  if (discogsResults && discogsResults.results?.length > 0) {
    const discogsData = discogsResults.results[0]?.data || {}
    const imvdbData = wizard.previewData?.data as any || {}

    // Extract Discogs values
    const discogsArtist = discogsData.artists?.map((a: any) => a.name).join(', ') || null
    const discogsLabel = discogsData.labels?.[0]?.name || null
    const discogsGenre = discogsData.genres?.[0] || null

    // Extract IMVDb values
    const imvdbDirectors = imvdbData.directors?.map((d: any) => d.entity_name).filter(Boolean).join(', ') || null

    comparisonFields.push(
      {
        key: 'title',
        label: 'Title',
        imvdbValue: imvdbData.song_title || null,
        discogsValue: null, // Discogs doesn't have track title, only album title
      },
      {
        key: 'artist',
        label: 'Artist',
        imvdbValue: imvdbData.artists?.[0]?.name || null,
        discogsValue: discogsArtist,
      },
      {
        key: 'year',
        label: 'Year',
        imvdbValue: imvdbData.year?.toString() || null,
        discogsValue: discogsData.year?.toString() || null,
      },
      {
        key: 'album',
        label: 'Album',
        imvdbValue: imvdbData.album || null,
        discogsValue: discogsData.title || null, // Discogs title = album name
      },
      {
        key: 'label',
        label: 'Label',
        imvdbValue: null, // IMVDb doesn't have label
        discogsValue: discogsLabel,
      },
      {
        key: 'genre',
        label: 'Genre',
        imvdbValue: null, // IMVDb doesn't have genre
        discogsValue: discogsGenre,
      },
      {
        key: 'director',
        label: 'Director',
        imvdbValue: imvdbDirectors,
        discogsValue: null, // Discogs doesn't have director
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
        // Title only comes from IMVDb (song_title)
        updates.title = imvdbData.song_title || ''
      } else if (fieldKey === 'artist') {
        updates.artist = source === 'imvdb'
          ? imvdbData.artists?.[0]?.name
          : discogsData.artists?.map((a: any) => a.name).join(', ')
      } else if (fieldKey === 'year') {
        updates.year = source === 'imvdb' ? imvdbData.year : discogsData.year
      } else if (fieldKey === 'album') {
        updates.album = source === 'imvdb'
          ? imvdbData.album
          : discogsData.title // Discogs title = album name
      } else if (fieldKey === 'label') {
        // Label only comes from Discogs
        updates.label = discogsData.labels?.[0]?.name || null
      } else if (fieldKey === 'genre') {
        // Genre only comes from Discogs
        updates.genre = discogsData.genres?.[0] || null
      } else if (fieldKey === 'director') {
        // Director only comes from IMVDb
        updates.directors = imvdbData.directors?.map((d: any) => d.entity_name).filter(Boolean).join(', ') || null
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
      <PageHeader
        title="Artist/Title Search"
        iconSrc="/fuzzbin-icon.png"
        iconAlt="Fuzzbin"
        accent="var(--channel-import)"
        navItems={[
          { label: 'Library', to: '/library' },
          { label: 'Import', to: '/add' },
          { label: 'Activity', to: '/activity' },
          { label: 'Settings', to: '/settings' },
        ]}
        subNavLabel="Import workflows"
        subNavItems={[
          { label: 'Search', to: '/add', end: true },
          { label: 'Spotify Playlist', to: '/add/spotify' },
          { label: 'Artist Videos', to: '/add/artist' },
          { label: 'NFO Scan', to: '/add/nfo' },
        ]}
      />

      <div className="searchWizardContent">
        {/* Step 0: Search */}
        {wizard.currentStep === 0 && (
          <div className="searchWizardStep">
            <h2 className="searchWizardCardTitle">Search Configuration</h2>
            <form onSubmit={handleSearch} className="searchWizardForm">
              <div className="searchWizardFormRow">
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
            {previewQuery.isLoading && <div className="searchWizardLoading">Loading preview...</div>}

            {previewQuery.data && (
              <div className="metadataEditor">
                {/* Source Comparison (shown first, unfurled, for IMVDb sources with Discogs data) */}
                {wizard.selectedSource?.source === 'imvdb' && discogsResults && comparisonFields.length > 0 && (
                  <div className="metadataEditorSection">
                    <SourceComparison
                      fields={comparisonFields}
                      selectedFields={selectedDiscogsFields}
                      onFieldSelect={handleFieldSelect}
                    />
                  </div>
                )}

                {/* Separator when source comparison is shown */}
                {wizard.selectedSource?.source === 'imvdb' && discogsResults && comparisonFields.length > 0 && (
                  <div className="metadataEditorSeparator">
                    <span>or manually edit below:</span>
                  </div>
                )}

                {/* Unified Metadata Section */}
                <div className="metadataEditorSection">
                  <h3 className="metadataEditorSectionTitle">Metadata</h3>

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
                    <label className="metadataEditorLabel">Record Label</label>
                    <input
                      type="text"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.label || ''}
                      onChange={(e) => wizard.updateMetadata({ label: e.target.value })}
                    />
                  </div>

                  <div className="metadataEditorFormGroup">
                    <label className="metadataEditorLabel">Genre</label>
                    <input
                      type="text"
                      className="metadataEditorInput"
                      value={wizard.editedMetadata.genre || ''}
                      onChange={(e) => wizard.updateMetadata({ genre: e.target.value })}
                      placeholder="e.g., Rock, Pop, Hip Hop"
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
                </div>

                {/* Video Sources (YouTube IDs) */}
                {wizard.previewData?.extra && (wizard.previewData.extra as any).youtube_ids?.length > 0 && (
                  <div className="metadataEditorSection">
                    <h3 className="metadataEditorSectionTitle">Video Sources</h3>
                    <p className="metadataEditorSectionDescription">
                      Select the video source to use for this import.
                    </p>

                    <div className="videoSourcesList">
                      {((wizard.previewData.extra as any).youtube_ids as string[]).map((ytId) => {
                        const metadata = wizard.youtubeMetadataCache[ytId]
                        const isLoading = !metadata
                        const isAvailable = metadata?.available
                        const isSelected = wizard.editedMetadata.youtubeId === ytId

                        // Format duration
                        const formatDuration = (seconds: number | null) => {
                          if (!seconds) return ''
                          const mins = Math.floor(seconds / 60)
                          const secs = seconds % 60
                          return `${mins}:${String(secs).padStart(2, '0')}`
                        }

                        // Format view count
                        const formatViews = (views: number | null) => {
                          if (!views) return ''
                          if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M views`
                          if (views >= 1000) return `${(views / 1000).toFixed(0)}K views`
                          return `${views} views`
                        }

                        return (
                          <label
                            key={ytId}
                            className={`videoSourceOption ${isSelected ? 'videoSourceOptionSelected' : ''} ${!isAvailable && !isLoading ? 'videoSourceOptionUnavailable' : ''}`}
                          >
                            <input
                              type="radio"
                              name="youtubeId"
                              value={ytId}
                              checked={isSelected}
                              onChange={() => {
                                wizard.updateMetadata({ youtubeId: ytId })
                                // Also update the selected source info for the banner
                                if (metadata) {
                                  wizard.setYouTubeSourceInfo(metadata)
                                }
                              }}
                            />
                            <div className="videoSourceContent">
                              <span className="videoSourceId">{ytId}</span>
                              {isLoading ? (
                                <span className="videoSourceMetadataLoading">Loading...</span>
                              ) : metadata ? (
                                <div className="videoSourceMetadata">
                                  {metadata.channel && (
                                    <span className="videoSourceChannel">{metadata.channel}</span>
                                  )}
                                  {metadata.duration && (
                                    <span className="videoSourceDuration">{formatDuration(metadata.duration)}</span>
                                  )}
                                  {metadata.view_count && (
                                    <span className="videoSourceViews">{formatViews(metadata.view_count)}</span>
                                  )}
                                  {!isAvailable && (
                                    <span className="videoSourceUnavailable">Unavailable</span>
                                  )}
                                </div>
                              ) : null}
                            </div>
                            <button
                              type="button"
                              className="videoSourcePreview"
                              onClick={(e) => {
                                e.preventDefault()
                                window.open(`https://youtube.com/watch?v=${ytId}`, '_blank')
                              }}
                            >
                              Preview
                            </button>
                          </label>
                        )
                      })}
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
                  {wizard.editedMetadata.genre && (
                    <>
                      <dt>Genre</dt>
                      <dd>{wizard.editedMetadata.genre}</dd>
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
                  {wizard.editedMetadata.youtubeId && (
                    <>
                      <dt>YouTube ID</dt>
                      <dd>{wizard.editedMetadata.youtubeId}</dd>
                    </>
                  )}
                </dl>
              </div>
            </div>

            <div className="configureForm">
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
