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

// Test user credentials - should match backend seed data
// Default is admin/changeme from migrations/001_initial_schema.sql
const TEST_USER = {
  username: process.env.E2E_TEST_USERNAME || 'admin',
  password: process.env.E2E_TEST_PASSWORD || 'changeme',
}

// New password to set if password change is required
const NEW_PASSWORD = process.env.E2E_TEST_NEW_PASSWORD || 'e2e-test-password-123'

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
  
  // Wait for redirect - could be library or password change page
  await expect(page).toHaveURL(/\/library|\/set-initial-password/, { timeout: 10000 })
  
  // Handle password change flow if required
  if (page.url().includes('set-initial-password')) {
    // Fill in password change form
    const currentPasswordInput = page.getByLabel(/current password/i)
    const newPasswordInput = page.getByLabel(/^new password$/i)
    const confirmPasswordInput = page.getByLabel(/confirm.*password/i)
    
    await currentPasswordInput.fill(TEST_USER.password)
    await newPasswordInput.fill(NEW_PASSWORD)
    await confirmPasswordInput.fill(NEW_PASSWORD)
    
    // Submit password change
    await page.getByRole('button', { name: /change password|submit|save/i }).click()
    
    // Wait for redirect to library after password change
    await expect(page).toHaveURL(/\/library/, { timeout: 10000 })
  }
  
  // Verify we see the library content
  await expect(page.getByText(/video library/i)).toBeVisible()
  
  // Save the authenticated state
  await page.context().storageState({ path: authFile })
})
