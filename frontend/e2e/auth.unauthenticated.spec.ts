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

  test('successful login redirects to library', async ({ page }) => {
    await page.goto('/login')

    // Use test credentials (default admin/changeme from DB seed)
    await page.getByPlaceholder('Username').fill('admin')
    await page.getByPlaceholder('Password').fill('changeme')
    
    // Listen for API responses to debug login issues
    page.on('response', response => {
      if (response.url().includes('/auth/login')) {
        console.log(`Login response: ${response.status()} ${response.statusText()}`)
      }
    })
    
    await page.getByRole('button', { name: 'Login' }).click()

    // Wait a moment for API call to complete
    await page.waitForTimeout(2000)
    
    // Check if there's an error shown on the page
    const errorElement = page.locator('.errorText, [class*="error"]')
    if (await errorElement.isVisible()) {
      const errorText = await errorElement.textContent()
      console.log(`Login error displayed: ${errorText}`)
    }

    // Should redirect to library (or password change if required)
    await expect(page).toHaveURL(/\/library|\/set-initial-password/, { timeout: 10000 })
  })

  test('redirects to login when accessing protected route unauthenticated', async ({ page }) => {
    // Try to access library without authentication
    await page.goto('/library')

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/)
  })

  test('redirects to login when accessing add page unauthenticated', async ({ page }) => {
    await page.goto('/add')

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
