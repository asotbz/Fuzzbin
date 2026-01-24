import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { server } from '../../../../mocks/server'
import { http, HttpResponse } from 'msw'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS, mockConfig } from '../../../../mocks/handlers'
import {
  getConfig,
  getConfigField,
  updateConfig,
  getConfigHistory,
  undoConfig,
  redoConfig,
  getFieldSafety,
} from '../config'

const BASE_URL = 'http://localhost:8000'

describe('config endpoints', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  describe('getConfig', () => {
    it('fetches complete configuration', async () => {
      const result = await getConfig()

      expect(result.config).toEqual(mockConfig)
      expect(result.config_path).toBe('/config/config.yaml')
    })

    it('includes library settings', async () => {
      const result = await getConfig()

      expect(result.config.library).toBeDefined()
      expect(result.config.library.library_dir).toBe('/music_videos')
    })

    it('includes API settings', async () => {
      const result = await getConfig()

      expect(result.config.apis).toBeDefined()
      expect(result.config.apis.imvdb.enabled).toBe(true)
    })
  })

  describe('getConfigField', () => {
    it('fetches specific nested field', async () => {
      const result = await getConfigField('library.library_dir')

      expect(result).toBe('/music_videos')
    })

    it('fetches entire section', async () => {
      const result = await getConfigField('library')

      expect(result).toEqual(mockConfig.library)
    })

    it('handles 404 for nonexistent field', async () => {
      await expect(getConfigField('nonexistent.field')).rejects.toThrow()
    })
  })

  describe('updateConfig', () => {
    it('updates configuration field successfully', async () => {
      const result = await updateConfig({
        updates: { 'logging.level': 'DEBUG' },
        description: 'Changed log level',
      })

      expect(result.updated_fields).toContain('logging.level')
      expect(result.safety_level).toBe('safe')
      expect(result.message).toContain('successfully')
    })

    it('returns conflict for unsafe changes without force', async () => {
      await expect(
        updateConfig({
          updates: { 'library.library_dir': '/new/path' },
        })
      ).rejects.toThrow()
    })

    it('allows unsafe changes with force flag', async () => {
      const result = await updateConfig({
        updates: { 'library.library_dir': '/new/path' },
        force: true,
      })

      expect(result.updated_fields).toContain('library.library_dir')
    })
  })

  describe('getConfigHistory', () => {
    it('fetches configuration history', async () => {
      const result = await getConfigHistory()

      expect(result.entries).toHaveLength(2)
      expect(result.current_index).toBe(1)
    })

    it('indicates undo/redo availability', async () => {
      const result = await getConfigHistory()

      expect(result.can_undo).toBe(true)
      expect(result.can_redo).toBe(false)
    })

    it('includes timestamps and descriptions', async () => {
      const result = await getConfigHistory()

      expect(result.entries[0]).toHaveProperty('timestamp')
      expect(result.entries[0]).toHaveProperty('description')
      expect(result.entries[0]).toHaveProperty('is_current')
    })
  })

  describe('undoConfig', () => {
    it('undoes last configuration change', async () => {
      const result = await undoConfig()

      expect(result.message).toContain('undone')
      expect(result.new_index).toBe(0)
      expect(result.can_undo).toBe(false)
      expect(result.can_redo).toBe(true)
    })

    it('fails when nothing to undo', async () => {
      // Override to simulate no undo available
      server.use(
        http.post(`${BASE_URL}/config/undo`, () => {
          return HttpResponse.json(
            { detail: 'Nothing to undo' },
            { status: 400 }
          )
        })
      )

      await expect(undoConfig()).rejects.toThrow()
    })
  })

  describe('redoConfig', () => {
    it('redoes configuration change', async () => {
      // First override to allow redo
      server.use(
        http.post(`${BASE_URL}/config/redo`, () => {
          return HttpResponse.json({
            message: 'Configuration change redone',
            new_index: 1,
            can_undo: true,
            can_redo: false,
          })
        })
      )

      const result = await redoConfig()

      expect(result.message).toContain('redone')
      expect(result.can_undo).toBe(true)
    })

    it('fails when nothing to redo', async () => {
      await expect(redoConfig()).rejects.toThrow()
    })
  })

  describe('getFieldSafety', () => {
    it('returns safety level for safe field', async () => {
      const result = await getFieldSafety('logging.level')

      expect(result.path).toBe('logging.level')
      expect(result.safety_level).toBe('safe')
      expect(result.description).toBeDefined()
    })

    it('returns affects_state for library fields', async () => {
      const result = await getFieldSafety('library.library_dir')

      expect(result.safety_level).toBe('affects_state')
    })

    it('returns requires_reload for API fields', async () => {
      const result = await getFieldSafety('apis.imvdb.enabled')

      expect(result.safety_level).toBe('requires_reload')
    })
  })
})
