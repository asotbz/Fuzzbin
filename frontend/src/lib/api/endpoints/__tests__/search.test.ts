import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { setTokens, clearTokens } from '../../../../auth/tokenStore'
import { TEST_TOKENS } from '../../../../mocks/handlers'
import { getFacets, getSuggestions } from '../search'

describe('search endpoints', () => {
  beforeEach(() => {
    setTokens({ accessToken: TEST_TOKENS.access_token })
  })

  afterEach(() => {
    clearTokens()
  })

  describe('getFacets', () => {
    it('fetches facets for filtering', async () => {
      const result = await getFacets({})

      expect(result).toHaveProperty('total_videos')
      expect(typeof result.total_videos).toBe('number')
    })

    it('returns facets with counts', async () => {
      const result = await getFacets({})

      // Check optional facet arrays exist
      expect(result).toHaveProperty('years')
      expect(result).toHaveProperty('directors')
      expect(result).toHaveProperty('genres')
      expect(result).toHaveProperty('tags')
    })
  })

  describe('getSuggestions', () => {
    it('returns suggestions for query', async () => {
      const result = await getSuggestions({ q: 'test' })

      // API returns suggestions in different fields
      expect(result).toHaveProperty('titles')
      expect(result).toHaveProperty('artists')
      expect(result).toHaveProperty('albums')
    })

    it('returns arrays for each suggestion field', async () => {
      const result = await getSuggestions({ q: 'test' })

      // All fields are optional arrays
      if (result.titles) expect(Array.isArray(result.titles)).toBe(true)
      if (result.artists) expect(Array.isArray(result.artists)).toBe(true)
      if (result.albums) expect(Array.isArray(result.albums)).toBe(true)
    })
  })
})
