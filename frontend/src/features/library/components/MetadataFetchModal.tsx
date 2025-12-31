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
  source: 'imvdb' | 'discogs_master' | 'discogs_release'
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
}

export default function MetadataFetchModal({
  artist,
  title,
  source,
  onApply,
  onClose,
}: MetadataFetchModalProps) {
  const [selectedResult, setSelectedResult] = useState<AddSearchResultItem | null>(null)
  const [previewData, setPreviewData] = useState<AddPreviewResponse | null>(null)

  const sourceName = source === 'imvdb' ? 'IMVDb' : 'Discogs'

  // Search mutation
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
    searchMutation.mutate()
  }

  const handleSelectResult = (item: AddSearchResultItem) => {
    setSelectedResult(item)
    previewMutation.mutate(item)
  }

  const handleApply = () => {
    if (!previewData) return

    const anyPreview = previewData as unknown as Record<string, unknown>
    const metadata: Partial<MetadataUpdate> = {}

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
            ×
          </button>
        </div>

        <div className="metadataFetchModalBody">
          {!searchMutation.data && !searchMutation.isPending && (
            <div className="metadataFetchEmptyState">
              <p className="metadataFetchEmptyText">
                Search {sourceName} for metadata matching:
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
              </div>
              <button
                type="button"
                className="metadataFetchButton metadataFetchButtonPrimary"
                onClick={handleSearch}
              >
                Search {sourceName}
              </button>
            </div>
          )}

          {searchMutation.isPending && (
            <div className="metadataFetchLoading">Searching {sourceName}...</div>
          )}

          {searchMutation.data && results.length === 0 && (
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

          {selectedResult && previewData && (
            <div className="metadataFetchPreviewSection">
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
