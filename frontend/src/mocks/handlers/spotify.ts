import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const mockSpotifyEnrichResponse = {
  spotify_track_id: 'spotify-track-123',
  musicbrainz: {
    canonical_artist: 'Canonical Artist',
    canonical_title: 'Canonical Title',
    album: 'Canonical Album',
    year: 2020,
    label: 'Record Label',
    genre: 'Rock',
    recording_mbid: 'mb-recording-123',
    release_mbid: 'mb-release-456',
    confident_match: true,
  },
  imvdb: {
    imvdb_id: 123,
    imvdb_url: 'https://imvdb.com/video/123',
    year: 2020,
    directors: 'Famous Director',
    featured_artists: null,
    youtube_ids: ['yt-abc123'],
    thumbnail_url: 'https://imvdb.com/thumb/123.jpg',
    match_found: true,
  },
  title: 'Canonical Title',
  artist: 'Canonical Artist',
  album: 'Canonical Album',
  year: 2020,
  label: 'Record Label',
  genre: 'Rock',
  directors: 'Famous Director',
  youtube_id: 'yt-abc123',
  already_exists: false,
  existing_video_id: null,
}

export const mockYouTubeSearchResponse = {
  artist: 'Test Artist',
  track_title: 'Test Song',
  results: [
    {
      source: 'youtube' as const,
      id: 'yt-result-1',
      title: 'Artist - Song (Official Music Video)',
      artist: 'Artist',
      year: 2020,
      url: 'https://youtube.com/watch?v=yt-result-1',
      thumbnail: 'https://i.ytimg.com/vi/yt-result-1/hqdefault.jpg',
      extra: {
        youtube_id: 'yt-result-1',
        view_count: 1000000,
        duration: 240,
      },
    },
    {
      source: 'youtube' as const,
      id: 'yt-result-2',
      title: 'Artist - Song (Live)',
      artist: 'Artist',
      year: 2020,
      url: 'https://youtube.com/watch?v=yt-result-2',
      thumbnail: 'https://i.ytimg.com/vi/yt-result-2/hqdefault.jpg',
      extra: {
        youtube_id: 'yt-result-2',
        view_count: 500000,
        duration: 300,
      },
    },
  ],
}

export const mockYouTubeMetadataResponse = {
  youtube_id: 'yt-abc123',
  title: 'Artist - Song (Official Music Video)',
  channel: 'ArtistVEVO',
  duration: 240,
  view_count: 5000000,
  available: true,
  error: null,
}

export const spotifyHandlers = [
  // Enrich Spotify track
  http.post(`${BASE_URL}/add/spotify/enrich-track`, async ({ request }) => {
    const body = (await request.json()) as {
      artist: string
      track_title: string
      spotify_track_id: string
      isrc?: string
    }

    if (!body.artist || !body.track_title) {
      return HttpResponse.json(
        { detail: 'artist and track_title are required' },
        { status: 400 }
      )
    }

    // Simulate already exists check
    if (body.track_title.toLowerCase().includes('existing')) {
      return HttpResponse.json({
        ...mockSpotifyEnrichResponse,
        spotify_track_id: body.spotify_track_id,
        already_exists: true,
        existing_video_id: 42,
      })
    }

    return HttpResponse.json({
      ...mockSpotifyEnrichResponse,
      spotify_track_id: body.spotify_track_id,
    })
  }),

  // Import selected tracks
  http.post(`${BASE_URL}/add/spotify/import-selected`, async ({ request }) => {
    const body = (await request.json()) as {
      playlist_id: string
      tracks: Array<{
        spotify_track_id: string
        metadata: Record<string, unknown>
      }>
      initial_status?: string
      auto_download?: boolean
    }

    if (!body.playlist_id || !body.tracks?.length) {
      return HttpResponse.json(
        { detail: 'playlist_id and tracks are required' },
        { status: 400 }
      )
    }

    return HttpResponse.json({
      job_id: `spotify-import-${Date.now()}`,
      playlist_id: body.playlist_id,
      track_count: body.tracks.length,
      auto_download: body.auto_download ?? false,
      status: 'queued',
    })
  }),

  // YouTube search
  http.post(`${BASE_URL}/add/youtube/search`, async ({ request }) => {
    const body = (await request.json()) as {
      artist: string
      track_title: string
      max_results?: number
    }

    if (!body.artist || !body.track_title) {
      return HttpResponse.json(
        { detail: 'artist and track_title are required' },
        { status: 400 }
      )
    }

    return HttpResponse.json({
      ...mockYouTubeSearchResponse,
      artist: body.artist,
      track_title: body.track_title,
    })
  }),

  // YouTube metadata
  http.post(`${BASE_URL}/add/youtube/metadata`, async ({ request }) => {
    const body = (await request.json()) as {
      youtube_id: string
    }

    if (!body.youtube_id) {
      return HttpResponse.json(
        { detail: 'youtube_id is required' },
        { status: 400 }
      )
    }

    // Simulate unavailable video
    if (body.youtube_id === 'unavailable-video') {
      return HttpResponse.json({
        youtube_id: body.youtube_id,
        title: null,
        channel: null,
        duration: null,
        view_count: null,
        available: false,
        error: 'Video unavailable',
      })
    }

    return HttpResponse.json({
      ...mockYouTubeMetadataResponse,
      youtube_id: body.youtube_id,
    })
  }),
]
