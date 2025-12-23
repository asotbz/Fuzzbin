import { useEffect, useMemo, useState } from 'react'
import VideoCard from '../../../components/video/VideoCard'
import VideoGrid from '../../../components/video/VideoGrid'
import type { FacetsResponse, ListVideosQuery, SortOrder, Video } from '../../../lib/api/types'
import { useFacets } from '../hooks/useFacets'
import { useVideos } from '../hooks/useVideos'
import './LibraryPage.css'

type FacetItem = { value: string; count: number }

type FacetSelections = {
  tag_name?: string
  genre?: string
  director?: string
  year?: number
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

function toggle<T>(current: T | undefined, next: T): T | undefined {
  return current === next ? undefined : next
}

export default function LibraryPage() {
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  const [sortBy, setSortBy] = useState<string>('created_at')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const [filters, setFilters] = useState<FacetSelections>({})

  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 300)
    return () => window.clearTimeout(t)
  }, [search])

  const facetsQuery = useFacets({ include_deleted: false })
  const facets = useMemo(() => getFacets(facetsQuery.data), [facetsQuery.data])

  const videosQueryParams: ListVideosQuery = useMemo(() => {
    const query: Record<string, unknown> = {
      page,
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
      include_deleted: false,
    }

    if (debouncedSearch.trim().length > 0) query.search = debouncedSearch

    if (filters.tag_name) query.tag_name = filters.tag_name
    if (filters.genre) query.genre = filters.genre
    if (filters.director) query.director = filters.director
    if (typeof filters.year === 'number') query.year = filters.year

    return query as ListVideosQuery
  }, [page, pageSize, sortBy, sortOrder, debouncedSearch, filters])

  const videosQuery = useVideos(videosQueryParams)

  const respAny = videosQuery.data as unknown as Record<string, unknown> | undefined
  const items = (respAny?.items as unknown as Video[] | undefined) ?? []
  const totalPages = typeof respAny?.total_pages === 'number' ? respAny.total_pages : 1

  const canPrev = page > 1
  const canNext = page < totalPages

  function resetFilters() {
    setFilters({})
    setPage(1)
  }

  return (
    <div className="libraryPage">
      <header className="libraryHeader">
        <h1 className="libraryTitle">Video Library</h1>

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
        </div>
      </header>

      <main className="libraryMain">
        <aside className="panelCard" aria-label="Filters">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-3)' }}>
            <h2 className="sectionTitle" style={{ marginBottom: 0 }}>
              Facets
            </h2>
            <button className="facetItem" type="button" onClick={resetFilters}>
              Reset
            </button>
          </div>

          {facetsQuery.isLoading ? <div className="statusLine">Loading filters…</div> : null}
          {facetsQuery.isError ? <div className="statusLine">Filters unavailable</div> : null}

          {!facetsQuery.isLoading && !facetsQuery.isError ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', marginTop: 'var(--space-4)' }}>
              <section>
                <h3 className="sectionTitle">Tags</h3>
                <div className="facetList">
                  {facets.tags.slice(0, 12).map((t) => (
                    <button
                      key={`tag:${t.value}`}
                      type="button"
                      className={`facetItem ${filters.tag_name === t.value ? 'facetItemActive' : ''}`}
                      onClick={() => {
                        setFilters((prev) => ({ ...prev, tag_name: toggle(prev.tag_name, t.value) }))
                        setPage(1)
                      }}
                    >
                      {t.value}
                      <span className="facetCount">{t.count}</span>
                    </button>
                  ))}
                </div>
              </section>

              <section>
                <h3 className="sectionTitle">Genres</h3>
                <div className="facetList">
                  {facets.genres.slice(0, 12).map((g) => (
                    <button
                      key={`genre:${g.value}`}
                      type="button"
                      className={`facetItem ${filters.genre === g.value ? 'facetItemActive' : ''}`}
                      onClick={() => {
                        setFilters((prev) => ({ ...prev, genre: toggle(prev.genre, g.value) }))
                        setPage(1)
                      }}
                    >
                      {g.value}
                      <span className="facetCount">{g.count}</span>
                    </button>
                  ))}
                </div>
              </section>

              <section>
                <h3 className="sectionTitle">Years</h3>
                <div className="facetList">
                  {facets.years.slice(0, 12).map((y) => {
                    const year = Number(y.value)
                    if (!Number.isFinite(year)) return null
                    return (
                      <button
                        key={`year:${y.value}`}
                        type="button"
                        className={`facetItem ${filters.year === year ? 'facetItemActive' : ''}`}
                        onClick={() => {
                          setFilters((prev) => ({ ...prev, year: toggle(prev.year, year) }))
                          setPage(1)
                        }}
                      >
                        {y.value}
                        <span className="facetCount">{y.count}</span>
                      </button>
                    )
                  })}
                </div>
              </section>

              <section>
                <h3 className="sectionTitle">Directors</h3>
                <div className="facetList">
                  {facets.directors.slice(0, 12).map((d) => (
                    <button
                      key={`director:${d.value}`}
                      type="button"
                      className={`facetItem ${filters.director === d.value ? 'facetItemActive' : ''}`}
                      onClick={() => {
                        setFilters((prev) => ({ ...prev, director: toggle(prev.director, d.value) }))
                        setPage(1)
                      }}
                    >
                      {d.value}
                      <span className="facetCount">{d.count}</span>
                    </button>
                  ))}
                </div>
              </section>
            </div>
          ) : null}
        </aside>

        <section className="panelCard" aria-label="Videos">
          {videosQuery.isLoading ? <div className="statusLine">Loading videos…</div> : null}
          {videosQuery.isError ? <div className="statusLine">Videos unavailable</div> : null}

          {!videosQuery.isLoading && !videosQuery.isError && items.length === 0 ? (
            <div className="statusLine">No videos found</div>
          ) : null}

          {!videosQuery.isLoading && !videosQuery.isError && items.length > 0 ? (
            <>
              <VideoGrid>
                {items.map((v) => {
                  const id = (v as unknown as Record<string, unknown>).id
                  const key = typeof id === 'number' || typeof id === 'string' ? String(id) : JSON.stringify(v)
                  return <VideoCard key={key} video={v} />
                })}
              </VideoGrid>

              <div className="pagination">
                <button className="primaryButton" type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={!canPrev}>
                  Prev
                </button>
                <div className="paginationInfo">
                  Page {page} / {totalPages}
                </div>
                <button className="primaryButton" type="button" onClick={() => setPage((p) => p + 1)} disabled={!canNext}>
                  Next
                </button>
              </div>
            </>
          ) : null}
        </section>
      </main>
    </div>
  )
}
