import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { addSearch, addPreview } from '../../../lib/api/endpoints/add'
import type { AddSearchResponse, AddPreviewResponse } from '../../../lib/api/types'
import './MetadataFetchModal.css'

type AddSearchResultItem = NonNullable<AddSearchResponse['results']>[number]

interface MetadataFetchModalProps {
  artist: string
  title: string
  isrc?: string
  videoId?: number
  source: 'imvdb' | 'discogs_master' | 'discogs_release' | 'musicbrainz'
  onApply: (metadata: Partial<MetadataUpdate>) => void
  onClose: () => void
}

interface MetadataUpdate {
  title: string
  artist: string
  album: string
  year: number
  genre: string
  director: string
  studio: string
  imvdb_url: string
  imvdb_video_id: string
}

export default function MetadataFetchModal({
  artist,
  title,
  isrc,
  videoId,
  source,
  onApply,
  onClose,
}: MetadataFetchModalProps) {
  const [selectedResult, setSelectedResult] = useState<AddSearchResultItem | null>(null)
  const [previewData, setPreviewData] = useState<AddPreviewResponse | null>(null)

  const sourceName = source === 'imvdb' ? 'IMVDb' : source === 'musicbrainz' ? 'MusicBrainz' : 'Discogs'
  const isMusicBrainz = source === 'musicbrainz'

  // MusicBrainz enrichment mutation (direct enrichment, no search)
  const musicbrainzEnrichMutation = useMutation({
    mutationFn: async () => {
      if (!videoId) {
        throw new Error('Video ID is required for MusicBrainz enrichment')
      }
      
      const response = await fetch(`/api/videos/${videoId}/enrich/musicbrainz`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          isrc: isrc || null,
          title: title || null,
          artist: artist || null,
        }),
      })
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(error.detail || 'Failed to enrich from MusicBrainz')
      }
      
      return await response.json()
    },
    onSuccess: (data) => {
      const anyData = data as Record<string, unknown>
      // Check if we got valid results (confident_match or any metadata)
      if (anyData.match_method === 'none' || (!anyData.album && !anyData.year && !anyData.genre)) {
        toast.error('No MusicBrainz results found', {
          description: 'Try adjusting the title, artist, or ISRC',
        })
        return
      }
      setPreviewData(data as unknown as AddPreviewResponse)
    },
    onError: (error) => {
      toast.error('Failed to enrich from MusicBrainz', {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  // Search mutation (for IMVDb and Discogs)
  const searchMutation = useMutation({
    mutationFn: async () => {
      const response = await addSearch({
        artist,
        track_title: title,
        include_sources: [source],
        imvdb_per_page: 10,
        discogs_per_page: 10,
        youtube_max_results: 5,
      })
      return response
    },
    onError: (error) => {
      toast.error(`Failed to search ${sourceName}`, {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: async (item: AddSearchResultItem) => {
      const response = await addPreview(item.source, item.id)
      return response
    },
    onSuccess: (data) => {
      setPreviewData(data)
    },
    onError: (error) => {
      toast.error(`Failed to fetch ${sourceName} details`, {
        description: error instanceof Error ? error.message : 'Unknown error',
      })
    },
  })

  const handleSearch = () => {
    if (isMusicBrainz) {
      musicbrainzEnrichMutation.mutate()
    } else {
      searchMutation.mutate()
    }
  }

  const handleSelectResult = (item: AddSearchResultItem) => {
    setSelectedResult(item)
    previewMutation.mutate(item)
  }

  const handleApply = () => {
    if (!previewData) return

    const anyPreview = previewData as unknown as Record<string, unknown>
    const metadata: Partial<MetadataUpdate> = {}

    // Handle MusicBrainz response format
    if (isMusicBrainz) {
      if (typeof anyPreview.canonical_title === 'string' && anyPreview.canonical_title.trim()) {
        metadata.title = anyPreview.canonical_title.trim()
      }
      if (typeof anyPreview.canonical_artist === 'string' && anyPreview.canonical_artist.trim()) {
        metadata.artist = anyPreview.canonical_artist.trim()
      }
      if (typeof anyPreview.album === 'string' && anyPreview.album.trim()) {
        metadata.album = anyPreview.album.trim()
      }
      if (typeof anyPreview.year === 'number') {
        metadata.year = anyPreview.year
      }
      if (typeof anyPreview.genre === 'string' && anyPreview.genre.trim()) {
        metadata.genre = anyPreview.genre.trim()
      }
      if (typeof anyPreview.label === 'string' && anyPreview.label.trim()) {
        metadata.studio = anyPreview.label.trim()
      }
    } else {
      // Handle IMVDb/Discogs response format
      const previewDataObj = anyPreview.data as Record<string, unknown> | undefined
      
      if (typeof anyPreview.title === 'string' && anyPreview.title.trim()) {
        metadata.title = anyPreview.title.trim()
      }
      if (typeof anyPreview.artist === 'string' && anyPreview.artist.trim()) {
        metadata.artist = anyPreview.artist.trim()
      }
      if (typeof anyPreview.album === 'string' && anyPreview.album.trim()) {
        metadata.album = anyPreview.album.trim()
      }
      if (typeof anyPreview.year === 'number') {
        metadata.year = anyPreview.year
      }
      if (typeof anyPreview.genre === 'string' && anyPreview.genre.trim()) {
        metadata.genre = anyPreview.genre.trim()
      }
      if (typeof anyPreview.director === 'string' && anyPreview.director.trim()) {
        metadata.director = anyPreview.director.trim()
      }
      if (typeof anyPreview.studio === 'string' && anyPreview.studio.trim()) {
        metadata.studio = anyPreview.studio.trim()
      }

      // Extract IMVDb URL and ID from preview data (IMVDb-specific)
      if (previewDataObj) {
        if (typeof previewDataObj.url === 'string' && previewDataObj.url.trim()) {
          metadata.imvdb_url = previewDataObj.url.trim()
        }
        if (typeof previewDataObj.id === 'number') {
          metadata.imvdb_video_id = String(previewDataObj.id)
        } else if (typeof previewDataObj.id === 'string' && previewDataObj.id.trim()) {
          metadata.imvdb_video_id = previewDataObj.id.trim()
        }
      }
    }

    onApply(metadata)
    onClose()
  }

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    }
  }

  const results = (searchMutation.data?.results ?? []) as AddSearchResultItem[]

  return (
    <div
      className="metadataFetchModalOverlay"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="metadata-fetch-title"
    >
      <div className="metadataFetchModal">
        <div className="metadataFetchModalHeader">
          <h2 id="metadata-fetch-title" className="metadataFetchModalTitle">
            Fetch from {sourceName}
          </h2>
          <button
            type="button"
            className="metadataFetchModalClose"
            onClick={onClose}
            aria-label="Close"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="metadataFetchModalBody">
          {!previewData && !searchMutation.isPending && !musicbrainzEnrichMutation.isPending && (
            <div className="metadataFetchEmptyState">
              <p className="metadataFetchEmptyText">
                {isMusicBrainz ? 'Enrich' : 'Search'} {sourceName} for metadata matching:
              </p>
              <div className="metadataFetchSearchInfo">
                <div className="metadataFetchSearchField">
                  <span className="metadataFetchSearchLabel">Artist:</span>
                  <span className="metadataFetchSearchValue">{artist || '—'}</span>
                </div>
                <div className="metadataFetchSearchField">
                  <span className="metadataFetchSearchLabel">Title:</span>
                  <span className="metadataFetchSearchValue">{title || '—'}</span>
                </div>
                {isMusicBrainz && (
                  <div className="metadataFetchSearchField">
                    <span className="metadataFetchSearchLabel">ISRC:</span>
                    <span className="metadataFetchSearchValue">{isrc || '—'}</span>
                  </div>
                )}
              </div>
              <button
                type="button"
                className="metadataFetchButton metadataFetchButtonPrimary"
                onClick={handleSearch}
              >
                {isMusicBrainz ? 'Enrich from' : 'Search'} {sourceName}
              </button>
            </div>
          )}

          {(searchMutation.isPending || musicbrainzEnrichMutation.isPending) && (
            <div className="metadataFetchLoading">{isMusicBrainz ? 'Enriching from' : 'Searching'} {sourceName}...</div>
          )}

          {searchMutation.data && results.length === 0 && !isMusicBrainz && (
            <div className="metadataFetchEmptyState">
              <p className="metadataFetchEmptyText">No results found on {sourceName}</p>
              <button
                type="button"
                className="metadataFetchButton metadataFetchButtonSecondary"
                onClick={handleSearch}
              >
                Search Again
              </button>
            </div>
          )}

          {searchMutation.data && results.length > 0 && !selectedResult && (
            <div className="metadataFetchResultsSection">
              <h3 className="metadataFetchSectionTitle">
                {results.length} result{results.length !== 1 ? 's' : ''} found
              </h3>
              <div className="metadataFetchResults">
                {results.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="metadataFetchResultItem"
                    onClick={() => handleSelectResult(item)}
                  >
                    <div className="metadataFetchResultTitle">{item.title}</div>
                    {item.artist && (
                      <div className="metadataFetchResultArtist">{item.artist}</div>
                    )}
                    <div className="metadataFetchResultMeta">
                      {item.year && <span>{item.year}</span>}
                      {item.source && (
                        <span className="metadataFetchResultSource">{item.source}</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {selectedResult && previewMutation.isPending && (
            <div className="metadataFetchLoading">Loading preview...</div>
          )}

          {previewData && (
            <div className="metadataFetchPreviewSection">
              {!isMusicBrainz && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 className="metadataFetchSectionTitle">Preview</h3>
                  <button
                    type="button"
                    className="metadataFetchButton metadataFetchButtonSecondary"
                    onClick={() => {
                      setSelectedResult(null)
                      setPreviewData(null)
                    }}
                  >
                    Back to Results
                  </button>
                </div>
              )}

              {isMusicBrainz && (
                <div>
                  <h3 className="metadataFetchSectionTitle">MusicBrainz Enrichment Result</h3>
                  {(previewData as Record<string, unknown>).match_method && (
                    <div style={{ marginBottom: 'var(--space-3)', fontSize: '0.875rem', color: 'var(--color-text-secondary, #6b7280)' }}>
                      <div>Match method: {String((previewData as Record<string, unknown>).match_method)}</div>
                      {typeof (previewData as Record<string, unknown>).match_score === 'number' && (
                        <div>Match score: {((previewData as Record<string, unknown>).match_score as number).toFixed(1)}%</div>
                      )}
                      {(previewData as Record<string, unknown>).confident_match === false && (
                        <div style={{ color: 'var(--color-warning, #f59e0b)' }}>⚠️ Low confidence match - please review carefully</div>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div className="metadataFetchPreviewGrid">
                {Object.entries(previewData as Record<string, unknown>)
                  .filter(([key, value]) => {
                    if (key === 'source' || key === 'id') return false
                    if (value === null || value === undefined) return false
                    if (typeof value === 'string' && !value.trim()) return false
                    return true
                  })
                  .map(([key, value]) => (
                    <div key={key} className="metadataFetchPreviewField">
                      <div className="metadataFetchPreviewLabel">
                        {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                      </div>
                      <div className="metadataFetchPreviewValue">
                        {typeof value === 'object'
                          ? JSON.stringify(value, null, 2)
                          : String(value)}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        <div className="metadataFetchModalFooter">
          <button
            type="button"
            className="metadataFetchButton metadataFetchButtonSecondary"
            onClick={onClose}
          >
            Cancel
          </button>
          {previewData && (
            <button
              type="button"
              className="metadataFetchButton metadataFetchButtonPrimary"
              onClick={handleApply}
            >
              Apply Metadata
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
