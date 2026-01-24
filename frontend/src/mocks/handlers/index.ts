import { authHandlers } from './auth'
import { videosHandlers } from './videos'
import { searchHandlers } from './search'
import { addHandlers } from './add'
import { jobsHandlers } from './jobs'
import { configHandlers } from './config'
import { spotifyHandlers } from './spotify'

// Combine all handlers - these are the default happy-path handlers
export const handlers = [
  ...authHandlers,
  ...videosHandlers,
  ...searchHandlers,
  ...addHandlers,
  ...jobsHandlers,
  ...configHandlers,
  ...spotifyHandlers,
]

// Re-export individual handler groups for selective use in tests
export { authHandlers } from './auth'
export { videosHandlers } from './videos'
export { searchHandlers } from './search'
export { addHandlers } from './add'
export { jobsHandlers } from './jobs'
export { configHandlers } from './config'
export { spotifyHandlers } from './spotify'

// Re-export test fixtures
export { TEST_USER, TEST_TOKENS, REFRESHED_TOKENS } from './auth'
export { mockVideos } from './videos'
export { mockFacets } from './search'
export { mockSearchResults, mockPreview } from './add'
export { mockJobs } from './jobs'
export { mockConfig, mockConfigHistory } from './config'
export { mockSpotifyEnrichResponse, mockYouTubeSearchResponse, mockYouTubeMetadataResponse } from './spotify'
