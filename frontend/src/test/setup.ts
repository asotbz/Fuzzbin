import '@testing-library/jest-dom/vitest'
import { beforeAll, afterEach, afterAll, vi } from 'vitest'
import { server } from '../mocks/server'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
    get length() {
      return Object.keys(store).length
    },
    key: vi.fn((index: number) => Object.keys(store)[index] || null),
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// Set window.location.origin to match MSW mock handlers
// This is needed because the API client uses window.location.origin when VITE_API_BASE_URL is not set
Object.defineProperty(window, 'location', {
  value: {
    ...window.location,
    origin: 'http://localhost:8000',
    href: 'http://localhost:8000/',
    protocol: 'http:',
    host: 'localhost:8000',
    hostname: 'localhost',
    port: '8000',
  },
  writable: true,
})

// Start MSW server before all tests
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

// Reset handlers after each test (removes any runtime overrides)
afterEach(() => {
  server.resetHandlers()
  localStorageMock.clear()
})

// Clean up after all tests
afterAll(() => {
  server.close()
})
