import { describe, it, expect } from 'vitest'
import { toQueryString } from '../queryString'

describe('toQueryString', () => {
  describe('basic values', () => {
    it('converts string value', () => {
      expect(toQueryString({ name: 'test' })).toBe('?name=test')
    })

    it('converts number value', () => {
      expect(toQueryString({ page: 5 })).toBe('?page=5')
    })

    it('converts boolean true', () => {
      expect(toQueryString({ active: true })).toBe('?active=true')
    })

    it('converts boolean false', () => {
      expect(toQueryString({ active: false })).toBe('?active=false')
    })

    it('converts multiple values', () => {
      const result = toQueryString({ name: 'test', page: 1 })
      expect(result).toContain('name=test')
      expect(result).toContain('page=1')
      expect(result).toMatch(/^\?/)
    })
  })

  describe('null and undefined handling', () => {
    it('skips undefined values', () => {
      expect(toQueryString({ name: undefined })).toBe('')
    })

    it('skips null values', () => {
      expect(toQueryString({ name: null })).toBe('')
    })

    it('returns empty string for empty object', () => {
      expect(toQueryString({})).toBe('')
    })

    it('returns empty string when all values are undefined', () => {
      expect(toQueryString({ a: undefined, b: undefined })).toBe('')
    })
  })

  describe('string trimming', () => {
    it('trims whitespace from string values', () => {
      expect(toQueryString({ name: '  test  ' })).toBe('?name=test')
    })

    it('skips empty strings', () => {
      expect(toQueryString({ name: '' })).toBe('')
    })

    it('skips whitespace-only strings', () => {
      expect(toQueryString({ name: '   ' })).toBe('')
    })
  })

  describe('number validation', () => {
    it('skips NaN', () => {
      expect(toQueryString({ value: NaN })).toBe('')
    })

    it('skips Infinity', () => {
      expect(toQueryString({ value: Infinity })).toBe('')
    })

    it('skips negative Infinity', () => {
      expect(toQueryString({ value: -Infinity })).toBe('')
    })

    it('handles zero', () => {
      expect(toQueryString({ value: 0 })).toBe('?value=0')
    })

    it('handles negative numbers', () => {
      expect(toQueryString({ value: -5 })).toBe('?value=-5')
    })

    it('handles decimal numbers', () => {
      expect(toQueryString({ value: 3.14 })).toBe('?value=3.14')
    })
  })

  describe('array handling', () => {
    it('appends multiple values for string arrays', () => {
      const result = toQueryString({ tags: ['rock', 'pop'] })
      expect(result).toBe('?tags=rock&tags=pop')
    })

    it('appends multiple values for number arrays', () => {
      const result = toQueryString({ ids: [1, 2, 3] })
      expect(result).toBe('?ids=1&ids=2&ids=3')
    })

    it('appends multiple values for boolean arrays', () => {
      const result = toQueryString({ flags: [true, false] })
      expect(result).toBe('?flags=true&flags=false')
    })

    it('skips undefined values in arrays', () => {
      const result = toQueryString({ tags: ['rock', undefined, 'pop'] })
      expect(result).toBe('?tags=rock&tags=pop')
    })

    it('skips null values in arrays', () => {
      const result = toQueryString({ tags: ['rock', null, 'pop'] })
      expect(result).toBe('?tags=rock&tags=pop')
    })

    it('skips empty strings in arrays', () => {
      const result = toQueryString({ tags: ['rock', '', 'pop'] })
      expect(result).toBe('?tags=rock&tags=pop')
    })

    it('trims strings in arrays', () => {
      const result = toQueryString({ tags: ['  rock  ', '  pop  '] })
      expect(result).toBe('?tags=rock&tags=pop')
    })

    it('skips NaN in arrays', () => {
      const result = toQueryString({ ids: [1, NaN, 3] })
      expect(result).toBe('?ids=1&ids=3')
    })

    it('returns empty for empty array', () => {
      expect(toQueryString({ tags: [] })).toBe('')
    })

    it('returns empty for array of all null/undefined', () => {
      expect(toQueryString({ tags: [null, undefined] })).toBe('')
    })
  })

  describe('mixed values', () => {
    it('handles object with mixed types', () => {
      const result = toQueryString({
        query: 'test',
        page: 1,
        active: true,
        missing: undefined,
        tags: ['rock', 'pop'],
      })
      expect(result).toContain('query=test')
      expect(result).toContain('page=1')
      expect(result).toContain('active=true')
      expect(result).toContain('tags=rock')
      expect(result).toContain('tags=pop')
      expect(result).not.toContain('missing')
    })
  })

  describe('URL encoding', () => {
    it('encodes special characters', () => {
      const result = toQueryString({ query: 'hello world' })
      expect(result).toBe('?query=hello+world')
    })

    it('encodes ampersand', () => {
      const result = toQueryString({ query: 'rock & roll' })
      expect(result).toContain('%26')
    })

    it('encodes equals sign', () => {
      const result = toQueryString({ query: 'a=b' })
      expect(result).toContain('%3D')
    })
  })

  describe('edge cases', () => {
    it('handles object values by converting to string', () => {
      const obj = { toString: () => 'custom-string' }
      const result = toQueryString({ value: obj })
      expect(result).toBe('?value=custom-string')
    })

    it('handles object values in arrays by converting to string', () => {
      const obj1 = { toString: () => 'obj1' }
      const obj2 = { toString: () => 'obj2' }
      const result = toQueryString({ items: [obj1, obj2] })
      expect(result).toBe('?items=obj1&items=obj2')
    })
  })
})
