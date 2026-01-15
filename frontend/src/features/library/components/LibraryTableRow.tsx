import type { Video } from '../../../lib/api/types'
import type { LibraryTableColumns } from './LibraryTable'

interface LibraryTableRowProps {
  video: Video
  selected: boolean
  columns: LibraryTableColumns
  onToggleSelection: (id: number) => void
  onVideoClick: (video: Video) => void
  onPlayVideo?: (video: Video) => void
}

function formatDuration(seconds: unknown): string {
  const sec = typeof seconds === 'number' && Number.isFinite(seconds) ? Math.max(0, Math.round(seconds)) : null
  if (sec === null) return '—'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function getFeaturedArtists(video: Video): string {
  const anyVideo = video as unknown as Record<string, unknown>
  const artists = Array.isArray(anyVideo.artists) ? anyVideo.artists : []

  const featured = artists
    .filter((a: unknown) => {
      if (!a || typeof a !== 'object') return false
      const artist = a as Record<string, unknown>
      return artist.role === 'featured'
    })
    .map((a: unknown) => {
      const artist = a as Record<string, unknown>
      return typeof artist.name === 'string' ? artist.name : ''
    })
    .filter(Boolean)

  return featured.join(', ')
}

function getTagLabels(video: Video): string[] {
  const anyVideo = video as unknown as Record<string, unknown>
  const tags = Array.isArray(anyVideo.tags) ? anyVideo.tags : []

  return tags
    .map((tag: unknown) => {
      if (!tag || typeof tag !== 'object') return null
      const tagObj = tag as Record<string, unknown>
      const label = tagObj.name ?? tagObj.tag_name ?? tagObj.value
      return typeof label === 'string' && label.trim().length > 0 ? label.trim() : null
    })
    .filter((t): t is string => Boolean(t))
}

export default function LibraryTableRow({
  video,
  selected,
  columns,
  onToggleSelection,
  onVideoClick,
  onPlayVideo,
}: LibraryTableRowProps) {
  const anyVideo = video as Record<string, unknown>
  const videoId = typeof anyVideo.id === 'number' ? anyVideo.id : 0
  const title = (typeof anyVideo.title === 'string' && anyVideo.title.trim().length > 0 ? anyVideo.title : 'Untitled') as string
  const artist = (typeof anyVideo.artist === 'string' && anyVideo.artist.trim().length > 0 ? anyVideo.artist : '—') as string
  const album = typeof anyVideo.album === 'string' ? anyVideo.album : '—'
  const year = typeof anyVideo.year === 'number' ? String(anyVideo.year) : '—'
  const director = typeof anyVideo.director === 'string' ? anyVideo.director : '—'
  const studio = typeof anyVideo.studio === 'string' ? anyVideo.studio : '—'
  const genre = typeof anyVideo.genre === 'string' && anyVideo.genre.trim().length > 0 ? anyVideo.genre : '—'
  const isrc = typeof anyVideo.isrc === 'string' && anyVideo.isrc.trim().length > 0 ? anyVideo.isrc : '—'
  const tags = getTagLabels(video)
  const tagsLabel = tags.length > 0 ? tags.join(', ') : '—'
  const duration = formatDuration(anyVideo.duration)
  const featuredArtists = getFeaturedArtists(video)
  const showFull = columns === 'full'
  const showCore = columns === 'core'
  const showCuration = columns === 'curation'

  const handleRowClick = () => {
    onVideoClick(video)
  }

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation()
  }

  const handleCheckboxChange = () => {
    onToggleSelection(videoId)
  }

  return (
    <div
      className={`libraryTableRow ${selected ? 'libraryTableRowSelected' : ''}`}
      onClick={handleRowClick}
      role="row"
      aria-selected={selected}
    >
      <div className="libraryTableCell" onClick={handleCheckboxClick}>
        <input
          type="checkbox"
          checked={selected}
          onChange={handleCheckboxChange}
          aria-label={`Select ${title}`}
        />
      </div>

      <div className="libraryTableCell">
        <div className="libraryTableCellPrimary">{artist}</div>
        {featuredArtists && (
          <div className="libraryTableCellSecondary">ft. {featuredArtists}</div>
        )}
      </div>

      <div className="libraryTableCell">
        <div className="libraryTableCellPrimary" title={title}>{title}</div>
      </div>

      {(showFull || showCore) && (
        <div className="libraryTableCell">
          <div className="libraryTableCellPrimary" title={album}>{album}</div>
        </div>
      )}

      {showFull && (
        <div className="libraryTableCell libraryTableCellCenter">
          {year}
        </div>
      )}

      {showFull && (
        <div className="libraryTableCell libraryTableCellHideTablet">
          <div className="libraryTableCellPrimary" title={director}>{director}</div>
        </div>
      )}

      {showFull && (
        <div className="libraryTableCell libraryTableCellHideTablet">
          <div className="libraryTableCellPrimary" title={studio}>{studio}</div>
        </div>
      )}

      {showFull && (
        <div className="libraryTableCell libraryTableCellCenter">
          {duration}
        </div>
      )}

      {showCore && (
        <div className="libraryTableCell">
          <div className="libraryTableCellPrimary" title={genre}>{genre}</div>
        </div>
      )}

      {showCuration && (
        <div className="libraryTableCell">
          <div className="libraryTableCellPrimary" title={genre}>{genre}</div>
        </div>
      )}

      {showCuration && (
        <div className="libraryTableCell libraryTableCellCenter">
          {isrc}
        </div>
      )}

      {showCuration && (
        <div className="libraryTableCell">
          <div className="libraryTableCellPrimary" title={tagsLabel}>{tagsLabel}</div>
        </div>
      )}

      <div className="libraryTableCell libraryTableActions">
        {onPlayVideo && (
          <button
            className="libraryTableActionButton"
            onClick={(e) => {
              e.stopPropagation()
              onPlayVideo(video)
            }}
            aria-label="Play video"
            title="Play video"
          >
            ▶
          </button>
        )}
        <button
          className="libraryTableActionButton"
          onClick={(e) => {
            e.stopPropagation()
            onVideoClick(video)
          }}
          aria-label="View details"
          title="View details"
        >
          ⋯
        </button>
      </div>
    </div>
  )
}
