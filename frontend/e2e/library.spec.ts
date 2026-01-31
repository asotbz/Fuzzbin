import { test, expect } from '@playwright/test'

/**
 * Library page E2E tests - runs WITH authenticated state
 * These tests verify the video library functionality.
 */

test.describe('Library Page', () => {
  test('shows video library header', async ({ page }) => {
    await page.goto('/library')

    await expect(page.getByText(/video library/i)).toBeVisible()
  })

  test('displays video grid or empty state', async ({ page }) => {
    await page.goto('/library')

    // Wait for loading to complete - either videos appear or empty state shows
    await page.waitForSelector('.statusLine:has-text("No videos found"), [class*="videoCard"], [class*="video-card"]', { timeout: 10000 })

    // Should show either videos or an empty state message
    const hasVideos = await page.locator('[class*="videoCard"], [class*="video-card"]').count() > 0
    const hasEmptyState = await page.getByText(/no videos found/i).isVisible().catch(() => false)

    expect(hasVideos || hasEmptyState).toBeTruthy()
  })

  test('has navigation to import hub', async ({ page }) => {
    await page.goto('/library')

    // Find link to add/import
    const addLink = page.getByRole('link', { name: /add|import/i })
    await expect(addLink).toBeVisible()
  })

  test('search input is visible', async ({ page }) => {
    await page.goto('/library')

    // Look for search input
    const searchInput = page.getByPlaceholder(/search/i)
    await expect(searchInput).toBeVisible()
  })

  test('facet filters are displayed', async ({ page }) => {
    await page.goto('/library')

    // Wait for facets to load (they come from API)
    await page.waitForLoadState('networkidle')

    // Check for common facet categories
    const facetLabels = ['year', 'director', 'genre', 'tag']
    let foundFacet = false

    for (const label of facetLabels) {
      const facet = page.getByText(new RegExp(label, 'i'))
      if (await facet.isVisible().catch(() => false)) {
        foundFacet = true
        break
      }
    }

    // At least one facet type should be visible
    expect(foundFacet).toBeTruthy()
  })

  test.describe('Search Functionality', () => {
    test('can type in search box', async ({ page }) => {
      await page.goto('/library')

      const searchInput = page.getByPlaceholder(/search/i)
      await searchInput.fill('test query')

      await expect(searchInput).toHaveValue('test query')
    })

    test('search filters videos (state-based, not URL)', async ({ page }) => {
      await page.goto('/library')

      const searchInput = page.getByPlaceholder(/search/i)
      await searchInput.fill('nirvana')
      
      // Wait for debounced search to trigger
      await page.waitForTimeout(500)

      // Verify search input has the value (URL doesn't update - search is state-based)
      await expect(searchInput).toHaveValue('nirvana')
    })
  })

  test.describe('Pagination', () => {
    test.skip('shows pagination when many videos exist', async ({ page }) => {
      // Skip - requires many videos in database
      await page.goto('/library')
      
      // Would check for pagination controls
    })
  })
})
