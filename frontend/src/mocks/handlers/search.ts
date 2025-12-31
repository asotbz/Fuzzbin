import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const mockFacets = {
  years: [
    { value: '2024', count: 3 },
    { value: '2023', count: 4 },
  ],
  directors: [
    { value: 'Test Director', count: 2 },
  ],
  genres: [],
  tags: [],
  total_videos: 7,
}

export const searchHandlers = [
  // Get facets
  http.get(`${BASE_URL}/search/facets`, () => {
    return HttpResponse.json(mockFacets)
  }),

  // Get suggestions
  http.get(`${BASE_URL}/search/suggestions`, ({ request }) => {
    const url = new URL(request.url)
    const q = url.searchParams.get('q') || ''

    // Return suggestions in correct format
    const titles: string[] = []
    const artists: string[] = []
    const albums: string[] = []

    if ('test'.includes(q.toLowerCase()) || q.toLowerCase().includes('test')) {
      artists.push('Test Artist')
      titles.push('Test Music Video')
      albums.push('Test Album')
    }

    return HttpResponse.json({ titles, artists, albums })
  }),
]
