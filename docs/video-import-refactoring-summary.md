# Video Import Refactoring - Executive Summary

## Quick Overview

This plan enhances Fuzzbin's video import process to better handle NFO metadata files and improve automatic metadata extraction.

## What's Changing

### 1. NFO File Support ✨ **NEW**
- **Automatically discover NFO files** next to video files
- **Parse Kodi-compatible `<musicvideo>` schema** 
- **Extract metadata:** artist(s), title, year, album, genres, tags, record label, directors, source URLs
- **Priority:** NFO metadata takes precedence over filename parsing

### 2. Enhanced Filename Parsing 🎯 **IMPROVED**
- Support more filename patterns (brackets, underscores, etc.)
- Extract **featured artists** (feat., ft., with, &, x)
- Better year detection from various positions
- Remove common suffixes (Official Video, HD, 4K, etc.)

### 3. Smarter Metadata Cache Integration 🧠 **IMPROVED**
- Query IMVDb/MusicBrainz **during scan** (not just at commit)
- Show **confidence scores** in review UI
- Auto-apply high-confidence matches (>95%)
- Store multiple match options for user review

## Key Benefits

| Feature | Before | After |
|---------|--------|-------|
| NFO Support | ❌ None | ✅ Full Kodi schema support |
| Featured Artists | ❌ Lost in title | ✅ Extracted and tracked |
| Metadata Confidence | ❌ Hidden | ✅ Visible in UI |
| Source URLs | ❌ Manual entry | ✅ Auto-extracted from NFO |
| Filename Patterns | 🟡 Basic | ✅ 10+ patterns |
| Metadata Source | ❌ Unknown | ✅ "NFO", "IMVDb", "Filename" |

## Example: Import Flow

### Before
```
1. Scan finds: "Artist - Title.mp4"
2. Parse filename → Artist, Title
3. User reviews in expansion panels → Commits
4. System tries to fetch metadata (maybe)
```

### After
```
1. Scan finds: "Taylor Swift feat. Future - End Game (2017).mp4" + NFO
2. Parse NFO → Extract:
   - Artist: "Taylor Swift" (primary)
   - Featured: ["Future", "Ed Sheeran"] (from artist + title fields)
   - Clean title: "End Game"
   - Year, genres, tags, director, source URLs
3. NFO incomplete? Query IMVDb/MusicBrainz → Get confidence scores
4. User reviews in TABLE view with color-coded status icons
5. "Needs review" items → Click button to select from candidates
6. Commits → System applies NFO + cache metadata comprehensively
```

## Database Changes

**New fields in `LibraryImportItem`:**
- `MetadataSource` - "NFO", "Auto (IMVDb)", "Filename"
- `NfoMetadataJson` - Stores parsed NFO data
- `CacheMetadataJson` - Stores cache search results
- `FeaturedArtistsJson` - List of featured artist names

## Implementation Timeline

| Phase | Duration | Deliverables |
|-------|----------|-------------|
| 1. NFO Integration | 2 weeks | NFO discovery, parsing, database migration |
| 2. Filename Parsing | 1 week | Enhanced parser with featured artists |
| 3. Cache Integration | 1 week | Query during scan, confidence scoring |
| 4. UI Enhancements | 1 week | Metadata previews, confidence displays |
| 5. Testing & Polish | 1 week | Integration tests, documentation |
| **TOTAL** | **6 weeks** | Fully enhanced import process |

## Risk Mitigation

- ✅ **Backward compatible** - existing imports still work
- ✅ **Graceful degradation** - falls back to filename parsing if NFO missing
- ✅ **Performance tested** - < 20% import time increase
- ✅ **Unit tested** - 95%+ test coverage for new code

## User Impact

### Positive
- 📈 **Better metadata accuracy** from NFO files (always prioritized)
- 🎨 **Richer data** with genres, tags, featured artists, source URLs
- 👁️ **More transparency** with color-coded status indicators and confidence scores
- ⚡ **Faster workflow** with table view, auto-apply for high-confidence matches (≥90%)
- 🎯 **Better UI** - spreadsheet/table layout with pagination, instant visual status
- 🔍 **Smart fallback** - cache queries only when NFO is missing/incomplete

### Neutral
- 🕒 **Slightly slower scans** if metadata cache enabled (configurable, only when needed)
- 📚 **More data to review** (but better organized in table with clear status)

### ⚠️ Breaking Changes

**This release includes breaking changes:**

1. **NFO Format Change**
   - ❌ `<customfield1>`, `<customfield2>`, `<customfield3>` no longer parsed for URLs
   - ✅ Must use `<sources><url>` format instead
   - 📝 Migration guide provided in release notes

2. **UI Complete Redesign**
   - ❌ Expansion panel interface removed
   - ✅ New table/spreadsheet layout with better UX
   - 👁️ Existing import sessions viewable but with new interface

3. **Database Schema**
   - ✅ Automatic migration on first startup
   - ⚠️ No rollback - backup database before upgrading

**Not Affected:**
- ✅ Existing video library remains intact
- ✅ All metadata and files preserved
- ✅ Core import functionality enhanced, not removed

## Configuration Options

Users can control:
- ☑️ Enable/disable NFO parsing
- ☑️ Enable/disable metadata cache queries
- ☑️ Auto-apply confidence threshold (default: 90%)
- ☑️ Compute file hashes (existing)
- ☑️ Refresh MediaInfo metadata (existing)

## NFO Format Support

**Standard Kodi `<musicvideo>` elements:**
- Artist(s), Title, Year, Album, Genres, Tags
- Director, Studio, Label (record label)
- Plot (description), Runtime
- IMVDb ID, MusicBrainz Recording ID

**Non-Kodi Extension (Fuzzbin-specific):**
```xml
<sources>
    <url>https://www.youtube.com/watch?v=...</url>
    <url>https://vimeo.com/...</url>
</sources>
```
These URLs point to video sources, stored in `VideoSourceVerification` for future verification.

**Featured Artist Extraction:**
- From `<artist>` field: "Taylor Swift feat. Ed Sheeran"
- From `<title>` field: "End Game (feat. Ed Sheeran)"
- NFO data always takes precedence

## Next Steps

1. **Review this plan** and provide feedback
2. **Answer decision questions** (see main document)
3. **Approve database schema changes**
4. **Begin Phase 1 implementation**

---

📄 **Full details:** See `video-import-refactoring-plan.md`
