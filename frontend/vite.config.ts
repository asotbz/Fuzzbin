import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API and WebSocket requests to the backend
      '/auth': 'http://localhost:8000',
      '/videos': 'http://localhost:8000',
      '/artists': 'http://localhost:8000',
      '/collections': 'http://localhost:8000',
      '/tags': 'http://localhost:8000',
      '/search': 'http://localhost:8000',
      '/files': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/add': 'http://localhost:8000',
      '/imvdb': 'http://localhost:8000',
      '/discogs': 'http://localhost:8000',
      '/spotify': 'http://localhost:8000',
      '/exports': 'http://localhost:8000',
      '/backup': 'http://localhost:8000',
      '/config': 'http://localhost:8000',
      '/genres': 'http://localhost:8000',
      '/ytdlp': 'http://localhost:8000',
      '/scan': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/ws': {
        target: 'http://localhost:8000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    exclude: [
      'node_modules/**',
      'e2e/**',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'node_modules/**',
        'src/test/**',
        'src/mocks/**',
        'src/lib/api/generated.ts',
        'src/lib/api/types.ts',
        '**/*.d.ts',
        '**/*.config.ts',
        '**/index.ts',
        'src/main.tsx',
      ],
      thresholds: {
        // Phase 1 target: 30% coverage
        lines: 30,
        branches: 30,
        functions: 30,
        statements: 30,
      },
    },
  },
})
