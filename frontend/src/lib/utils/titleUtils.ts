/**
 * Utility functions for normalizing and cleaning track/album titles.
 *
 * These functions mirror the backend normalization logic in string_utils.py
 * but preserve capitalization for display purposes.
 */

/**
 * Remove version/edition qualifiers from track or album titles while preserving capitalization.
 *
 * Removes common qualifiers that Spotify adds to remastered/deluxe/special editions:
 * - Parenthetical: (Remastered), (Deluxe Edition), (Anniversary Edition), etc.
 * - Hyphenated: - 2015 Remaster, - From "Movie" Soundtrack, - Radio Edit, etc.
 * - Bracketed: [Remastered], [Deluxe Edition], etc.
 *
 * Handles edge cases:
 * - Preserves titles that START with parentheses (e.g., "(What's the Story) Morning Glory?")
 * - Removes multiple qualifiers in sequence
 * - Handles nested parentheses in soundtrack references
 *
 * @param text - Title with potential version qualifiers
 * @returns Title with qualifiers removed and whitespace trimmed
 *
 * @example
 * removeVersionQualifiers("Jump - 2015 Remaster")
 * // Returns: "Jump"
 *
 * @example
 * removeVersionQualifiers("1984 (Remastered)")
 * // Returns: "1984"
 *
 * @example
 * removeVersionQualifiers("Heartbeat City (Expanded Edition)")
 * // Returns: "Heartbeat City"
 *
 * @example
 * removeVersionQualifiers("(What's the Story) Morning Glory?")
 * // Returns: "(What's the Story) Morning Glory?"
 */
export function removeVersionQualifiers(text: string): string {
  let result = text.trim()

  // Don't process titles that start with parentheses (they're part of the actual title)
  if (result.startsWith('(')) {
    return result
  }

  // Pattern for parenthetical qualifiers (must appear at end of string)
  // Matches: (Remastered), (Deluxe Edition), (2015 Remaster), etc.
  const parentheticalPattern = new RegExp(
    String.raw`\s*\([^)]*(?:` +
      String.raw`remaster(?:ed)?|deluxe|anniversary|expanded|edition|version|mix|edit|` +
      String.raw`live|acoustic|radio|single|album|explicit|clean|instrumental|karaoke|demo|bonus|` +
      String.raw`collector'?s?|limited|\d{4}\s*remaster` +
      String.raw`)\b[^)]*\)\s*$`,
    'i'
  )

  // Pattern for hyphenated qualifiers (must appear at end of string)
  // Matches: - 2015 Remaster, - From "Movie" Soundtrack, - Radio Edit, etc.
  const hyphenatedPattern = new RegExp(
    String.raw`\s*-\s*(?:` +
      String.raw`\d{4}\s*remaster(?:ed)?|` +
      String.raw`remaster(?:ed)?|` +
      String.raw`from\s+["'][^"']*["'](?:\s+(?:soundtrack|ost))?|` +
      String.raw`radio\s+edit|` +
      String.raw`single\s+version|` +
      String.raw`album\s+version|` +
      String.raw`live|` +
      String.raw`acoustic|` +
      String.raw`explicit|` +
      String.raw`clean|` +
      String.raw`instrumental` +
      String.raw`)\s*$`,
    'i'
  )

  // Pattern for bracketed qualifiers (less common, but some labels use them)
  // Matches: [Remastered], [Deluxe Edition], etc.
  const bracketedPattern = new RegExp(
    String.raw`\s*\[[^\]]*(?:` +
      String.raw`remaster(?:ed)?|deluxe|anniversary|expanded|edition|version` +
      String.raw`)\b[^\]]*\]\s*$`,
    'i'
  )

  // Apply patterns repeatedly until no more matches
  // (handles cases with multiple qualifiers like "Song (Deluxe) - Remastered")
  const maxIterations = 5 // Safety limit
  for (let i = 0; i < maxIterations; i++) {
    const original = result
    result = result.replace(parentheticalPattern, '').trim()
    result = result.replace(hyphenatedPattern, '').trim()
    result = result.replace(bracketedPattern, '').trim()

    // Stop if no changes were made
    if (result === original) {
      break
    }
  }

  return result
}

/**
 * Get the display title for a track, preferring IMVDb enrichment data over Spotify metadata.
 *
 * Priority:
 * 1. IMVDb song_title (if enrichment data is available)
 * 2. Original Spotify track title
 *
 * @param spotifyTitle - Original track title from Spotify
 * @param enrichmentTitle - Optional track title from IMVDb enrichment
 * @returns The best available track title for display
 */
export function getDisplayTrackTitle(
  spotifyTitle: string,
  enrichmentTitle?: string | null
): string {
  // Use IMVDb title if available, otherwise use Spotify title
  return enrichmentTitle || spotifyTitle
}

/**
 * Get the display album title, removing version qualifiers while preserving capitalization.
 *
 * @param spotifyAlbum - Original album name from Spotify
 * @returns Album name with version qualifiers removed
 *
 * @example
 * getDisplayAlbumTitle("1984 (Remastered)")
 * // Returns: "1984"
 *
 * @example
 * getDisplayAlbumTitle("Heartbeat City (Expanded Edition)")
 * // Returns: "Heartbeat City"
 */
export function getDisplayAlbumTitle(spotifyAlbum: string | null): string | null {
  if (!spotifyAlbum) {
    return null
  }
  return removeVersionQualifiers(spotifyAlbum)
}

/**
 * Remove featured artists from a string.
 *
 * Detects patterns like "ft.", "feat.", "featuring", "f/" (case-insensitive)
 * and removes everything after the pattern, including the pattern itself.
 * Handles both standalone and parenthetical notations.
 *
 * @param text - String potentially containing featured artist notation
 * @returns String with featured artists removed
 *
 * @example
 * removeFeaturedArtists("Robin Thicke ft. T.I.")
 * // Returns: "Robin Thicke"
 *
 * @example
 * removeFeaturedArtists("The Warrior (feat. Patty Smyth)")
 * // Returns: "The Warrior"
 *
 * @example
 * removeFeaturedArtists("Artist feat. Other & Another")
 * // Returns: "Artist"
 */
export function removeFeaturedArtists(text: string): string {
  let result = text

  // First, handle parenthetical featured artists: (feat. X), (ft. X), etc.
  // This removes the entire parenthetical including the parentheses
  const parentheticalPattern = /\s*\((?:ft\.?|feat\.?|featuring|f\/)[^)]*\)/gi
  result = result.replace(parentheticalPattern, '')

  // Then handle standalone featured artists: "ft. X", "feat. X", etc.
  // Pattern matches: ft., ft, feat., feat, featuring, f/
  // Handle both mid-string and start-of-string cases
  const standalonePattern = /(?:^|\s+)(?:ft\.?|feat\.?|featuring|f\/)(?:\s+.*)?$/i
  result = result.replace(standalonePattern, '')

  return result.trim()
}
