import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const mockSearchResults = {
  results: [
    {
      source: 'imvdb' as const,
      id: 'imvdb-result-1',
      data: {
        title: 'Test Music Video',
        artist: 'Test Artist',
        year: 2023,
      },
    },
    {
      source: 'youtube' as const,
      id: 'yt-result-1',
      data: {
        title: 'Test Music Video (Official)',
        artist: 'Test Artist',
        year: 2023,
      },
    },
  ],
  total: 2,
}

export const mockPreview = {
  source: 'imvdb' as const,
  id: 'imvdb-result-1',
  data: {
    title: 'Test Music Video',
    artist: 'Test Artist',
    album: 'Test Album',
    year: 2023,
    director: 'Test Director',
  },
}

export const addHandlers = [
  // Search for videos to add
  http.post(`${BASE_URL}/add/search`, async ({ request }) => {
    const body = await request.json() as { artist: string; track_title: string }

    if (!body.artist && !body.track_title) {
      return HttpResponse.json(
        { detail: 'Artist and track_title are required' },
        { status: 400 }
      )
    }

    return HttpResponse.json(mockSearchResults)
  }),

  // Preview a video before importing
  http.get(`${BASE_URL}/add/preview/:source/:itemId`, ({ params }) => {
    const { source, itemId } = params as { source: string; itemId: string }

    return HttpResponse.json({
      source,
      id: itemId,
      data: mockPreview.data,
    })
  }),

  // Import a single video
  http.post(`${BASE_URL}/add/import`, async ({ request }) => {
    const body = await request.json() as {
      source: string
      id: string
      initial_status?: string
      skip_existing?: boolean
    }

    return HttpResponse.json({
      job_id: `job-${Date.now()}`,
      source: body.source,
      id: body.id,
      status: 'queued',
    })
  }),

  // Batch preview
  http.post(`${BASE_URL}/add/preview-batch`, async ({ request }) => {
    const body = await request.json() as { mode: string; recursive?: boolean; skip_existing?: boolean }

    return HttpResponse.json({
      mode: body.mode,
      items: [],
    })
  }),

  // Spotify import
  http.post(`${BASE_URL}/add/spotify`, async ({ request }) => {
    const body = await request.json() as { playlist_id: string; skip_existing?: boolean; initial_status?: string }

    if (!body.playlist_id) {
      return HttpResponse.json(
        { detail: 'playlist_id is required' },
        { status: 400 }
      )
    }

    return HttpResponse.json({
      job_id: `spotify-job-${Date.now()}`,
      playlist_id: body.playlist_id,
      status: 'queued',
    })
  }),

  // NFO scan
  http.post(`${BASE_URL}/add/nfo-scan`, async ({ request }) => {
    const body = await request.json() as { directory: string; mode?: string; recursive?: boolean }

    if (!body.directory) {
      return HttpResponse.json(
        { detail: 'Directory is required' },
        { status: 400 }
      )
    }

    return HttpResponse.json({
      job_id: `nfo-scan-${Date.now()}`,
    })
  }),

  // Check if video exists
  http.get(`${BASE_URL}/add/check-exists`, ({ request }) => {
    const url = new URL(request.url)
    const imvdbId = url.searchParams.get('imvdb_id')
    // Note: youtube_id param available via url.searchParams.get('youtube_id') if needed

    // Simulate that 'existing-imvdb-id' already exists
    if (imvdbId === 'existing-imvdb-id') {
      return HttpResponse.json({
        exists: true,
        video_id: 1,
        title: 'Existing Video',
        artist: 'Existing Artist',
      })
    }

    return HttpResponse.json({
      exists: false,
      video_id: null,
      title: null,
      artist: null,
    })
  }),
]
