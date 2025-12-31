import type { Video } from '../../../lib/api/types'

interface LibraryTableRowProps {
  video: Video
  selected: boolean
  onToggleSelection: (id: number) => void
  onVideoClick: (video: Video) => void
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

export default function LibraryTableRow({
  video,
  selected,
  onToggleSelection,
  onVideoClick,
}: LibraryTableRowProps) {
  const anyVideo = video as Record<string, unknown>
  const videoId = typeof anyVideo.id === 'number' ? anyVideo.id : 0
  const title = (typeof anyVideo.title === 'string' && anyVideo.title.trim().length > 0 ? anyVideo.title : 'Untitled') as string
  const artist = (typeof anyVideo.artist === 'string' && anyVideo.artist.trim().length > 0 ? anyVideo.artist : '—') as string
  const album = typeof anyVideo.album === 'string' ? anyVideo.album : '—'
  const year = typeof anyVideo.year === 'number' ? String(anyVideo.year) : '—'
  const director = typeof anyVideo.director === 'string' ? anyVideo.director : '—'
  const studio = typeof anyVideo.studio === 'string' ? anyVideo.studio : '—'
  const duration = formatDuration(anyVideo.duration)
  const featuredArtists = getFeaturedArtists(video)

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

      <div className="libraryTableCell">
        <div className="libraryTableCellPrimary" title={album}>{album}</div>
      </div>

      <div className="libraryTableCell libraryTableCellCenter">
        {year}
      </div>

      <div className="libraryTableCell libraryTableCellHideTablet">
        <div className="libraryTableCellPrimary" title={director}>{director}</div>
      </div>

      <div className="libraryTableCell libraryTableCellHideTablet">
        <div className="libraryTableCellPrimary" title={studio}>{studio}</div>
      </div>

      <div className="libraryTableCell libraryTableCellCenter">
        {duration}
      </div>

      <div className="libraryTableCell">
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
