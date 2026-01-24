import { describe, it, expect } from 'vitest'
import {
  removeVersionQualifiers,
  getDisplayTrackTitle,
  getDisplayAlbumTitle,
  removeFeaturedArtists,
} from '../titleUtils'

describe('titleUtils', () => {
  describe('removeVersionQualifiers', () => {
    describe('parenthetical qualifiers', () => {
      it('removes (Remastered) suffix', () => {
        expect(removeVersionQualifiers('Jump (Remastered)')).toBe('Jump')
      })

      it('removes (Remaster) suffix', () => {
        expect(removeVersionQualifiers('Jump (Remaster)')).toBe('Jump')
      })

      it('removes (2015 Remaster) suffix', () => {
        expect(removeVersionQualifiers('Jump (2015 Remaster)')).toBe('Jump')
      })

      it('removes (Deluxe Edition) suffix', () => {
        expect(removeVersionQualifiers('1984 (Deluxe Edition)')).toBe('1984')
      })

      it('removes (Expanded Edition) suffix', () => {
        expect(removeVersionQualifiers('Heartbeat City (Expanded Edition)')).toBe('Heartbeat City')
      })

      it('removes (Anniversary Edition) suffix', () => {
        expect(removeVersionQualifiers('Album (Anniversary Edition)')).toBe('Album')
      })

      it('removes (Radio Edit) suffix', () => {
        expect(removeVersionQualifiers('Song (Radio Edit)')).toBe('Song')
      })

      it('removes (Single Version) suffix', () => {
        expect(removeVersionQualifiers('Track (Single Version)')).toBe('Track')
      })

      it('removes (Live) suffix', () => {
        expect(removeVersionQualifiers('Concert (Live)')).toBe('Concert')
      })

      it('removes (Acoustic) suffix', () => {
        expect(removeVersionQualifiers('Ballad (Acoustic)')).toBe('Ballad')
      })

      it('removes (Explicit) suffix', () => {
        expect(removeVersionQualifiers('Track (Explicit)')).toBe('Track')
      })

      it('removes (Instrumental) suffix', () => {
        expect(removeVersionQualifiers('Song (Instrumental)')).toBe('Song')
      })

      it("removes (Collector's Edition) suffix", () => {
        expect(removeVersionQualifiers("Album (Collector's Edition)")).toBe('Album')
      })
    })

    describe('hyphenated qualifiers', () => {
      it('removes - 2015 Remaster suffix', () => {
        expect(removeVersionQualifiers('Jump - 2015 Remaster')).toBe('Jump')
      })

      it('removes - Remastered suffix', () => {
        expect(removeVersionQualifiers('Track - Remastered')).toBe('Track')
      })

      it('removes - Radio Edit suffix', () => {
        expect(removeVersionQualifiers('Song - Radio Edit')).toBe('Song')
      })

      it('removes - Live suffix', () => {
        expect(removeVersionQualifiers('Concert - Live')).toBe('Concert')
      })

      it('removes - Acoustic suffix', () => {
        expect(removeVersionQualifiers('Ballad - Acoustic')).toBe('Ballad')
      })

      it('removes soundtrack reference', () => {
        expect(removeVersionQualifiers('Theme - From "Movie" Soundtrack')).toBe('Theme')
      })
    })

    describe('bracketed qualifiers', () => {
      it('removes [Remastered] suffix', () => {
        expect(removeVersionQualifiers('Track [Remastered]')).toBe('Track')
      })

      it('removes [Deluxe Edition] suffix', () => {
        expect(removeVersionQualifiers('Album [Deluxe Edition]')).toBe('Album')
      })
    })

    describe('edge cases', () => {
      it('preserves titles starting with parentheses', () => {
        expect(removeVersionQualifiers("(What's the Story) Morning Glory?")).toBe(
          "(What's the Story) Morning Glory?"
        )
      })

      it('handles multiple qualifiers', () => {
        expect(removeVersionQualifiers('Song (Deluxe) - Remastered')).toBe('Song')
      })

      it('preserves original title without qualifiers', () => {
        expect(removeVersionQualifiers('Normal Song Title')).toBe('Normal Song Title')
      })

      it('trims whitespace', () => {
        expect(removeVersionQualifiers('  Song (Remastered)  ')).toBe('Song')
      })

      it('handles empty string', () => {
        expect(removeVersionQualifiers('')).toBe('')
      })

      it('handles title that is only whitespace', () => {
        expect(removeVersionQualifiers('   ')).toBe('')
      })

      it('preserves mid-title parentheses', () => {
        // Parentheses that are part of the title (not at end)
        expect(removeVersionQualifiers('Song (Part 1) of Album')).toBe('Song (Part 1) of Album')
      })

      it('is case-insensitive', () => {
        expect(removeVersionQualifiers('Track (REMASTERED)')).toBe('Track')
        expect(removeVersionQualifiers('Track (remastered)')).toBe('Track')
        expect(removeVersionQualifiers('Track (ReMasTeReD)')).toBe('Track')
      })
    })
  })

  describe('getDisplayTrackTitle', () => {
    it('returns enrichment title when available', () => {
      expect(getDisplayTrackTitle('Spotify Title', 'IMVDb Title')).toBe('IMVDb Title')
    })

    it('returns Spotify title when enrichment is null', () => {
      expect(getDisplayTrackTitle('Spotify Title', null)).toBe('Spotify Title')
    })

    it('returns Spotify title when enrichment is undefined', () => {
      expect(getDisplayTrackTitle('Spotify Title', undefined)).toBe('Spotify Title')
    })

    it('returns Spotify title when enrichment is empty string', () => {
      expect(getDisplayTrackTitle('Spotify Title', '')).toBe('Spotify Title')
    })
  })

  describe('getDisplayAlbumTitle', () => {
    it('removes version qualifiers from album title', () => {
      expect(getDisplayAlbumTitle('1984 (Remastered)')).toBe('1984')
    })

    it('removes expanded edition from album title', () => {
      expect(getDisplayAlbumTitle('Heartbeat City (Expanded Edition)')).toBe('Heartbeat City')
    })

    it('returns null for null input', () => {
      expect(getDisplayAlbumTitle(null)).toBeNull()
    })

    it('preserves album title without qualifiers', () => {
      expect(getDisplayAlbumTitle('Normal Album')).toBe('Normal Album')
    })
  })

  describe('removeFeaturedArtists', () => {
    describe('standalone patterns', () => {
      it('removes ft. pattern', () => {
        expect(removeFeaturedArtists('Robin Thicke ft. T.I.')).toBe('Robin Thicke')
      })

      it('removes feat. pattern', () => {
        expect(removeFeaturedArtists('Artist feat. Other Artist')).toBe('Artist')
      })

      it('removes featuring pattern', () => {
        expect(removeFeaturedArtists('Main Artist featuring Guest')).toBe('Main Artist')
      })

      it('removes f/ pattern', () => {
        expect(removeFeaturedArtists('Artist f/ Another')).toBe('Artist')
      })

      it('removes ft without period', () => {
        expect(removeFeaturedArtists('Artist ft Other')).toBe('Artist')
      })

      it('removes feat without period', () => {
        expect(removeFeaturedArtists('Artist feat Other')).toBe('Artist')
      })
    })

    describe('parenthetical patterns', () => {
      it('removes (feat. Artist) pattern', () => {
        expect(removeFeaturedArtists('The Warrior (feat. Patty Smyth)')).toBe('The Warrior')
      })

      it('removes (ft. Artist) pattern', () => {
        expect(removeFeaturedArtists('Song Title (ft. Guest Artist)')).toBe('Song Title')
      })

      it('removes (featuring Artist) pattern', () => {
        expect(removeFeaturedArtists('Track (featuring Singer)')).toBe('Track')
      })
    })

    describe('edge cases', () => {
      it('handles multiple featured artists', () => {
        expect(removeFeaturedArtists('Artist feat. Other & Another')).toBe('Artist')
      })

      it('preserves text without featured artists', () => {
        expect(removeFeaturedArtists('Normal Artist Name')).toBe('Normal Artist Name')
      })

      it('trims whitespace after removal', () => {
        expect(removeFeaturedArtists('Artist   ft. Other')).toBe('Artist')
      })

      it('handles empty string', () => {
        expect(removeFeaturedArtists('')).toBe('')
      })

      it('is case-insensitive', () => {
        expect(removeFeaturedArtists('Artist FT. Other')).toBe('Artist')
        expect(removeFeaturedArtists('Artist FEAT. Other')).toBe('Artist')
        expect(removeFeaturedArtists('Artist FEATURING Other')).toBe('Artist')
      })

      it('handles both parenthetical and standalone patterns', () => {
        // Edge case: both patterns present (unusual but possible)
        expect(removeFeaturedArtists('Song (feat. A) ft. B')).toBe('Song')
      })
    })
  })
})
