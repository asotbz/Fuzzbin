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

  // Search artists
  http.post(`${BASE_URL}/add/search/artist`, async () => {
    return HttpResponse.json({
      artist_name: 'Test Artist',
      total_results: 2,
      results: [
        {
          id: 1,
          name: 'Mock Artist 1',
          slug: 'mock-artist-1',
          url: 'https://imvdb.com/artist/mock-artist-1',
          image: null,
          discogs_id: null,
          artist_video_count: 10,
          featured_video_count: 2,
          sample_tracks: ['Track 1', 'Track 2'],
        },
        {
          id: 2,
          name: 'Mock Artist 2',
          slug: 'mock-artist-2',
          url: 'https://imvdb.com/artist/mock-artist-2',
          image: null,
          discogs_id: null,
          artist_video_count: 5,
          featured_video_count: 0,
          sample_tracks: ['Track A'],
        },
      ],
    })
  }),

  // Preview artist videos
  http.get(`${BASE_URL}/add/artist/preview/:entityId`, ({ params, request }) => {
    const { entityId } = params as { entityId: string }
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1', 10)
    const perPage = parseInt(url.searchParams.get('per_page') || '50', 10)

    return HttpResponse.json({
      entity_id: parseInt(entityId, 10),
      entity_name: 'Mock Artist',
      entity_slug: 'mock-artist',
      total_videos: 50,
      current_page: page,
      per_page: perPage,
      total_pages: Math.ceil(50 / perPage),
      has_more: page * perPage < 50,
      videos: [
        {
          id: 1,
          song_title: 'Artist Video 1',
          year: 2023,
          url: 'https://imvdb.com/video/1',
          thumbnail_url: null,
          production_status: 'official',
          version_name: null,
          already_exists: false,
          existing_video_id: null,
        },
        {
          id: 2,
          song_title: 'Artist Video 2',
          year: 2022,
          url: 'https://imvdb.com/video/2',
          thumbnail_url: null,
          production_status: 'official',
          version_name: null,
          already_exists: false,
          existing_video_id: null,
        },
      ],
      existing_count: 0,
      new_count: 2,
    })
  }),

  // Enrich IMVDb video
  http.post(`${BASE_URL}/add/enrich/imvdb-video`, async ({ request }) => {
    const body = await request.json() as { imvdb_id: number; artist: string; track_title: string }

    return HttpResponse.json({
      imvdb_id: body.imvdb_id,
      title: body.track_title,
      artist: body.artist,
      album: 'Enriched Album',
      year: 2023,
      label: null,
      genre: 'Pop',
      directors: 'Test Director',
      featured_artists: null,
      youtube_ids: ['yt-123'],
      imvdb_url: `https://imvdb.com/video/${body.imvdb_id}`,
      thumbnail_url: null,
      musicbrainz: {
        recording_mbid: null,
        release_mbid: null,
        canonical_title: null,
        canonical_artist: null,
        album: null,
        year: null,
        label: null,
        genre: null,
        classified_genre: null,
        all_genres: [],
        match_score: 0,
        match_method: 'none',
        confident_match: false,
      },
      enrichment_status: 'success',
      already_exists: false,
      existing_video_id: null,
    })
  }),

  // Import artist videos
  http.post(`${BASE_URL}/add/artist/import`, async ({ request }) => {
    const body = await request.json() as { entity_id: number; videos: unknown[] }

    return HttpResponse.json({
      job_id: `artist-import-${Date.now()}`,
      entity_id: body.entity_id,
      video_count: body.videos.length,
      auto_download: false,
      status: 'queued',
    })
  }),
]
