import { test as setup, expect } from '@playwright/test'
import path from 'path'

const authFile = path.join(__dirname, '.auth/user.json')

/**
 * Authentication setup for Playwright E2E tests.
 * 
 * This runs before all other tests and stores the authenticated state
 * so subsequent tests can skip the login process.
 * 
 * Prerequisites:
 * - Backend server running at http://localhost:8000
 * - Frontend dev server running at http://localhost:5173
 * - Test user credentials configured (see below)
 */

// Test user credentials - should match backend test fixtures
const TEST_USER = {
  username: process.env.E2E_TEST_USERNAME || 'admin',
  password: process.env.E2E_TEST_PASSWORD || 'admin',
}

setup('authenticate', async ({ page }) => {
  // Navigate to login page
  await page.goto('/login')
  
  // Verify we're on the login page
  await expect(page.getByPlaceholder('Username')).toBeVisible()
  
  // Fill in credentials
  await page.getByPlaceholder('Username').fill(TEST_USER.username)
  await page.getByPlaceholder('Password').fill(TEST_USER.password)
  
  // Submit the form
  await page.getByRole('button', { name: /sign in|log in/i }).click()
  
  // Wait for redirect to library page (indicates successful login)
  await expect(page).toHaveURL(/\/library/, { timeout: 10000 })
  
  // Verify we see the library content
  await expect(page.getByText(/video library/i)).toBeVisible()
  
  // Save the authenticated state
  await page.context().storageState({ path: authFile })
})
