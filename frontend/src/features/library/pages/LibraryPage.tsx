import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import PageHeader from '../../../components/layout/PageHeader'
import VideoCard, { type VideoCardJobStatus } from '../../../components/video/VideoCard'
import VideoGrid from '../../../components/video/VideoGrid'
import LibraryTable, { type LibraryTableColumns } from '../components/LibraryTable'
import MultiSelectToolbar from '../components/MultiSelectToolbar'
import BulkTagModal from '../components/BulkTagModal'
import VideoDetailsModal from '../components/VideoDetailsModal'
import VideoPlayerModal from '../components/VideoPlayerModal'
import ConfirmDialog from '../components/ConfirmDialog'
import type { FacetsResponse, ListVideosQuery, SortOrder, Video } from '../../../lib/api/types'
import { useFacets } from '../hooks/useFacets'
import { searchKeys, videosKeys } from '../../../lib/api/queryKeys'
import { bulkDeleteVideos } from '../../../lib/api/endpoints/videos'
import { useJobEvents, type VideoUpdateEvent } from '../../../lib/ws/useJobEvents'
import { useAuthTokens } from '../../../auth/useAuthTokens'
import { getApiBaseUrl } from '../../../api/client'
import { listVideos } from '../../../lib/api/endpoints/videos'
import './LibraryPage.css'

type FacetItem = { value: string; count: number }
type FacetKey = 'tags' | 'genres' | 'years'

const FACET_LIMIT = 12
const FACET_NONE_VALUE = '__none__'
const YEAR_NONE_SENTINEL = -1

type FacetSelections = {
  tag_name?: string[]
  genre?: string[]
  director?: string
  year?: number[]
}

function asFacetList(list: unknown): FacetItem[] {
  if (!Array.isArray(list)) return []
  return list
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const obj = item as Record<string, unknown>
      const value = typeof obj.value === 'string' ? obj.value : null
      const count = typeof obj.count === 'number' ? obj.count : null
      if (!value || count === null) return null
      return { value, count }
    })
    .filter((x): x is FacetItem => Boolean(x))
}

function getFacets(facets: FacetsResponse | undefined): {
  tags: FacetItem[]
  genres: FacetItem[]
  years: FacetItem[]
  directors: FacetItem[]
} {
  const any = facets as unknown as Record<string, unknown> | undefined
  return {
    tags: asFacetList(any?.tags),
    genres: asFacetList(any?.genres),
    years: asFacetList(any?.years),
    directors: asFacetList(any?.directors),
  }
}

function toggleListValue<T>(current: T[] | undefined, next: T): T[] {
  const list = current ? [...current] : []
  const index = list.indexOf(next)
  if (index >= 0) {
    list.splice(index, 1)
    return list
  }
  list.push(next)
  return list
}

function updateListFilter<T>(current: T[] | undefined, next: T): T[] | undefined {
  const updated = toggleListValue(current, next)
  return updated.length > 0 ? updated : undefined
}

function formatFacetValue(value: string): string {
  return value === FACET_NONE_VALUE ? '(none)' : value
}

function getFacetDisplay(values: string[]): string | null {
  if (values.length === 0) return null
  if (values.length === 1) return formatFacetValue(values[0])
  return `${values.length} selected`
}

