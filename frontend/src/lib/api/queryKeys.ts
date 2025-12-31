import type { FacetsQuery, ListVideosQuery } from './types'

export const videosKeys = {
  all: ['videos'] as const,
  lists: () => [...videosKeys.all, 'list'] as const,
  list: (query: ListVideosQuery) => [...videosKeys.lists(), query] as const,
}

export const searchKeys = {
  all: ['search'] as const,
  facets: (query: FacetsQuery) => [...searchKeys.all, 'facets', query] as const,
}

export const addKeys = {
  all: ['add'] as const,
  preview: (source: string, itemId: string) => [...addKeys.all, 'preview', source, itemId] as const,
}

export const jobsKeys = {
  all: ['jobs'] as const,
  byId: (jobId: string) => [...jobsKeys.all, jobId] as const,
}

export const configKeys = {
  all: ['config'] as const,
  config: () => [...configKeys.all, 'current'] as const,
  history: () => [...configKeys.all, 'history'] as const,
  field: (path: string) => [...configKeys.all, 'field', path] as const,
  safety: (path: string) => [...configKeys.all, 'safety', path] as const,
}
