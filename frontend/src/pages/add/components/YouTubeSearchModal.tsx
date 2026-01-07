import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { searchYouTube } from '../../../lib/api/endpoints/spotify'
import type { AddSearchResponse } from '../../../lib/api/types'

interface YouTubeSearchModalProps {
  artist: string
  trackTitle: string
  onSelect: (youtubeId: string, youtubeUrl: string) => void
  onCancel: () => void
}

export default function YouTubeSearchModal({
  artist,
  trackTitle,
  onSelect,
  onCancel,
}: YouTubeSearchModalProps) {
  const [searchQuery, setSearchQuery] = useState(`${artist} ${trackTitle}`)

  // Auto-search on mount
  const searchResults = useQuery<AddSearchResponse>({
    queryKey: ['youtube-search', artist, trackTitle],
    queryFn: () =>
      searchYouTube({
        artist,
        track_title: trackTitle,
        max_results: 10,
      }),
  })

  const handleSelect = (youtubeId: string, url: string) => {
    onSelect(youtubeId, url)
  }

  const handleManualSearch = () => {
    // For manual search, we'd need to update the query
    // For now, this is a placeholder
    searchResults.refetch()
  }

  return (
    <div className="youtubeSearchModal">
      <div className="youtubeSearchModalOverlay" onClick={onCancel} />
      <div className="youtubeSearchModalContent" onClick={(e) => e.stopPropagation()}>
        <div className="youtubeSearchModalHeader">
          <h2 className="youtubeSearchModalTitle">Search YouTube</h2>
          <button type="button" className="youtubeSearchModalClose" onClick={onCancel}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="youtubeSearchModalBody">
          {/* Search input */}
          <div className="youtubeSearchModalSearch">
            <input
              type="text"
              className="youtubeSearchModalInput"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Refine search..."
            />
            <button
              type="button"
              className="youtubeSearchModalSearchButton"
              onClick={handleManualSearch}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <path d="M21 21l-4.35-4.35" />
              </svg>
            </button>
          </div>

          {/* Results */}
          {searchResults.isLoading && (
            <div className="youtubeSearchModalLoading">Searching YouTube...</div>
          )}

          {searchResults.isError && (
            <div className="youtubeSearchModalError">
              Failed to search YouTube. Please try again.
            </div>
          )}

          {searchResults.data && (
            <div className="youtubeSearchModalResults">
              {(searchResults.data.results ?? []).length === 0 && (
                <div className="youtubeSearchModalEmpty">No results found</div>
              )}

              {(searchResults.data.results ?? []).map((result) => (
                <div
                  key={result.id}
                  className="youtubeSearchModalResult"
                  onClick={() => handleSelect(result.id, result.url || '')}
                >
                  {/* Thumbnail */}
                  {result.thumbnail && (
                    <div className="youtubeSearchModalThumbnail">
                      <img src={result.thumbnail} alt={result.title} />
                      <div className="youtubeSearchModalPlayIcon">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                          <polygon points="5 3 19 12 5 21 5 3" />
                        </svg>
                      </div>
                    </div>
                  )}

                  {/* Info */}
                  <div className="youtubeSearchModalInfo">
                    <div className="youtubeSearchModalResultTitle">{result.title}</div>
                    <div className="youtubeSearchModalMeta">
                      {result.extra && typeof result.extra === 'object' && 'channel' in result.extra && (
                        <span className="youtubeSearchModalChannel">{String(result.extra.channel)}</span>
                      )}
                      {result.extra && typeof result.extra === 'object' && 'view_count' in result.extra && typeof result.extra.view_count === 'number' && (
                        <span className="youtubeSearchModalViews">
                          {formatViewCount(result.extra.view_count)}
                        </span>
                      )}
                      {result.extra && typeof result.extra === 'object' && 'duration' in result.extra && typeof result.extra.duration === 'number' && (
                        <span className="youtubeSearchModalDuration">
                          {formatDuration(result.extra.duration)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="youtubeSearchModalFooter">
          <button type="button" className="youtubeSearchModalButton" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}

function formatViewCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M views`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K views`
  }
  return `${count} views`
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }
  return `${minutes}:${String(secs).padStart(2, '0')}`
}
