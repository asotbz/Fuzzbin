import { setupServer } from 'msw/node'
import { handlers } from './handlers'

/**
 * MSW server for Node.js environment (Vitest tests).
 * 
 * Setup is handled automatically in src/test/setup.ts.
 * 
 * To override handlers in a specific test:
 * 
 *   import { server } from '../mocks/server'
 *   import { rateLimitedLogin } from '../mocks/handlers/overrides'
 * 
 *   test('handles rate limiting', async () => {
 *     server.use(rateLimitedLogin) // Override for this test only
 *     // ... test code
 *   })
 */
export const server = setupServer(...handlers)
