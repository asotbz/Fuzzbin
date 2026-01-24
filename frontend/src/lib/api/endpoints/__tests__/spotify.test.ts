import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS } from '../../../../mocks/handlers'
import {
  enrichSpotifyTrack,
  importSelectedTracks,
  searchYouTube,
  getYouTubeMetadata,
} from '../spotify'

describe('spotify endpoints', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  describe('enrichSpotifyTrack', () => {
    it('enriches track with MusicBrainz and IMVDb data', async () => {
      const result = await enrichSpotifyTrack({
        artist: 'Test Artist',
        track_title: 'Test Song',
        spotify_track_id: 'spotify-track-123',
        isrc: 'USRC12345678',
      })

      expect(result.musicbrainz).toBeDefined()
      expect(result.musicbrainz?.canonical_artist).toBe('Canonical Artist')
      expect(result.musicbrainz?.canonical_title).toBe('Canonical Title')
      expect(result.musicbrainz?.genre).toBeDefined()
    })

    it('includes IMVDb data when available', async () => {
      const result = await enrichSpotifyTrack({
        artist: 'Test Artist',
        track_title: 'Test Song',
        spotify_track_id: 'spotify-track-123',
      })

      expect(result.imvdb).toBeDefined()
      expect(result.imvdb?.imvdb_id).toBe(123)
      expect(result.imvdb?.directors).toBeDefined()
      expect(result.imvdb?.youtube_ids).toBeDefined()
    })

    it('indicates when track already exists in library', async () => {
      const result = await enrichSpotifyTrack({
        artist: 'Test Artist',
        track_title: 'Existing Song', // Contains 'existing' to trigger mock
        spotify_track_id: 'spotify-track-existing',
      })

      expect(result.already_exists).toBe(true)
      expect(result.existing_video_id).toBe(42)
    })

    it('indicates when track does not exist', async () => {
      const result = await enrichSpotifyTrack({
        artist: 'Test Artist',
        track_title: 'New Song',
        spotify_track_id: 'spotify-track-new',
      })

      expect(result.already_exists).toBe(false)
      expect(result.existing_video_id).toBeNull()
    })

    it('throws error when artist is missing', async () => {
      await expect(
        enrichSpotifyTrack({
          artist: '',
          track_title: 'Test Song',
          spotify_track_id: 'spotify-track-123',
        })
      ).rejects.toThrow()
    })

    it('throws error when track_title is missing', async () => {
      await expect(
        enrichSpotifyTrack({
          artist: 'Test Artist',
          track_title: '',
          spotify_track_id: 'spotify-track-123',
        })
      ).rejects.toThrow()
    })
  })

  describe('importSelectedTracks', () => {
    it('starts import job for selected tracks', async () => {
      const result = await importSelectedTracks({
        playlist_id: 'playlist-123',
        tracks: [
          {
            spotify_track_id: 'track-1',
            metadata: { artist: 'Artist 1', title: 'Song 1' },
          },
          {
            spotify_track_id: 'track-2',
            metadata: { artist: 'Artist 2', title: 'Song 2' },
          },
        ],
        initial_status: 'discovered',
        auto_download: true,
      })

      expect(result.job_id).toBeDefined()
      expect(result.job_id).toContain('spotify-import')
      expect(result.playlist_id).toBe('playlist-123')
      expect(result.track_count).toBe(2)
      expect(result.status).toBe('queued')
    })

    it('throws error when playlist_id is missing', async () => {
      await expect(
        importSelectedTracks({
          playlist_id: '',
          tracks: [
            {
              spotify_track_id: 'track-1',
              metadata: { artist: 'Artist', title: 'Song' },
            },
          ],
          initial_status: 'discovered',
          auto_download: false,
        })
      ).rejects.toThrow()
    })

    it('throws error when tracks array is empty', async () => {
      await expect(
        importSelectedTracks({
          playlist_id: 'playlist-123',
          tracks: [],
          initial_status: 'discovered',
          auto_download: false,
        })
      ).rejects.toThrow()
    })
  })

  describe('searchYouTube', () => {
    it('searches YouTube for videos', async () => {
      const result = await searchYouTube({
        artist: 'Test Artist',
        track_title: 'Test Song',
        max_results: 10,
      })

      expect(result.results).toBeDefined()
      expect(result.results).toHaveLength(2)
    })

    it('returns YouTube video data', async () => {
      const result = await searchYouTube({
        artist: 'Test Artist',
        track_title: 'Test Song',
        max_results: 10,
      })

      const firstResult = result.results![0]
      expect(firstResult.source).toBe('youtube')
      expect(firstResult.id).toBe('yt-result-1')
      expect(firstResult.extra?.youtube_id).toBe('yt-result-1')
      expect(firstResult.extra?.view_count).toBe(1000000)
    })

    it('throws error when artist is missing', async () => {
      await expect(
        searchYouTube({
          artist: '',
          track_title: 'Test Song',
          max_results: 10,
        })
      ).rejects.toThrow()
    })

    it('throws error when track_title is missing', async () => {
      await expect(
        searchYouTube({
          artist: 'Test Artist',
          track_title: '',
          max_results: 10,
        })
      ).rejects.toThrow()
    })
  })

  describe('getYouTubeMetadata', () => {
    it('fetches metadata for available video', async () => {
      const result = await getYouTubeMetadata({
        youtube_id: 'yt-abc123',
      })

      expect(result.youtube_id).toBe('yt-abc123')
      expect(result.title).toBe('Artist - Song (Official Music Video)')
      expect(result.channel).toBe('ArtistVEVO')
      expect(result.duration).toBe(240)
      expect(result.view_count).toBe(5000000)
      expect(result.available).toBe(true)
      expect(result.error).toBeNull()
    })

    it('indicates when video is unavailable', async () => {
      const result = await getYouTubeMetadata({
        youtube_id: 'unavailable-video',
      })

      expect(result.available).toBe(false)
      expect(result.error).toBe('Video unavailable')
      expect(result.title).toBeNull()
    })

    it('throws error when youtube_id is missing', async () => {
      await expect(
        getYouTubeMetadata({
          youtube_id: '',
        })
      ).rejects.toThrow()
    })
  })
})
