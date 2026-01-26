import { test, expect } from '@playwright/test'

/**
 * Authentication E2E tests - runs WITHOUT stored auth state
 * These tests verify the login flow and authentication-related functionality.
 */

test.describe('Login Page', () => {
  test('shows login form', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByPlaceholder('Username')).toBeVisible()
    await expect(page.getByPlaceholder('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Login' })).toBeVisible()
  })

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/login')

    await page.getByPlaceholder('Username').fill('wronguser')
    await page.getByPlaceholder('Password').fill('wrongpassword')
    await page.getByRole('button', { name: 'Login' }).click()

    // Should show error message
    await expect(page.getByText(/invalid|incorrect|failed/i)).toBeVisible({ timeout: 5000 })

    // Should stay on login page
    await expect(page).toHaveURL(/\/login/)
  })

  // Note: "successful login" test is covered by auth.setup.ts which handles
  // the full login flow including password change. We skip it here to avoid
  // conflicts when setup changes the password before this test runs.

  test('redirects to login when accessing protected route unauthenticated', async ({ page }) => {
    // Try to access library without authentication
    await page.goto('/library')

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/)
  })

  test('redirects to login when accessing import page unauthenticated', async ({ page }) => {
    await page.goto('/import')

    await expect(page).toHaveURL(/\/login/)
  })
})

test.describe('Password Change Flow', () => {
  test.skip('shows password change form when required', async ({ page }) => {
    // This test requires a user with password_change_required flag
    // Skip for now - requires specific backend state
    await page.goto('/login')
    
    // Would need to log in with user that requires password change
    // and verify redirect to /set-initial-password
  })
})
