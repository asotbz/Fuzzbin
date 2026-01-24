import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { server } from '../../../../mocks/server'
import { http, HttpResponse } from 'msw'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS, mockVideos } from '../../../../mocks/handlers'
import {
  listVideos,
  getVideo,
  bulkDeleteVideos,
  listTrash,
  getTrashStats,
  emptyTrash,
} from '../videos'

const BASE_URL = 'http://localhost:8000'

describe('videos endpoints', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  describe('listVideos', () => {
    it('fetches paginated video list', async () => {
      const result = await listVideos({ page: 1, page_size: 20 })

      expect(result.items).toHaveLength(mockVideos.length)
      expect(result.total).toBe(mockVideos.length)
      expect(result.page).toBe(1)
      expect(result.page_size).toBe(20)
    })

    it('supports title search parameter', async () => {
      const result = await listVideos({ title: 'Test Video 1' })

      expect(result.items).toHaveLength(1)
      expect(result.items[0].title).toBe('Test Video 1')
    })

    it('returns empty list when no matches', async () => {
      const result = await listVideos({ title: 'nonexistent' })

      expect(result.items).toHaveLength(0)
      expect(result.total).toBe(0)
    })
  })

  describe('getVideo', () => {
    it('fetches single video by ID', async () => {
      const result = await getVideo(1)

      expect(result).toHaveProperty('id')
      expect(result).toHaveProperty('title')
      expect(result).toHaveProperty('artist')
      expect(result.id).toBe(1)
    })
  })

  describe('bulkDeleteVideos', () => {
    it('deletes multiple videos by ID', async () => {
      const result = await bulkDeleteVideos([1, 2])

      expect(result.success_ids).toEqual([1, 2])
      expect(result.failed_ids).toEqual([])
      expect(result.success_count).toBe(2)
      expect(result.failed_count).toBe(0)
    })

    it('reports failed IDs for nonexistent videos', async () => {
      const result = await bulkDeleteVideos([1, 999])

      expect(result.success_ids).toEqual([1])
      expect(result.failed_ids).toEqual([999])
      expect(result.success_count).toBe(1)
      expect(result.failed_count).toBe(1)
    })

    it('supports delete_files and permanent options', async () => {
      // Override handler to verify options are passed
      server.use(
        http.post(`${BASE_URL}/videos/bulk/delete`, async ({ request }) => {
          const body = await request.json() as {
            video_ids: number[]
            delete_files?: boolean
            permanent?: boolean
          }

          return HttpResponse.json({
            success_ids: body.video_ids,
            failed_ids: [],
            errors: {},
            file_errors: [],
            total: body.video_ids.length,
            success_count: body.video_ids.length,
            failed_count: 0,
            // Echo back the options for verification
            _delete_files: body.delete_files,
            _permanent: body.permanent,
          })
        })
      )

      const result = await bulkDeleteVideos([1], true, true)

      expect(result).toMatchObject({
        success_ids: [1],
        _delete_files: true,
        _permanent: true,
      })
    })
  })

  describe('listTrash', () => {
    it('fetches paginated trash list', async () => {
      const result = await listTrash(1, 20)

      expect(result.items).toEqual([])
      expect(result.total).toBe(0)
      expect(result.page).toBe(1)
      expect(result.page_size).toBe(20)
    })

    it('uses default pagination when not specified', async () => {
      const result = await listTrash()

      expect(result.page).toBe(1)
      expect(result.page_size).toBe(20)
    })
  })

  describe('getTrashStats', () => {
    it('fetches trash statistics', async () => {
      const result = await getTrashStats()

      expect(result).toHaveProperty('total_count')
      expect(result).toHaveProperty('total_size_bytes')
      expect(typeof result.total_count).toBe('number')
      expect(typeof result.total_size_bytes).toBe('number')
    })
  })

  describe('emptyTrash', () => {
    it('empties trash and returns result', async () => {
      const result = await emptyTrash()

      expect(result).toHaveProperty('deleted_count')
      expect(result).toHaveProperty('errors')
      expect(Array.isArray(result.errors)).toBe(true)
    })
  })
})
