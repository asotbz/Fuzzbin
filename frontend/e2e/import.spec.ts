import { test, expect } from '@playwright/test'

/**
 * Import page E2E tests - runs WITH authenticated state
 * These tests verify the video import wizard functionality.
 * 
 * Routes:
 * - /import - SearchWizard (Artist/Title Search)
 * - /import/spotify - Spotify Playlist Import
 * - /import/artist - Artist Videos Import
 * - /import/nfo - NFO Scan Import
 */

test.describe('Search Import Wizard', () => {
  test('shows search wizard page', async ({ page }) => {
    await page.goto('/import')

    // Should show the Artist/Title Search header
    await expect(page.getByText('Artist/Title Search')).toBeVisible()
  })

  test('has sub-navigation for import workflows', async ({ page }) => {
    await page.goto('/import')

    // Check for sub-navigation items
    await expect(page.getByRole('link', { name: 'Search' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Spotify Playlist' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Artist Videos' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'NFO Scan' })).toBeVisible()
  })

  test('has artist input field', async ({ page }) => {
    await page.goto('/import')

    const artistInput = page.getByPlaceholder('Enter artist name')
    await expect(artistInput).toBeVisible()
  })

  test('has track title input field', async ({ page }) => {
    await page.goto('/import')

    const titleInput = page.getByPlaceholder('Enter track title')
    await expect(titleInput).toBeVisible()
  })

  test('has search button', async ({ page }) => {
    await page.goto('/import')

    const searchButton = page.getByRole('button', { name: 'Search' })
    await expect(searchButton).toBeVisible()
  })

  test('can fill search form', async ({ page }) => {
    await page.goto('/import')

    const artistInput = page.getByPlaceholder('Enter artist name')
    const titleInput = page.getByPlaceholder('Enter track title')

    await artistInput.fill('Nirvana')
    await titleInput.fill('Smells Like Teen Spirit')

    await expect(artistInput).toHaveValue('Nirvana')
    await expect(titleInput).toHaveValue('Smells Like Teen Spirit')
  })
})

test.describe('Spotify Playlist Import', () => {
  test('can navigate to Spotify import', async ({ page }) => {
    await page.goto('/import')

    await page.getByRole('link', { name: 'Spotify Playlist' }).click()

    await expect(page).toHaveURL(/\/import\/spotify/)
  })
})

test.describe('Artist Videos Import', () => {
  test('can navigate to Artist Videos import', async ({ page }) => {
    await page.goto('/import')

    await page.getByRole('link', { name: 'Artist Videos' }).click()

    await expect(page).toHaveURL(/\/import\/artist/)
  })
})

test.describe('NFO Scan Import', () => {
  test('can navigate to NFO Scan import', async ({ page }) => {
    await page.goto('/import')

    await page.getByRole('link', { name: 'NFO Scan' }).click()

    await expect(page).toHaveURL(/\/import\/nfo/)
  })
})

test.describe('Navigation', () => {
  test('has navigation to library', async ({ page }) => {
    await page.goto('/import')

    const libraryLink = page.getByRole('link', { name: 'Library' })
    await expect(libraryLink).toBeVisible()
  })

  test('has navigation to activity', async ({ page }) => {
    await page.goto('/import')

    const activityLink = page.getByRole('link', { name: 'Activity' })
    await expect(activityLink).toBeVisible()
  })

  test('has navigation to settings', async ({ page }) => {
    await page.goto('/import')

    const settingsLink = page.getByRole('link', { name: 'Settings' })
    await expect(settingsLink).toBeVisible()
  })
})
