import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS } from '../../../../mocks/handlers'
import {
  addSearch,
  addPreview,
  addImport,
  addPreviewBatch,
  addSpotifyImport,
  addNFOScan,
  checkVideoExists,
} from '../add'

describe('add endpoints', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  describe('addSearch', () => {
    it('searches for videos to add', async () => {
      const result = await addSearch({
        artist: 'Test Artist',
        track_title: 'Test Song',
        imvdb_per_page: 10,
        discogs_per_page: 10,
        youtube_max_results: 10,
      })

      expect(result).toHaveProperty('results')
      expect(Array.isArray(result.results)).toBe(true)
    })
  })

  describe('addPreview', () => {
    it('fetches preview for a specific item', async () => {
      const result = await addPreview('imvdb', 'test-item-id')

      expect(result).toHaveProperty('source')
      expect(result).toHaveProperty('id')
      expect(result).toHaveProperty('data')
    })
  })

  describe('addImport', () => {
    it('starts import job and returns job ID', async () => {
      const result = await addImport({
        source: 'imvdb',
        id: 'test-123',
        initial_status: 'pending',
        skip_existing: true,
        auto_download: true,
      })

      expect(result).toHaveProperty('job_id')
      expect(result).toHaveProperty('status')
    })
  })

  describe('addPreviewBatch', () => {
    it('previews batch items', async () => {
      const result = await addPreviewBatch({
        mode: 'spotify',
        recursive: false,
        skip_existing: true,
      })

      expect(result).toHaveProperty('mode')
    })
  })

  describe('addSpotifyImport', () => {
    it('starts Spotify playlist import', async () => {
      const result = await addSpotifyImport({
        playlist_id: 'abc123',
        skip_existing: true,
        initial_status: 'pending',
      })

      expect(result).toHaveProperty('job_id')
      expect(result).toHaveProperty('playlist_id')
    })
  })

  describe('addNFOScan', () => {
    it('starts NFO directory scan', async () => {
      const result = await addNFOScan({
        directory: '/path/to/videos',
        mode: 'full',
        recursive: true,
        skip_existing: true,
        update_file_paths: false,
      })

      expect(result).toHaveProperty('job_id')
    })
  })

  describe('checkVideoExists', () => {
    it('returns exists: true for known video', async () => {
      const result = await checkVideoExists({ imvdb_id: 'existing-imvdb-id' })

      expect(result.exists).toBe(true)
      expect(result.video_id).toBe(1)
      expect(result.title).toBe('Existing Video')
    })

    it('returns exists: false for unknown video', async () => {
      const result = await checkVideoExists({ imvdb_id: 'unknown-id' })

      expect(result.exists).toBe(false)
      expect(result.video_id).toBeNull()
    })

    it('supports checking by youtube_id', async () => {
      const result = await checkVideoExists({ youtube_id: 'yt-unknown' })

      expect(result.exists).toBe(false)
    })
  })
})
