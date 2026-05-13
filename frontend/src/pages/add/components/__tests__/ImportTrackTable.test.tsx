import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { server } from '../../../../mocks/server'
import { mockSpotifyEnrichResponse } from '../../../../mocks/handlers/spotify'
import ImportTrackTable from '../ImportTrackTable'
import type { BatchPreviewItem } from '../../../../lib/api/types'

const BASE_URL = 'http://localhost:8000'

function makeTrack(overrides: Partial<BatchPreviewItem> = {}): BatchPreviewItem {
  return {
    kind: 'spotify_track',
    title: 'Some Title',
    artist: 'Some Artist',
    album: 'Some Album',
    year: 2020,
    label: null,
    isrc: null,
    already_exists: false,
    spotify_track_id: 'sp-1',
    spotify_playlist_id: null,
    spotify_artist_id: null,
    artist_genres: null,
    nfo_path: null,
    ...overrides,
  } as BatchPreviewItem
}

function renderTable(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

const noopProps = {
  metadataOverrides: new Map(),
  onEnrichmentComplete: vi.fn(),
  onEditTrack: vi.fn(),
  onSearchYouTube: vi.fn(),
}

describe('ImportTrackTable', () => {
  let enrichCalls: Array<{ spotify_track_id: string }>

  beforeEach(() => {
    enrichCalls = []
    // Capture every enrich-track call so we can assert which tracks were
    // visited by the sequential enrichment state machine.
    server.use(
      http.post(`${BASE_URL}/add/spotify/enrich-track`, async ({ request }) => {
        const body = (await request.json()) as { spotify_track_id: string }
        enrichCalls.push({ spotify_track_id: body.spotify_track_id })
        return HttpResponse.json({
          ...mockSpotifyEnrichResponse,
          spotify_track_id: body.spotify_track_id,
        })
      })
    )
  })

  it('kicks off enrichment on first render for non-existing tracks', async () => {
    // Regression test for the rubber-duck-identified bug: lazy useState
    // initializers must populate trackStates from the initial `tracks`
    // prop, otherwise advanceEnrichment short-circuits on
    // trackStates.size === 0 and never fires.
    const tracks = [
      makeTrack({ spotify_track_id: 'sp-1', title: 'T1' }),
      makeTrack({ spotify_track_id: 'sp-2', title: 'T2' }),
    ]

    renderTable(<ImportTrackTable tracks={tracks} {...noopProps} />)

    await waitFor(() => expect(enrichCalls.length).toBeGreaterThanOrEqual(2))
    expect(enrichCalls.map((c) => c.spotify_track_id).sort()).toEqual(['sp-1', 'sp-2'])
  })

  it('auto-selects only new tracks (skips already_exists)', async () => {
    const tracks = [
      makeTrack({ spotify_track_id: 'new-1', title: 'New', already_exists: false }),
      makeTrack({ spotify_track_id: 'old-1', title: 'Old', already_exists: true }),
    ]

    renderTable(<ImportTrackTable tracks={tracks} {...noopProps} />)

    expect(
      await screen.findByText(/^1 track selected$/i)
    ).toBeInTheDocument()
  })

  it('does not call enrich for tracks that already exist', async () => {
    const tracks = [
      makeTrack({ spotify_track_id: 'old-1', title: 'Old', already_exists: true }),
      makeTrack({ spotify_track_id: 'old-2', title: 'Old 2', already_exists: true }),
    ]

    renderTable(<ImportTrackTable tracks={tracks} {...noopProps} />)

    // No "Enriching tracks: x/y" progress should show when all are already-existing.
    await waitFor(() => {
      expect(screen.queryByText(/Enriching tracks:/i)).not.toBeInTheDocument()
    })
    expect(enrichCalls).toHaveLength(0)
  })

  it('reports selection count through onSelectionChange after deselect', async () => {
    const onSelectionChange = vi.fn()
    const tracks = [
      makeTrack({ spotify_track_id: 'sp-a', title: 'A' }),
      makeTrack({ spotify_track_id: 'sp-b', title: 'B' }),
    ]

    renderTable(
      <ImportTrackTable
        tracks={tracks}
        {...noopProps}
        onSelectionChange={onSelectionChange}
      />
    )

    // After mount both new tracks are auto-selected.
    await waitFor(() => {
      expect(onSelectionChange).toHaveBeenCalled()
      const lastCall = onSelectionChange.mock.calls.at(-1)?.[0] as Set<string>
      expect(lastCall.size).toBe(2)
    })

    // Click the header "select all" checkbox to deselect everything.
    const headerCheckbox = screen.getByTitle('Select all new tracks')
    fireEvent.click(headerCheckbox)

    await waitFor(() => {
      const lastCall = onSelectionChange.mock.calls.at(-1)?.[0] as Set<string>
      expect(lastCall.size).toBe(0)
    })
  })

  it('re-initializes when the tracks prop is replaced post-mount', async () => {
    const initial = [makeTrack({ spotify_track_id: 'sp-x', title: 'X' })]
    const { rerender } = renderTable(
      <ImportTrackTable tracks={initial} {...noopProps} />
    )

    await waitFor(() => expect(enrichCalls.length).toBeGreaterThanOrEqual(1))
    expect(enrichCalls[0].spotify_track_id).toBe('sp-x')

    // Different playlist preview: brand-new tracks array reference.
    const replacement = [
      makeTrack({ spotify_track_id: 'sp-y', title: 'Y' }),
      makeTrack({ spotify_track_id: 'sp-z', title: 'Z' }),
    ]
    rerender(
      <QueryClientProvider client={new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      })}>
        <ImportTrackTable tracks={replacement} {...noopProps} />
      </QueryClientProvider>
    )

    await waitFor(() =>
      expect(
        enrichCalls.some((c) => c.spotify_track_id === 'sp-y') &&
          enrichCalls.some((c) => c.spotify_track_id === 'sp-z')
      ).toBe(true)
    )
  })
})