export default function LibraryPage() {
  const location = useLocation()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  const [sortBy, setSortBy] = useState<string>('artist')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')
  const pageSize = 20

  const [filters, setFilters] = useState<FacetSelections>({})
  const [facetExpandedByKey, setFacetExpandedByKey] = useState<Record<FacetKey, boolean>>({
    tags: false,
    genres: false,
    years: false,
  })
  const [facetSearch, setFacetSearch] = useState<Record<FacetKey, string>>({
    tags: '',
    genres: '',
    years: '',
  })

  // View mode state
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid')
  const [tableColumns, setTableColumns] = useState<LibraryTableColumns>('full')

  // Facet popover state
  const [openFacet, setOpenFacet] = useState<FacetKey | null>(null)
  const facetBarRef = useRef<HTMLDivElement | null>(null)
  const loadMoreRef = useRef<HTMLDivElement | null>(null)

  // Multi-select state
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<number>>(new Set())

  // Modal state
  const [detailsModalVideo, setDetailsModalVideo] = useState<Video | null>(null)
  const [playerVideo, setPlayerVideo] = useState<Video | null>(null)
  const [bulkTagModalOpen, setBulkTagModalOpen] = useState(false)
  const [showBulkDeleteConfirm, setShowBulkDeleteConfirm] = useState(false)

  const queryClient = useQueryClient()

  // Bulk delete mutation
  const bulkDeleteMutation = useMutation({
    mutationFn: async ({ videoIds, deleteFiles }: { videoIds: number[]; deleteFiles: boolean }) => {
      await bulkDeleteVideos(videoIds, deleteFiles)
    },
    onSuccess: (_, { videoIds, deleteFiles }) => {
      if (deleteFiles) {
        toast.success(`Deleted ${videoIds.length} video${videoIds.length !== 1 ? 's' : ''} and files`)
      } else {
        toast.success(`Deleted ${videoIds.length} video${videoIds.length !== 1 ? 's' : ''}`)
      }
      queryClient.invalidateQueries({ queryKey: videosKeys.all })
      queryClient.invalidateQueries({ queryKey: searchKeys.all })
      clearSelection()
    },
    onError: (error) => {
      toast.error('Failed to delete videos', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const urlSearch = (params.get('search') ?? '').trim()
    if (!urlSearch) return

    setSearch(urlSearch)
    setDebouncedSearch(urlSearch)
  }, [location.search])

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedSearch(search)
    }, 300)
    return () => window.clearTimeout(t)
  }, [search])

  // Load view mode from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('library-view-mode')
    if (saved === 'grid' || saved === 'table') setViewMode(saved)
  }, [])

  // Save view mode to localStorage
  useEffect(() => {
    localStorage.setItem('library-view-mode', viewMode)
  }, [viewMode])

  // Force grid view on mobile
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768 && viewMode === 'table') {
        setViewMode('grid')
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [viewMode])

  // Clear selection on filter/sort/search changes
  useEffect(() => {
    setSelectedVideoIds(new Set())
  }, [debouncedSearch, sortBy, sortOrder, filters.tag_name, filters.genre, filters.year])

  useEffect(() => {
    if (!openFacet) return
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (!target || !facetBarRef.current) return
      if (!facetBarRef.current.contains(target)) {
        setOpenFacet(null)
      }
    }
    window.addEventListener('mousedown', handleClickOutside)
    return () => window.removeEventListener('mousedown', handleClickOutside)
  }, [openFacet])

  const facetsQuery = useFacets({ include_deleted: false })
  const facets = useMemo(() => getFacets(facetsQuery.data), [facetsQuery.data])
  const yearFacetItems = useMemo(
    () =>
      facets.years.filter(
        (y) => y.value === FACET_NONE_VALUE || Number.isFinite(Number(y.value))
      ),
    [facets.years]
  )

  const videosQueryBase: ListVideosQuery = useMemo(() => {
    const query: Record<string, unknown> = {
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
      include_deleted: false,
    }

    if (debouncedSearch.trim().length > 0) query.search = debouncedSearch

    if (filters.tag_name && filters.tag_name.length > 0) query.tag_name = filters.tag_name
    if (filters.genre && filters.genre.length > 0) query.genre = filters.genre
    if (filters.director) query.director = filters.director
    if (filters.year && filters.year.length > 0) query.year = filters.year

    return query as ListVideosQuery
  }, [pageSize, sortBy, sortOrder, debouncedSearch, filters])

  const videosQuery = useInfiniteQuery({
    queryKey: videosKeys.list(videosQueryBase),
    queryFn: ({ pageParam = 1 }) => listVideos({ ...videosQueryBase, page: pageParam as number }),
    getNextPageParam: (lastPage) => {
      if (!lastPage || typeof lastPage.page !== 'number' || typeof lastPage.total_pages !== 'number') {
        return undefined
      }
      return lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined
    },
    initialPageParam: 1,
  })
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = videosQuery

  const items = useMemo(() => {
    const pages = videosQuery.data?.pages ?? []
    const merged = pages.flatMap((page) => (page.items as unknown as Video[] | undefined) ?? [])
    return merged
  }, [videosQuery.data?.pages])

  // Extract video IDs from loaded items for WebSocket subscription
  const pageVideoIds = useMemo(() => {
    return items
      .map((v) => (v as unknown as Record<string, unknown>).id)
      .filter((id): id is number => typeof id === 'number')
  }, [items])

  // Subscribe to job events for loaded videos
  const tokens = useAuthTokens()
  const { jobs: wsJobs, hasActiveJobForVideo, getThumbnailTimestamp } = useJobEvents(tokens.accessToken, {
    videoIds: pageVideoIds.length > 0 ? pageVideoIds : null,
    includeActiveState: true,
    autoConnect: pageVideoIds.length > 0,
    onVideoUpdate: useCallback((event: VideoUpdateEvent) => {
    // Only invalidate if video is loaded and non-thumbnail fields changed
      // Thumbnail changes are handled via thumbnailTimestamp cache-busting
      if (pageVideoIds.includes(event.video_id)) {
        const nonThumbnailFields = event.fields_changed.filter(f => 
          f !== 'thumbnail' && f !== 'width' && f !== 'height'
        )
        // Only refetch if metadata fields changed (title, artist, status, etc.)
        if (nonThumbnailFields.length > 0) {
          queryClient.invalidateQueries({ queryKey: videosKeys.all })
        }
      }
    }, [pageVideoIds, queryClient]),
  })

  // Build job status map for VideoCard components
  const getJobStatusForVideo = useCallback((videoId: number): VideoCardJobStatus => {
    const hasActive = hasActiveJobForVideo(videoId)
    // Find the most relevant job for this video
    let relevantJob = undefined
    for (const job of wsJobs.values()) {
      if (job.metadata?.video_id === videoId) {
        relevantJob = job
        break
      }
    }
    return {
      hasActiveJob: hasActive,
      jobStatus: relevantJob?.status,
      jobProgress: relevantJob?.progress,
    }
  }, [wsJobs, hasActiveJobForVideo])

  // Refetch videos when a job completes or fails
  useEffect(() => {
    // Check for any terminal job events
    for (const job of wsJobs.values()) {
      const jobVideoId = job.metadata?.video_id
      if (typeof jobVideoId !== 'number') continue
      if (!pageVideoIds.includes(jobVideoId)) continue

      if (job.status === 'completed' || job.status === 'failed') {
        // Refetch to get updated video state
        queryClient.invalidateQueries({ queryKey: videosKeys.all })
        break
      }
    }
  }, [wsJobs, pageVideoIds, queryClient])

  function resetFilters() {
    setFilters({})
  }

  // Selection management
  function toggleSelection(id: number) {
    setSelectedVideoIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAll() {
    setSelectedVideoIds(new Set(items.map((v) => {
      const id = (v as unknown as Record<string, unknown>).id
      return typeof id === 'number' ? id : 0
    }).filter(id => id !== 0)))
  }

  function clearSelection() {
    setSelectedVideoIds(new Set())
  }

  // Bulk operation handlers
  async function handleBulkTags(addTags: string[], removeTags: string[]) {
    try {
      // TODO: Replace with actual API call when endpoint is available
      // await bulkUpdateTags(Array.from(selectedVideoIds), addTags, removeTags)

      toast.success(
        `Tags updated for ${selectedVideoIds.size} video${selectedVideoIds.size !== 1 ? 's' : ''}`,
        {
          description: `Added: ${addTags.join(', ') || 'none'} | Removed: ${removeTags.join(', ') || 'none'}`,
        }
      )

      // Invalidate queries to refresh the video list
      await queryClient.invalidateQueries({ queryKey: videosKeys.all })

      setBulkTagModalOpen(false)
      clearSelection()
    } catch (error) {
      toast.error('Failed to update tags', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    }
  }

  function handleBulkWriteNFO() {
    // TODO: Implement bulk NFO write
    toast.info(`Writing NFO files for ${selectedVideoIds.size} videos...`)
    console.log('Write NFO for', selectedVideoIds.size, 'videos')
  }

  function handleBulkOrganize() {
    // TODO: Implement bulk organize
    toast.info(`Organizing ${selectedVideoIds.size} videos...`)
    console.log('Organize', selectedVideoIds.size, 'videos')
  }

  async function handleBulkDownload() {
    const selectedIds = Array.from(selectedVideoIds)

    try {
      const response = await fetch(`${getApiBaseUrl()}/videos/bulk/download`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tokens.accessToken && { Authorization: `Bearer ${tokens.accessToken}` }),
        },
        body: JSON.stringify(selectedIds),
      })

      if (!response.ok) {
        throw new Error('Failed to submit bulk download')
      }

      const result = await response.json()

      if (result.skipped > 0) {
        toast.warning(`Queued ${result.submitted} download(s), skipped ${result.skipped}`, {
          description: 'Some videos lack YouTube IDs',
        })
      } else {
        toast.success(`Queued ${result.submitted} download(s)`, {
          description: 'Check job queue for progress',
        })
      }

      clearSelection()
    } catch (error) {
      toast.error('Bulk download failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    }
  }

  function handleBulkDeleteClick() {
    setShowBulkDeleteConfirm(true)
  }

  function handleBulkDeleteConfirm(deleteFiles?: boolean) {
    bulkDeleteMutation.mutate({
      videoIds: Array.from(selectedVideoIds),
      deleteFiles: deleteFiles ?? false,
    })
    setShowBulkDeleteConfirm(false)
  }

  const renderFacetSection = (
    key: FacetKey,
    label: string,
    items: FacetItem[],
    selectedValues: string[],
    onSelect: (value: string) => void
  ) => {
    const isExpanded = facetExpandedByKey[key]
    const query = facetSearch[key].trim().toLowerCase()
    const selectedSet = new Set(selectedValues)
    const pinnedItems = selectedValues
      .map((value) => items.find((item) => item.value === value) ?? { value, count: 0 })
      .filter((item) => item.value)
    const remainingItems = items.filter((item) => !selectedSet.has(item.value))
    const filteredItems = query
      ? remainingItems.filter((item) =>
          formatFacetValue(item.value).toLowerCase().includes(query)
        )
      : remainingItems
    const visibleItems = isExpanded ? filteredItems : filteredItems.slice(0, FACET_LIMIT)
    const showToggle = isExpanded || filteredItems.length > FACET_LIMIT
    const listId = `facet-popover-${key}`

    const handleSelect = (value: string) => {
      onSelect(value)
    }

    return (
      <div id={listId} className="facetPopover" role="dialog" aria-label={`${label} filters`}>
        <div className="facetPopoverHeader">
          <span className="facetPopoverTitle">{label}</span>
          {showToggle && (
            <button
              type="button"
              className="facetToggle"
              onClick={() =>
                setFacetExpandedByKey((prev) => ({ ...prev, [key]: !prev[key] }))
              }
              aria-expanded={isExpanded}
              aria-controls={listId}
            >
              {isExpanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </div>

        <div className="facetPopoverBody">
          <input
            className="searchInput facetSearchInput facetPopoverSearch"
            type="search"
            value={facetSearch[key]}
            onChange={(event) =>
              setFacetSearch((prev) => ({ ...prev, [key]: event.target.value }))
            }
            placeholder={`Search ${label.toLowerCase()}...`}
            aria-label={`Filter ${label.toLowerCase()} options`}
          />

          {pinnedItems.length > 0 && (
            <div className="facetPinned">
              <div className="facetList facetListPinned">
                {pinnedItems.map((item) => (
                  <button
                    key={`${key}:selected:${item.value}`}
                    type="button"
                    className="facetItem facetItemActive facetItemPinned"
                    onClick={() => handleSelect(item.value)}
                  >
                    {formatFacetValue(item.value)}
                    <span className="facetCount">{item.count}</span>
                  </button>
                ))}
              </div>
              <div className="facetDivider" />
            </div>
          )}

          <div className={`facetList ${isExpanded ? 'facetListExpanded' : ''}`}>
            {visibleItems.map((item) => (
              <button
                key={`${key}:${item.value}`}
                type="button"
                className="facetItem"
                onClick={() => handleSelect(item.value)}
              >
                {formatFacetValue(item.value)}
                <span className="facetCount">{item.count}</span>
              </button>
            ))}
          </div>

          {isExpanded && filteredItems.length === 0 && (
            <div className="facetEmpty">No matching options</div>
          )}
        </div>
      </div>
    )
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && openFacet) {
        setOpenFacet(null)
        return
      }
      // Ctrl+A or Cmd+A to select all
      if ((e.ctrlKey || e.metaKey) && e.key === 'a' && items.length > 0) {
        e.preventDefault()
        selectAll()
      }
      // Esc to clear selection
      if (e.key === 'Escape' && selectedVideoIds.size > 0) {
        clearSelection()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- selectAll is stable, only re-bind when items/selection changes
  }, [items.length, selectedVideoIds.size, openFacet])

  useEffect(() => {
    const loadMoreNode = loadMoreRef.current
    if (!loadMoreNode) return
    if (!hasNextPage) return
    if (typeof window === 'undefined' || !('IntersectionObserver' in window)) return

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0]
        if (first?.isIntersecting && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { rootMargin: '200px' }
    )

    observer.observe(loadMoreNode)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const activeYearValues = (filters.year ?? []).map((year) =>
    year === YEAR_NONE_SENTINEL ? FACET_NONE_VALUE : String(year)
  )

  const hasActiveFilters = Boolean(
    (filters.tag_name?.length ?? 0) > 0 ||
    (filters.genre?.length ?? 0) > 0 ||
    (filters.year?.length ?? 0) > 0
  )

  return (
    <div className="libraryPage">
      <PageHeader
        title="Video Library"
        iconSrc="/fuzzbin-icon.png"
        iconAlt="Fuzzbin"
        accent="var(--channel-library)"
        actions={
          <div className="libraryControls">
            <input
              className="searchInput"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search videos…"
              aria-label="Search videos"
            />

            <select className="select" value={sortBy} onChange={(e) => setSortBy(e.target.value)} aria-label="Sort by">
              <option value="created_at">Created</option>
              <option value="title">Title</option>
              <option value="artist">Artist</option>
              <option value="year">Year</option>
            </select>

            <button
              className="primaryButton"
              type="button"
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              aria-label="Toggle sort order"
            >
              {sortOrder === 'asc' ? 'Asc' : 'Desc'}
            </button>

            <div className="viewToggle">
              <button
                className={`viewToggleButton ${viewMode === 'grid' ? 'viewToggleButtonActive' : ''}`}
                type="button"
                onClick={() => setViewMode('grid')}
                aria-label="Grid view"
                aria-pressed={viewMode === 'grid'}
              >
                Grid
              </button>
              <button
                className={`viewToggleButton ${viewMode === 'table' ? 'viewToggleButtonActive' : ''}`}
                type="button"
                onClick={() => setViewMode('table')}
                aria-label="Table view"
                aria-pressed={viewMode === 'table'}
              >
                Table
              </button>
            </div>
          </div>
        }
        navItems={[
          { label: 'Library', to: '/library' },
          { label: 'Import', to: '/add' },
          { label: 'Activity', to: '/activity' },
          { label: 'Settings', to: '/settings' },
        ]}
      />

      <main className="libraryMain">
        <section className="panelCard libraryFacetsBar" aria-label="Filters">
          <div className="libraryFacetsBarRow" ref={facetBarRef}>
            <div className="libraryFacetsBarTitle">
              <h2 className="sectionTitle" style={{ marginBottom: 0 }}>
                Filters
              </h2>
              {hasActiveFilters && (
                <button className="facetClearButton" type="button" onClick={resetFilters}>
                  Clear
                </button>
              )}
            </div>

            <div className="libraryFacetButtons">
              {([
                { key: 'tags', label: 'Tags', items: facets.tags, selected: filters.tag_name ?? [] },
                { key: 'genres', label: 'Genres', items: facets.genres, selected: filters.genre ?? [] },
                { key: 'years', label: 'Years', items: yearFacetItems, selected: activeYearValues },
              ] as Array<{ key: FacetKey; label: string; items: FacetItem[]; selected: string[] }>).map(
                ({ key, label, items, selected }) => {
                  const isOpen = openFacet === key
                  const isActive = selected.length > 0
                  const displayValue = getFacetDisplay(selected)
                  const disableFacet = facetsQuery.isLoading || facetsQuery.isError

                  const handleSelect = (value: string) => {
                    if (key === 'tags') {
                      setFilters((prev) => ({
                        ...prev,
                        tag_name: updateListFilter(prev.tag_name, value),
                      }))
                      return
                    }
                    if (key === 'genres') {
                      setFilters((prev) => ({
                        ...prev,
                        genre: updateListFilter(prev.genre, value),
                      }))
                      return
                    }
                    if (key === 'years') {
                      const year = value === FACET_NONE_VALUE ? YEAR_NONE_SENTINEL : Number(value)
                      if (!Number.isFinite(year)) return
                      setFilters((prev) => ({
                        ...prev,
                        year: updateListFilter(prev.year, year),
                      }))
                    }
                  }

                  return (
                    <div key={key} className="libraryFacetGroup">
                      <button
                        type="button"
                        className={`libraryFacetButton ${isActive ? 'libraryFacetButtonActive' : ''}`}
                        onClick={() => setOpenFacet((prev) => (prev === key ? null : key))}
                        aria-expanded={isOpen}
                        aria-controls={`facet-popover-${key}`}
                        aria-label={`${label} filters`}
                        disabled={disableFacet}
                      >
                        <span className="libraryFacetButtonLabel">{label}</span>
                        {displayValue && <span className="libraryFacetButtonValue">{displayValue}</span>}
                        <span className="libraryFacetButtonCaret" aria-hidden="true">▾</span>
                      </button>
                      {isOpen && !disableFacet && renderFacetSection(key, label, items, selected, handleSelect)}
                    </div>
                  )
                }
              )}
            </div>

            {viewMode === 'table' && (
              <label className="libraryColumnsControl">
                <span className="libraryColumnsLabel">Columns</span>
                <select
                  className="select libraryColumnsSelect"
                  value={tableColumns}
                  onChange={(event) => setTableColumns(event.target.value as LibraryTableColumns)}
                  aria-label="Select table columns"
                >
                  <option value="full">Full</option>
                  <option value="core">Core (Title, Artist, Album, Genre)</option>
                  <option value="curation">Curation (Genre, ISRC, Tags)</option>
                </select>
              </label>
            )}

            <div className="libraryFacetsBarStatus">
              {facetsQuery.isLoading ? <span className="statusLine">Loading filters…</span> : null}
              {facetsQuery.isError ? <span className="statusLine">Filters unavailable</span> : null}
            </div>
          </div>
        </section>

        <section className="panelCard libraryVideos" aria-label="Videos">
          {videosQuery.isLoading ? <div className="statusLine">Loading videos…</div> : null}
          {videosQuery.isError ? <div className="statusLine">Videos unavailable</div> : null}

          {!videosQuery.isLoading && !videosQuery.isError && items.length === 0 ? (
            <div className="statusLine">No videos found</div>
          ) : null}

          {!videosQuery.isLoading && !videosQuery.isError && items.length > 0 ? (
            <>
              {viewMode === 'grid' ? (
                <VideoGrid>
                  {items.map((v) => {
                    const id = (v as unknown as Record<string, unknown>).id
                    const videoId = typeof id === 'number' ? id : 0
                    const key = typeof id === 'number' || typeof id === 'string' ? String(id) : JSON.stringify(v)
                    return (
                      <VideoCard
                        key={key}
                        video={v}
                        selectable
                        selected={selectedVideoIds.has(videoId)}
                        onToggleSelection={toggleSelection}
                        onClick={() => setDetailsModalVideo(v)}
                        onPlay={setPlayerVideo}
                        jobStatus={videoId ? getJobStatusForVideo(videoId) : undefined}
                        thumbnailTimestamp={videoId ? getThumbnailTimestamp(videoId) : undefined}
                      />
                    )
                  })}
                </VideoGrid>
              ) : (
                <LibraryTable
                  videos={items}
                  selectedIds={selectedVideoIds}
                  columns={tableColumns}
                  onToggleSelection={toggleSelection}
                  onSelectAll={selectAll}
                  onClearAll={clearSelection}
                  onVideoClick={(video) => setDetailsModalVideo(video)}
                  onPlayVideo={setPlayerVideo}
                />
              )}

              <div className="libraryLoadMore" ref={loadMoreRef}>
                {videosQuery.isFetchingNextPage ? (
                  <div className="statusLine">Loading more…</div>
                ) : videosQuery.hasNextPage ? (
                  <div className="statusLine">Scroll for more</div>
                ) : null}
              </div>
            </>
          ) : null}
        </section>
      </main>

      {selectedVideoIds.size > 0 && (
        <MultiSelectToolbar
          count={selectedVideoIds.size}
          onAddTags={() => setBulkTagModalOpen(true)}
          onRemoveTags={() => setBulkTagModalOpen(true)}
          onWriteNFO={handleBulkWriteNFO}
          onOrganize={handleBulkOrganize}
          onDownload={handleBulkDownload}
          onDelete={handleBulkDeleteClick}
          onClear={clearSelection}
        />
      )}

      {bulkTagModalOpen && (
        <BulkTagModal
          count={selectedVideoIds.size}
          availableTags={facets.tags
            .filter((t) => t.value !== FACET_NONE_VALUE)
            .map((t) => t.value)}
          onApply={handleBulkTags}
          onCancel={() => setBulkTagModalOpen(false)}
        />
      )}

      {detailsModalVideo && (
        <VideoDetailsModal
          video={detailsModalVideo}
          onClose={() => setDetailsModalVideo(null)}
          thumbnailTimestamp={
            typeof (detailsModalVideo as Record<string, unknown>).id === 'number'
              ? getThumbnailTimestamp((detailsModalVideo as Record<string, unknown>).id as number)
              : undefined
          }
        />
      )}

      {playerVideo && (
        <VideoPlayerModal
          video={playerVideo}
          onClose={() => setPlayerVideo(null)}
        />
      )}

      {showBulkDeleteConfirm && (
        <ConfirmDialog
          title="Delete Videos"
          message={`Are you sure you want to delete ${selectedVideoIds.size} video${selectedVideoIds.size !== 1 ? 's' : ''}?`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          variant="danger"
          checkboxLabel="Also delete video files from disk (cannot be undone)"
          checkboxDefaultChecked={false}
          onConfirm={handleBulkDeleteConfirm}
          onCancel={() => setShowBulkDeleteConfirm(false)}
        />
      )}
    </div>
  )
}
