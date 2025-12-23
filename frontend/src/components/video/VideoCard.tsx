import './video.css'
import type { Video } from '../../lib/api/types'

function formatDuration(seconds: unknown): string {
  const sec = typeof seconds === 'number' && Number.isFinite(seconds) ? Math.max(0, Math.round(seconds)) : null
  if (sec === null) return '—'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function getTagLabel(tag: unknown): string | null {
  if (!tag || typeof tag !== 'object') return null
  const anyTag = tag as Record<string, unknown>
  const label = anyTag.name ?? anyTag.tag_name ?? anyTag.value
  return typeof label === 'string' && label.trim().length > 0 ? label.trim() : null
}

export default function VideoCard({ video }: { video: Video }) {
  const anyVideo = video as Record<string, unknown>
  const title = (typeof anyVideo.title === 'string' && anyVideo.title.trim().length > 0 ? anyVideo.title : 'Untitled') as string
  const artist = (typeof anyVideo.artist === 'string' && anyVideo.artist.trim().length > 0 ? anyVideo.artist : '—') as string
  const year = typeof anyVideo.year === 'number' ? String(anyVideo.year) : null
  const duration = formatDuration(anyVideo.duration)
  const status = typeof anyVideo.status === 'string' ? anyVideo.status : null

  const tagsRaw = Array.isArray(anyVideo.tags) ? anyVideo.tags : []
  const tags = tagsRaw.map(getTagLabel).filter((t): t is string => Boolean(t)).slice(0, 3)

  return (
    <div className="videoCard" role="article">
      <div className="videoCardThumb" aria-hidden="true">
        <div className="videoCardDuration">{duration}</div>
      </div>
      <div className="videoCardBody">
        <div className="videoCardTitle" title={title}>
          {title}
        </div>
        <div className="videoCardArtist">
          {artist}
          {year ? <span className="videoCardYear">· {year}</span> : null}
        </div>

        <div className="videoCardMeta">
          {status ? <span className="badge badgeCyan">{status}</span> : null}
          {tags.length > 0 ? (
            <div className="videoCardTags">
              {tags.map((t) => (
                <span key={t} className="badge badgeCyan badgeTilt">
                  {t}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
