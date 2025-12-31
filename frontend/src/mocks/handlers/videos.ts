import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const mockVideos = [
  {
    id: 1,
    title: 'Test Video 1',
    artist: 'Test Artist',
    album: 'Test Album',
    year: 2023,
    director: 'Test Director',
    imvdb_id: 'imvdb-123',
    youtube_id: 'yt-123',
    file_path: '/videos/test1.mp4',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
  },
  {
    id: 2,
    title: 'Test Video 2',
    artist: 'Another Artist',
    album: 'Another Album',
    year: 2024,
    director: null,
    imvdb_id: 'imvdb-456',
    youtube_id: 'yt-456',
    file_path: '/videos/test2.mp4',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
]

export const videosHandlers = [
  // List videos
  http.get(`${BASE_URL}/videos`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1', 10)
    const pageSize = parseInt(url.searchParams.get('page_size') || '20', 10)
    const search = url.searchParams.get('q')
    const titleFilter = url.searchParams.get('title')
    const artistFilter = url.searchParams.get('artist')

    let filtered = [...mockVideos]

    // Simple search filter
    if (search) {
      const searchLower = search.toLowerCase()
      filtered = filtered.filter(
        v =>
          v.title?.toLowerCase().includes(searchLower) ||
          v.artist?.toLowerCase().includes(searchLower)
      )
    }

    // Title filter (exact match style)
    if (titleFilter) {
      filtered = filtered.filter(v => v.title === titleFilter)
    }

    // Artist filter
    if (artistFilter) {
      filtered = filtered.filter(v => v.artist === artistFilter)
    }

    const start = (page - 1) * pageSize
    const items = filtered.slice(start, start + pageSize)

    return HttpResponse.json({
      items,
      total: filtered.length,
      page,
      page_size: pageSize,
    })
  }),

  // Get single video
  http.get(`${BASE_URL}/videos/:id`, ({ params }) => {
    const id = parseInt(params.id as string, 10)
    const video = mockVideos.find(v => v.id === id)

    if (!video) {
      return HttpResponse.json(
        { detail: 'Video not found' },
        { status: 404 }
      )
    }

    return HttpResponse.json(video)
  }),

  // Bulk delete videos
  http.post(`${BASE_URL}/videos/bulk/delete`, async ({ request }) => {
    const body = await request.json() as {
      video_ids: number[]
      delete_files?: boolean
      permanent?: boolean
    }

    const successIds = body.video_ids.filter(id => mockVideos.some(v => v.id === id))
    const failedIds = body.video_ids.filter(id => !mockVideos.some(v => v.id === id))

    return HttpResponse.json({
      success_ids: successIds,
      failed_ids: failedIds,
      errors: {},
      file_errors: [],
      total: body.video_ids.length,
      success_count: successIds.length,
      failed_count: failedIds.length,
    })
  }),

  // List trash
  http.get(`${BASE_URL}/files/trash`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1', 10)
    const pageSize = parseInt(url.searchParams.get('page_size') || '20', 10)

    return HttpResponse.json({
      items: [],
      total: 0,
      page,
      page_size: pageSize,
    })
  }),

  // Trash stats
  http.get(`${BASE_URL}/files/trash/stats`, () => {
    return HttpResponse.json({
      total_count: 0,
      total_size_bytes: 0,
    })
  }),

  // Empty trash
  http.post(`${BASE_URL}/files/trash/empty`, () => {
    return HttpResponse.json({
      deleted_count: 0,
      errors: [],
    })
  }),
]
