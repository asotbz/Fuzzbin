import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
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
