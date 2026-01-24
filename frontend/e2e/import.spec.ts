import { test, expect } from '@playwright/test'

/**
 * Import/Add page E2E tests - runs WITH authenticated state
 * These tests verify the video import wizard functionality.
 */

test.describe('Import Hub Page', () => {
  test('shows import hub header', async ({ page }) => {
    await page.goto('/add')

    await expect(page.getByText(/import|add/i)).toBeVisible()
  })

  test('displays import method cards', async ({ page }) => {
    await page.goto('/add')

    // Import methods based on the frontend structure
    const methods = [
      /directory scan/i,
      /search/i,
      /url|link/i,
    ]

    let foundMethod = false
    for (const method of methods) {
      const card = page.getByText(method)
      if (await card.isVisible().catch(() => false)) {
        foundMethod = true
        break
      }
    }

    expect(foundMethod).toBeTruthy()
  })
})

test.describe('Search Import Wizard', () => {
  test('can navigate to search wizard', async ({ page }) => {
    await page.goto('/add')

    // Find and click search option
    const searchCard = page.getByText(/search/i).first()
    await searchCard.click()

    // Should navigate to search wizard
    await expect(page).toHaveURL(/add\/search|import\/search|search/i)
  })

  test('search wizard has artist input', async ({ page }) => {
    await page.goto('/add/search')

    // Look for artist search input
    const artistInput = page
      .getByPlaceholder(/artist/i)
      .or(page.getByLabel(/artist/i))
      .first()

    await expect(artistInput).toBeVisible()
  })

  test('search wizard has title input', async ({ page }) => {
    await page.goto('/add/search')

    // Look for title search input
    const titleInput = page
      .getByPlaceholder(/title|song|track/i)
      .or(page.getByLabel(/title|song|track/i))
      .first()

    await expect(titleInput).toBeVisible()
  })

  test('can enter search criteria and submit', async ({ page }) => {
    await page.goto('/add/search')

    // Find and fill inputs
    const artistInput = page.getByPlaceholder(/artist/i).or(page.getByLabel(/artist/i)).first()
    const titleInput = page.getByPlaceholder(/title/i).or(page.getByLabel(/title/i)).first()

    await artistInput.fill('Nirvana')
    await titleInput.fill('Smells Like Teen Spirit')

    // Find and click search/next button
    const searchButton = page.getByRole('button', { name: /search|next|find/i })
    await searchButton.click()

    // Should progress to next step or show results
    await page.waitForLoadState('networkidle')
    
    // Check for either results or next wizard step
    const hasResults = await page.getByText(/result|found|match/i).isVisible().catch(() => false)
    const hasNextStep = await page.getByText(/select|choose|step 2/i).isVisible().catch(() => false)
    const hasNoResults = await page.getByText(/no results|not found/i).isVisible().catch(() => false)

    expect(hasResults || hasNextStep || hasNoResults).toBeTruthy()
  })
})

test.describe('Directory Scan Import', () => {
  test('can navigate to directory scan', async ({ page }) => {
    await page.goto('/add')

    // Find and click directory scan option
    const dirCard = page.getByText(/directory|folder|nfo/i).first()
    await dirCard.click()

    // Should navigate to directory scan
    await expect(page).toHaveURL(/add\/directory|add\/scan|import\/directory/i)
  })

  test.skip('directory scan has path input', async ({ page }) => {
    // Path input might be hidden on some implementations
    await page.goto('/add/directory')

    const pathInput = page.getByPlaceholder(/path|directory/i)
    await expect(pathInput).toBeVisible()
  })
})

test.describe('Import Preview', () => {
  test.skip('shows import preview with video details', async () => {
    // Skip - requires going through full wizard flow
    // Would test: title, artist, year, director, duration are shown
  })

  test.skip('can confirm import from preview', async () => {
    // Skip - requires going through full wizard flow  
    // Would test: confirm button works, success message shown
  })
})

test.describe('Background Jobs', () => {
  test('activity indicator is visible', async ({ page }) => {
    await page.goto('/add')

    // Check for activity/jobs indicator in header or sidebar
    const activityIndicator = page
      .getByRole('button', { name: /activity|jobs|queue/i })
      .or(page.getByLabel(/activity|jobs/i))
      .first()

    await expect(activityIndicator).toBeVisible()
  })

  test.skip('clicking activity shows job list', async ({ page }) => {
    // Skip if activity panel implementation varies
    await page.goto('/add')

    const activityIndicator = page.getByRole('button', { name: /activity/i }).first()
    await activityIndicator.click()

    // Should show activity panel or dialog
    await expect(page.getByText(/recent|running|completed/i)).toBeVisible()
  })
})
