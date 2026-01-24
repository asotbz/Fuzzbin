import { describe, it, expect } from 'vitest'
import { videosKeys, searchKeys, addKeys, jobsKeys, configKeys } from '../queryKeys'

describe('queryKeys', () => {
  describe('videosKeys', () => {
    it('all returns base key', () => {
      expect(videosKeys.all).toEqual(['videos'])
    })

    it('lists builds on all', () => {
      expect(videosKeys.lists()).toEqual(['videos', 'list'])
    })

    it('list includes query params', () => {
      const query = { page: 1, page_size: 20, title: 'test' }
      expect(videosKeys.list(query)).toEqual(['videos', 'list', query])
    })

    it('byId includes video ID', () => {
      expect(videosKeys.byId(123)).toEqual(['videos', 'detail', 123])
    })
  })

  describe('searchKeys', () => {
    it('all returns base key', () => {
      expect(searchKeys.all).toEqual(['search'])
    })

    it('facets includes query', () => {
      const query = { include_deleted: true }
      expect(searchKeys.facets(query)).toEqual(['search', 'facets', query])
    })
  })

  describe('addKeys', () => {
    it('all returns base key', () => {
      expect(addKeys.all).toEqual(['add'])
    })

    it('preview includes source and itemId', () => {
      expect(addKeys.preview('imvdb', 'item-123')).toEqual(['add', 'preview', 'imvdb', 'item-123'])
    })
  })

  describe('jobsKeys', () => {
    it('all returns base key', () => {
      expect(jobsKeys.all).toEqual(['jobs'])
    })

    it('byId includes job ID', () => {
      expect(jobsKeys.byId('job-abc')).toEqual(['jobs', 'job-abc'])
    })
  })

  describe('configKeys', () => {
    it('all returns base key', () => {
      expect(configKeys.all).toEqual(['config'])
    })

    it('config returns current config key', () => {
      expect(configKeys.config()).toEqual(['config', 'current'])
    })

    it('history returns history key', () => {
      expect(configKeys.history()).toEqual(['config', 'history'])
    })

    it('field includes field path', () => {
      expect(configKeys.field('apis.discogs.api_key')).toEqual(['config', 'field', 'apis.discogs.api_key'])
    })

    it('safety includes path', () => {
      expect(configKeys.safety('server.port')).toEqual(['config', 'safety', 'server.port'])
    })
  })
})
