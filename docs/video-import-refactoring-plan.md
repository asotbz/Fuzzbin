# Video Import Process Refactoring Plan

## Overview

This document outlines a comprehensive plan to refactor and enhance the video import process in Fuzzbin to better handle NFO files and improve metadata extraction from filenames.

## Current State Analysis

### Existing Implementation

**Location:** `Fuzzbin.Services/LibraryImportService.cs`

**Current Capabilities:**
- ✅ Recursive directory scanning for video files
- ✅ File hash computation (SHA-256) for duplicate detection
- ✅ Basic filename parsing (Artist - Title pattern with year extraction)
- ✅ Fuzzy matching against existing videos in library
- ✅ MediaInfo metadata extraction (resolution, codecs, duration, etc.)
- ✅ Integration with MetadataCacheService for IMVDb/MusicBrainz lookups
- ✅ Confidence scoring for automatic metadata application
- ⚠️ **Limited NFO support** - NFO reading exists in `MetadataService.ReadNfoAsync()` but is **not used during import**

**Current NFO Support:**
- `MetadataService.ReadNfoAsync()` exists and can parse Kodi `<musicvideo>` XML
- Extracts: title, artist, album, year, plot, director, studio, label, genres, tags, IMVDb ID, MusicBrainz ID
- **Gap:** Not integrated into `LibraryImportService.StartImportAsync()` workflow

### Current Data Flow

```
User Initiates Scan
    ↓
Scan Directory for Video Files (.mp4, .mkv, .mov, .avi, .webm)
    ↓
For Each Video File:
    1. Compute File Hash (if enabled)
    2. Extract MediaInfo Metadata (if enabled)
    3. Parse Filename (Artist - Title - Year)
    4. Check for Duplicates (hash/path/fuzzy match)
    5. Store as LibraryImportItem
    ↓
User Reviews Items in UI
    ↓
User Commits Import
    ↓
For Each Approved Item:
    1. Create or Link to Video Entity
    2. Apply Metadata from Import Item
    3. Optionally Enrich with MetadataCacheService (if confidence >= 0.9)
```

## Enhancement Requirements

### 1. NFO File Discovery and Parsing

**Goal:** Automatically discover and parse NFO files adjacent to video files during import scan.

#### Implementation Details

**NFO File Naming Conventions:**
- Same basename as video: `Artist - Title.mp4` → `Artist - Title.nfo`
- Kodi pattern with `-nfo` suffix: `Artist - Title-nfo.nfo`
- Directory-level: `movie.nfo` (if only one video in directory)

**NFO Schema Validation:**
- Verify root element is `<musicvideo>`
- Log warning if different root element (e.g., `<movie>`, `<tvshow>`)
- Continue with filename parsing if NFO is invalid

**NFO Priority Rule:**
- ✅ **NFO metadata ALWAYS overrides filename parsing** when present
- If NFO is missing required fields, fallback to filename parsing and/or metadata cache

**Metadata Extraction from NFO:**

| NFO Element | Video Entity Field | Notes |
|-------------|-------------------|-------|
| `<title>` | `Title` | Required. May contain feat. pattern |
| `<artist>` (first) | `Artist` | Primary artist. May contain feat. pattern |
| `<artist>` (additional) | `FeaturedArtists` collection | Multi-artist support |
| `<year>` | `Year` | Integer |
| `<album>` | `Album` | Optional |
| `<studio>` or `<label>` | `Publisher` | Record label |
| `<genre>` | `Genres` collection | Multiple allowed |
| `<tag>` | `Tags` collection | Multiple allowed |
| `<plot>` | `Description` | Video description |
| `<director>` | `Director` | Video director |
| `<imvdbid>` | `ImvdbId` | External ID |
| `<musicbrainzrecordingid>` | `MusicBrainzRecordingId` | External ID |
| `<runtime>` or `<durationinseconds>` | `Duration` | Convert to seconds |
| `<sources>` | `VideoSourceVerification` | **Non-Kodi extension** |
| `<sources><url>` | Source URLs | One to many video source URLs |

**Featured Artist Extraction from NFO:**
- Parse `<artist>` field for feat. patterns: "Taylor Swift feat. Ed Sheeran"
- Parse `<title>` field for feat. patterns: "End Game (feat. Ed Sheeran)"
- Trust NFO data over any other source

**Source URL Extraction:**
- Support custom `<sources>` element (non-Kodi extension)
- Parse structure: `<sources><url>https://youtube.com/...</url><url>...</url></sources>`
- Each URL points to a video source (YouTube, Vimeo, etc.), NOT metadata source
- Store in `VideoSourceVerification` entity for future verification
- **No legacy support**: Only `<sources>` element is recognized (customfield1/2/3 ignored)

#### Code Changes Required

**File:** `Fuzzbin.Services/LibraryImportService.cs`

```csharp
// New method to discover NFO files
private async Task<string?> FindNfoFileAsync(string videoFilePath, CancellationToken cancellationToken)
{
    var directory = Path.GetDirectoryName(videoFilePath);
    var fileNameWithoutExt = Path.GetFileNameWithoutExtension(videoFilePath);
    
    // Check same basename
    var nfoPath = Path.Combine(directory, $"{fileNameWithoutExt}.nfo");
    if (File.Exists(nfoPath)) return nfoPath;
    
    // Check Kodi pattern
    nfoPath = Path.Combine(directory, $"{fileNameWithoutExt}-nfo.nfo");
    if (File.Exists(nfoPath)) return nfoPath;
    
    // Check directory-level (if only one video)
    nfoPath = Path.Combine(directory, "movie.nfo");
    var videoCount = Directory.GetFiles(directory, "*.*")
        .Count(f => FallbackExtensions.Contains(Path.GetExtension(f), StringComparer.OrdinalIgnoreCase));
    if (videoCount == 1 && File.Exists(nfoPath)) return nfoPath;
    
    return null;
}

// New method to apply NFO metadata to import item
private async Task<bool> ApplyNfoMetadataAsync(
    LibraryImportItem item, 
    string nfoPath, 
    CancellationToken cancellationToken)
{
    var nfoData = await _metadataService.ReadNfoAsync(nfoPath, cancellationToken);
    if (nfoData == null) return false;
    
    // NFO ALWAYS overrides - no fallback to existing values
    item.Title = nfoData.Title;
    item.Artist = nfoData.Artist;
    item.Album = nfoData.Album;
    item.Year = nfoData.Year;
    item.Notes = AppendNote(item.Notes, $"Metadata sourced from NFO: {Path.GetFileName(nfoPath)}");
    
    // Extract featured artists from artist field and/or title field
    var featuredArtists = new List<string>();
    
    // Check artist field: "Taylor Swift feat. Ed Sheeran"
    if (!string.IsNullOrWhiteSpace(nfoData.Artist))
    {
        var (primaryArtist, artistFeatured) = ExtractFeaturedArtists(nfoData.Artist);
        item.Artist = primaryArtist;
        featuredArtists.AddRange(artistFeatured);
    }
    
    // Check title field: "End Game (feat. Ed Sheeran)"
    if (!string.IsNullOrWhiteSpace(nfoData.Title))
    {
        var (cleanTitle, titleFeatured) = ExtractFeaturedFromTitle(nfoData.Title);
        item.Title = cleanTitle;
        featuredArtists.AddRange(titleFeatured);
    }
    
    // Store unique featured artists
    if (featuredArtists.Any())
    {
        var uniqueFeatured = featuredArtists.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        item.FeaturedArtistsJson = JsonSerializer.Serialize(uniqueFeatured);
    }
    
    // Store additional metadata in JSON for later use
    var nfoMetadata = new
    {
        Genres = nfoData.Genres,
        Tags = nfoData.Tags,
        Director = nfoData.Director,
        Studio = nfoData.Studio,
        RecordLabel = nfoData.RecordLabel,
        Description = nfoData.Plot,
        ImvdbId = nfoData.ImvdbId,
        MusicBrainzId = nfoData.MusicBrainzId,
        SourceUrls = ExtractSourceUrls(nfoData),
        HasCompleteMetadata = IsMetadataComplete(nfoData)
    };
    item.NfoMetadataJson = JsonSerializer.Serialize(nfoMetadata);
    
    return true;
}

// Check if NFO provides complete metadata (for UI indicator)
private bool IsMetadataComplete(NfoData nfoData)
{
    return !string.IsNullOrWhiteSpace(nfoData.Title) &&
           !string.IsNullOrWhiteSpace(nfoData.Artist) &&
           nfoData.Year.HasValue &&
           nfoData.Genres?.Any() == true;
}

// Extract featured artists from title: "End Game (feat. Ed Sheeran)" → ("End Game", ["Ed Sheeran"])
private (string CleanTitle, List<string> FeaturedArtists) ExtractFeaturedFromTitle(string title)
{
    var featured = new List<string>();
    var cleanTitle = title;
    
    // Pattern: (feat. Artist) or [feat. Artist] or (ft. Artist)
    var patterns = new[]
    {
        @"\s*[\(\[](?:feat\.?|ft\.?|featuring)\s+([^\)\]]+)[\)\]]",
    };
    
    foreach (var pattern in patterns)
    {
        var match = Regex.Match(cleanTitle, pattern, RegexOptions.IgnoreCase);
        if (match.Success)
        {
            cleanTitle = cleanTitle.Remove(match.Index, match.Length).Trim();
            var artistsPart = match.Groups[1].Value;
            
            // Split multiple artists
            var separators = new[] { " & ", ", ", " and ", " x " };
            var artists = artistsPart.Split(separators, StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
            featured.AddRange(artists.Where(a => !string.IsNullOrWhiteSpace(a)));
        }
    }
    
    return (cleanTitle, featured);
}

// Extract URLs from <sources> element only
private List<string> ExtractSourceUrls(NfoData nfoData)
{
    var urls = new List<string>();
    
    // Only <sources><url> elements are supported
    if (nfoData.SourceUrls?.Any() == true)
    {
        urls.AddRange(nfoData.SourceUrls);
    }
    
    return urls.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
}
```

**Modify `BuildImportItemAsync` to check for NFO:**

```csharp
// After line ~410 in existing BuildImportItemAsync
var metadata = request.RefreshMetadata ? await TryExtractMetadataAsync(filePath, cancellationToken) : null;

// NEW: Check for NFO file
var nfoPath = await FindNfoFileAsync(filePath, cancellationToken);
if (nfoPath != null)
{
    var nfoApplied = await ApplyNfoMetadataAsync(item, nfoPath, cancellationToken);
    if (nfoApplied)
    {
        item.MetadataSource = "NFO";
    }
}

// Continue with existing logic...
if (metadata != null) { ... }
```

### 2. Enhanced Filename Parsing

**Current Limitation:** Simple pattern matching for `Artist - Title` with year extraction.

**Enhancement Goals:**
- Support more filename patterns
- Extract featured artists from title
- Better year detection
- Handle common prefixes/suffixes

#### Common Patterns to Support

```
Artist - Title (Year).ext
Artist - Title [Year].ext
Artist feat. Artist2 - Title.ext
Year - Artist - Title.ext
Artist_-_Title_-_Year.ext
[Year] Artist - Title.ext
Artist - Title (Official Video).ext
Artist - Title (Official Music Video).ext
Artist - Title [HD].ext
Artist - Title [4K].ext
```

#### Featured Artist Detection

**Patterns:**
- `feat.`, `ft.`, `featuring`
- `with`, `&`, `+`, `x`
- `vs.`, `versus`

**Example:**
```
"Taylor Swift feat. Ed Sheeran - End Game (2017).mp4"
→ Artist: "Taylor Swift"
→ Featured: ["Ed Sheeran"]
→ Title: "End Game"
→ Year: 2017
```

#### Implementation

**File:** `Fuzzbin.Services/LibraryImportService.cs`

```csharp
// Enhanced filename parser
private static (string? Artist, string? Title, int? Year, List<string> FeaturedArtists) 
    InferFromFilenameEnhanced(string fileName)
{
    var nameWithoutExt = Path.GetFileNameWithoutExtension(fileName);
    var normalized = nameWithoutExt
        .Replace('_', ' ')
        .Replace("  ", " ")
        .Trim();
    
    // Remove common suffixes
    var suffixesToRemove = new[]
    {
        "(Official Video)", "(Official Music Video)", 
        "(Official Audio)", "[Official Video]",
        "[HD]", "[4K]", "(HD)", "(4K)",
        "(Explicit)", "[Explicit]"
    };
    foreach (var suffix in suffixesToRemove)
    {
        var idx = normalized.LastIndexOf(suffix, StringComparison.OrdinalIgnoreCase);
        if (idx > 0)
        {
            normalized = normalized.Substring(0, idx).Trim();
        }
    }
    
    // Extract year
    int? year = null;
    var yearMatch = FilenameYearRegex.Match(normalized);
    if (yearMatch.Success && int.TryParse(yearMatch.Value, out var parsedYear))
    {
        year = parsedYear;
        normalized = normalized.Replace(yearMatch.Value, "").Trim();
        
        // Remove surrounding brackets/parens
        normalized = Regex.Replace(normalized, @"\s*[\[\(\{\s]*\s*[\]\)\}\s]*\s*$", "");
    }
    
    // Try different separator patterns
    var separators = new[] { " - ", " – ", " — ", " | " };
    foreach (var separator in separators)
    {
        var parts = normalized.Split(separator, StringSplitOptions.TrimEntries);
        if (parts.Length >= 2)
        {
            var artistPart = parts[0];
            var titlePart = string.Join(" - ", parts.Skip(1));
            
            // Extract featured artists from artist part
            var (primaryArtist, featured) = ExtractFeaturedArtists(artistPart);
            
            return (primaryArtist, titlePart, year, featured);
        }
    }
    
    return (null, normalized, year, new List<string>());
}

// Extract featured artists
private static (string PrimaryArtist, List<string> FeaturedArtists) 
    ExtractFeaturedArtists(string artistString)
{
    var featuredArtists = new List<string>();
    var primary = artistString;
    
    // Patterns for featured artists
    var featuredPatterns = new[]
    {
        @"\s+feat\.?\s+(.+)$",
        @"\s+ft\.?\s+(.+)$",
        @"\s+featuring\s+(.+)$",
        @"\s+with\s+(.+)$",
        @"\s+x\s+(.+)$"
    };
    
    foreach (var pattern in featuredPatterns)
    {
        var match = Regex.Match(artistString, pattern, RegexOptions.IgnoreCase);
        if (match.Success)
        {
            primary = artistString.Substring(0, match.Index).Trim();
            var featuredPart = match.Groups[1].Value;
            
            // Split multiple featured artists
            var separators = new[] { " & ", ", ", " and " };
            var artists = featuredPart.Split(separators, StringSplitOptions.TrimEntries);
            featuredArtists.AddRange(artists.Where(a => !string.IsNullOrWhiteSpace(a)));
            break;
        }
    }
    
    return (primary, featuredArtists);
}
```

### 3. Metadata Cache Integration Strategy

**Current State:** MetadataCache integration happens during commit phase, only if confidence >= 0.9

**Enhancement:** Make cache integration more intelligent and visible during review phase

#### Improved Strategy

1. **During Scan Phase:**
   - If NFO present → Use NFO metadata (highest priority)
   - If NFO missing → Query MetadataCache if Artist + Title available
   - Store cache results in `LibraryImportItem.CacheMetadataJson`
   - Display confidence scores in review UI

2. **Confidence Thresholds:**
   - **>= 0.95:** Auto-apply (mark as "High Confidence Match")
   - **0.80-0.94:** Suggest in UI (mark as "Good Match")
   - **0.60-0.79:** Show as option (mark as "Possible Match")
   - **< 0.60:** Require manual search

3. **Multi-Source Resolution:**
   - NFO metadata takes precedence
   - MetadataCache enriches missing fields
   - User can override in review UI

#### Implementation

**File:** `Fuzzbin.Services/LibraryImportService.cs`

```csharp
// Query metadata cache if NFO is incomplete OR missing
bool shouldQueryCache = false;
bool nfoIsIncomplete = false;

if (!string.IsNullOrWhiteSpace(item.NfoMetadataJson))
{
    var nfoMeta = JsonSerializer.Deserialize<NfoMetadataDto>(item.NfoMetadataJson);
    nfoIsIncomplete = nfoMeta?.HasCompleteMetadata == false;
    shouldQueryCache = nfoIsIncomplete;
}
else
{
    // No NFO at all - always query cache if we have artist + title
    shouldQueryCache = !string.IsNullOrWhiteSpace(item.Artist) && !string.IsNullOrWhiteSpace(item.Title);
}

if (shouldQueryCache)
{
    try
    {
        var cacheResult = await _metadataCacheService.SearchAsync(
            item.Artist,
            item.Title,
            item.DurationSeconds.HasValue ? (int)item.DurationSeconds.Value : null,
            cancellationToken);
        
        if (cacheResult.Found && cacheResult.BestMatch != null)
        {
            item.CacheMetadataJson = JsonSerializer.Serialize(new
            {
                Source = cacheResult.BestMatch.PrimarySource,
                Confidence = cacheResult.BestMatch.OverallConfidence,
                ImvdbId = cacheResult.BestMatch.ImvdbVideoId,
                MusicBrainzId = cacheResult.BestMatch.MusicBrainzRecordingId,
                Album = cacheResult.BestMatch.Album,
                Year = cacheResult.BestMatch.Year,
                Genres = cacheResult.BestMatch.Genres,
                FeaturedArtists = cacheResult.BestMatch.FeaturedArtists,
                RequiresManualSelection = cacheResult.RequiresManualSelection,
                AllCandidates = cacheResult.RequiresManualSelection 
                    ? cacheResult.AllCandidates?.Take(5).ToList() 
                    : null
            });
            
            if (cacheResult.BestMatch.OverallConfidence >= 0.90)
            {
                // Auto-apply threshold met
                if (string.IsNullOrWhiteSpace(item.MetadataSource))
                {
                    item.MetadataSource = $"Auto ({cacheResult.BestMatch.PrimarySource})";
                }
                item.Notes = AppendNote(item.Notes, 
                    $"High confidence match from {cacheResult.BestMatch.PrimarySource} ({cacheResult.BestMatch.OverallConfidence:P0})");
            }
            else if (cacheResult.RequiresManualSelection)
            {
                // Multiple candidates - needs review
                item.Notes = AppendNote(item.Notes, 
                    $"Multiple matches found - manual selection required");
            }
            else
            {
                // Lower confidence - show as option
                item.Notes = AppendNote(item.Notes, 
                    $"Possible match from {cacheResult.BestMatch.PrimarySource} ({cacheResult.BestMatch.OverallConfidence:P0})");
            }
            
            if (nfoIsIncomplete)
            {
                item.Notes = AppendNote(item.Notes, "NFO incomplete - cache enrichment available");
            }
        }
    }
    catch (Exception ex)
    {
        _logger.LogWarning(ex, "Failed to query metadata cache for {Artist} - {Title}", 
            item.Artist, item.Title);
    }
}
```

### 4. Database Schema Changes

**New Fields for `LibraryImportItem`:**

| Field | Type | Purpose |
|-------|------|---------|
| `MetadataSource` | `string?` | "NFO", "Auto (IMVDb)", "Filename", etc. |
| `NfoMetadataJson` | `string?` | JSON storage for NFO-extracted metadata |
| `CacheMetadataJson` | `string?` | JSON storage for cache search results |
| `FeaturedArtistsJson` | `string?` | JSON array of featured artist names |

**Migration Required:**

```csharp
// Fuzzbin.Data/Migrations/AddImportMetadataFields.cs
public partial class AddImportMetadataFields : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>(
            name: "MetadataSource",
            table: "LibraryImportItems",
            type: "TEXT",
            maxLength: 100,
            nullable: true);

        migrationBuilder.AddColumn<string>(
            name: "NfoMetadataJson",
            table: "LibraryImportItems",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<string>(
            name: "CacheMetadataJson",
            table: "LibraryImportItems",
            type: "TEXT",
            nullable: true);

        migrationBuilder.AddColumn<string>(
            name: "FeaturedArtistsJson",
            table: "LibraryImportItems",
            type: "TEXT",
            nullable: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(name: "MetadataSource", table: "LibraryImportItems");
        migrationBuilder.DropColumn(name: "NfoMetadataJson", table: "LibraryImportItems");
        migrationBuilder.DropColumn(name: "CacheMetadataJson", table: "LibraryImportItems");
        migrationBuilder.DropColumn(name: "FeaturedArtistsJson", table: "LibraryImportItems");
    }
}
```

### 5. Commit Phase Enhancements

**Goal:** Apply enriched metadata from NFO and cache during commit

**Implementation:**

```csharp
// Modify ApplyImportMetadata in LibraryImportService.cs
private async Task ApplyImportMetadataEnhanced(
    Video video, 
    LibraryImportSession session, 
    LibraryImportItem item,
    CancellationToken cancellationToken)
{
    // Apply base metadata (existing logic)
    ApplyImportMetadata(video, session, item);
    
    // Apply NFO metadata if available
    if (!string.IsNullOrWhiteSpace(item.NfoMetadataJson))
    {
        var nfoMetadata = JsonSerializer.Deserialize<NfoMetadataDto>(item.NfoMetadataJson);
        if (nfoMetadata != null)
        {
            await ApplyNfoMetadataToVideo(video, nfoMetadata, cancellationToken);
        }
    }
    
    // Apply cache metadata if available and confidence is high
    if (!string.IsNullOrWhiteSpace(item.CacheMetadataJson))
    {
        var cacheMetadata = JsonSerializer.Deserialize<CacheMetadataDto>(item.CacheMetadataJson);
        if (cacheMetadata != null && cacheMetadata.Confidence >= 0.90)
        {
            await ApplyCacheMetadataToVideo(video, cacheMetadata, cancellationToken);
        }
    }
    
    // Apply featured artists
    if (!string.IsNullOrWhiteSpace(item.FeaturedArtistsJson))
    {
        var featuredNames = JsonSerializer.Deserialize<List<string>>(item.FeaturedArtistsJson);
        if (featuredNames?.Any() == true)
        {
            await ApplyFeaturedArtists(video, featuredNames, cancellationToken);
        }
    }
}

private async Task ApplyNfoMetadataToVideo(
    Video video, 
    NfoMetadataDto nfoMetadata, 
    CancellationToken cancellationToken)
{
    // Apply genres
    if (nfoMetadata.Genres?.Any() == true)
    {
        foreach (var genreName in nfoMetadata.Genres)
        {
            var genre = await _unitOfWork.Genres.FirstOrDefaultAsync(
                new GenreByNameSpecification(genreName));
            if (genre == null)
            {
                genre = new Genre { Name = genreName };
                await _unitOfWork.Genres.AddAsync(genre);
            }
            if (!video.Genres.Contains(genre))
            {
                video.Genres.Add(genre);
            }
        }
    }
    
    // Apply tags (similar to genres)
    if (nfoMetadata.Tags?.Any() == true)
    {
        foreach (var tagName in nfoMetadata.Tags)
        {
            var tag = await _unitOfWork.Tags.FirstOrDefaultAsync(
                new TagByNameSpecification(tagName));
            if (tag == null)
            {
                tag = new Tag { Name = tagName };
                await _unitOfWork.Tags.AddAsync(tag);
            }
            if (!video.Tags.Contains(tag))
            {
                video.Tags.Add(tag);
            }
        }
    }
    
    // Apply other fields (only if not already set)
    video.Director ??= nfoMetadata.Director;
    video.ProductionCompany ??= nfoMetadata.Studio;
    video.Publisher ??= nfoMetadata.RecordLabel;
    video.Description ??= nfoMetadata.Description;
    video.ImvdbId ??= nfoMetadata.ImvdbId;
    video.MusicBrainzRecordingId ??= nfoMetadata.MusicBrainzId;
    
    // Store source URLs for verification
    if (nfoMetadata.SourceUrls?.Any() == true)
    {
        foreach (var url in nfoMetadata.SourceUrls)
        {
            var verification = new VideoSourceVerification
            {
                VideoId = video.Id,
                SourceUrl = url,
                Status = VerificationStatus.NotVerified,
                Notes = "Imported from NFO file"
            };
            await _unitOfWork.VideoSourceVerifications.AddAsync(verification);
        }
    }
}

private async Task ApplyFeaturedArtists(
    Video video, 
    List<string> featuredNames, 
    CancellationToken cancellationToken)
{
    foreach (var name in featuredNames)
    {
        var artist = await _unitOfWork.FeaturedArtists.FirstOrDefaultAsync(
            new FeaturedArtistByNameSpecification(name));
        if (artist == null)
        {
            artist = new FeaturedArtist { Name = name };
            await _unitOfWork.FeaturedArtists.AddAsync(artist);
        }
        if (!video.FeaturedArtists.Contains(artist))
        {
            video.FeaturedArtists.Add(artist);
        }
    }
}
```

### 6. UI Enhancements - Table/Spreadsheet View

**Import Review Page (`Import.razor`):** Complete redesign to table format

#### New Table-Based Layout

**Replace expansion panel UI with:**

```razor
<MudTable Items="@_importItems" 
          Dense="true" 
          Hover="true" 
          FixedHeader="true"
          Height="calc(100vh - 300px)"
          @bind-SelectedItem="_selectedItem"
          RowsPerPage="50">
    <HeaderContent>
        <MudTh>Status</MudTh>
        <MudTh>Artist</MudTh>
        <MudTh>Title</MudTh>
        <MudTh>Year</MudTh>
        <MudTh>Album</MudTh>
        <MudTh>Source</MudTh>
        <MudTh>Actions</MudTh>
    </HeaderContent>
    <RowTemplate>
        <MudTd DataLabel="Status">
            @GetStatusIcon(context)
        </MudTd>
        <MudTd DataLabel="Artist">
            <MudText Typo="Typo.body2">@context.Artist</MudText>
            @if (!string.IsNullOrEmpty(context.FeaturedArtistsJson))
            {
                var featured = ParseFeaturedArtists(context.FeaturedArtistsJson);
                <MudText Typo="Typo.caption" Color="Color.Secondary">
                    feat. @string.Join(", ", featured)
                </MudText>
            }
        </MudTd>
        <MudTd DataLabel="Title">@context.Title</MudTd>
        <MudTd DataLabel="Year">@context.Year</MudTd>
        <MudTd DataLabel="Album">@context.Album</MudTd>
        <MudTd DataLabel="Source">
            @if (!string.IsNullOrEmpty(context.MetadataSource))
            {
                <MudChip Size="Size.Small" Color="GetMetadataSourceColor(context.MetadataSource)">
                    @context.MetadataSource
                </MudChip>
            }
        </MudTd>
        <MudTd DataLabel="Actions">
            @if (RequiresReview(context))
            {
                <MudIconButton Icon="@Icons.Material.Filled.Search" 
                               Size="Size.Small"
                               Color="Color.Warning"
                               OnClick="@(() => OpenCandidateSelector(context))"
                               Title="Select metadata candidate" />
            }
            <MudIconButton Icon="@Icons.Material.Filled.Delete" 
                           Size="Size.Small"
                           Color="Color.Error"
                           OnClick="@(() => RemoveFromImport(context))"
                           Title="Remove from import" />
        </MudTd>
    </RowTemplate>
    <PagerContent>
        <MudTablePager PageSizeOptions="new int[] { 25, 50, 100 }" />
    </PagerContent>
</MudTable>
```

#### Status Icon Logic

```csharp
private RenderFragment GetStatusIcon(LibraryImportItem item)
{
    var (color, icon, tooltip) = GetStatusIndicator(item);
    return @<MudTooltip Text="@tooltip">
        <MudIcon Icon="@icon" Color="@color" Size="Size.Small" />
    </MudTooltip>;
}

private (Color Color, string Icon, string Tooltip) GetStatusIndicator(LibraryImportItem item)
{
    // Complete metadata (green check)
    if (!string.IsNullOrEmpty(item.NfoMetadataJson))
    {
        var nfoMeta = JsonSerializer.Deserialize<NfoMetadataDto>(item.NfoMetadataJson);
        if (nfoMeta?.HasCompleteMetadata == true)
        {
            return (Color.Success, Icons.Material.Filled.CheckCircle, "Complete metadata from NFO");
        }
    }
    
    // High confidence auto-match (blue check)
    if (!string.IsNullOrEmpty(item.CacheMetadataJson))
    {
        var cache = JsonSerializer.Deserialize<CacheMetadataDto>(item.CacheMetadataJson);
        if (cache?.Confidence >= 0.90)
        {
            return (Color.Info, Icons.Material.Filled.CheckCircle, $"Auto-matched ({cache.Confidence:P0})");
        }
    }
    
    // Needs review (yellow warning)
    if (!string.IsNullOrEmpty(item.CacheMetadataJson))
    {
        var cache = JsonSerializer.Deserialize<CacheMetadataDto>(item.CacheMetadataJson);
        if (cache?.RequiresManualSelection == true)
        {
            return (Color.Warning, Icons.Material.Filled.Warning, "Multiple matches - select one");
        }
    }
    
    // Incomplete/needs attention (orange alert)
    if (string.IsNullOrWhiteSpace(item.Artist) || string.IsNullOrWhiteSpace(item.Title))
    {
        return (Color.Error, Icons.Material.Filled.Error, "Missing required fields");
    }
    
    // Partial metadata (gray info)
    return (Color.Default, Icons.Material.Filled.Info, "Partial metadata - may need enrichment");
}

private bool RequiresReview(LibraryImportItem item)
{
    if (!string.IsNullOrEmpty(item.CacheMetadataJson))
    {
        var cache = JsonSerializer.Deserialize<CacheMetadataDto>(item.CacheMetadataJson);
        return cache?.RequiresManualSelection == true || cache?.Confidence < 0.90;
    }
    return false;
}
```

#### Candidate Selection Dialog

```razor
<MudDialog @bind-IsVisible="_candidateSelectorOpen">
    <TitleContent>
        <MudText Typo="Typo.h6">Select Metadata Match</MudText>
    </TitleContent>
    <DialogContent>
        <MudText Typo="Typo.body2" Class="mb-4">
            Searching for: <strong>@_selectedItem?.Artist - @_selectedItem?.Title</strong>
        </MudText>
        
        @if (_candidates?.Any() == true)
        {
            <MudList Clickable="true" Dense="true">
                @foreach (var candidate in _candidates)
                {
                    <MudListItem OnClick="@(() => SelectCandidate(candidate))">
                        <MudStack Row="true" Justify="Justify.SpaceBetween" AlignItems="AlignItems.Center">
                            <div>
                                <MudText Typo="Typo.body1">@candidate.Artist - @candidate.Title</MudText>
                                <MudText Typo="Typo.caption" Color="Color.Secondary">
                                    @candidate.Year · @candidate.Album · @candidate.Source
                                </MudText>
                            </div>
                            <MudProgressCircular Size="Size.Small" 
                                                Value="@(candidate.Confidence * 100)" 
                                                Color="@GetConfidenceColor(candidate.Confidence)">
                                <MudText Typo="Typo.caption">@candidate.Confidence.ToString("P0")</MudText>
                            </MudProgressCircular>
                        </MudStack>
                    </MudListItem>
                    <MudDivider />
                }
            </MudList>
        }
        else
        {
            <MudAlert Severity="Severity.Info">No matches found. Video will import with filename metadata.</MudAlert>
        }
    </DialogContent>
    <DialogActions>
        <MudButton OnClick="@(() => _candidateSelectorOpen = false)">Cancel</MudButton>
        <MudButton Color="Color.Primary" OnClick="@(() => SearchManually())">Manual Search</MudButton>
    </DialogActions>
</MudDialog>
```

#### Real-time Updates as Metadata Loads

```csharp
// Stream updates via SignalR as scan progresses
protected override async Task OnInitializedAsync()
{
    await _hubConnection.On<LibraryImportItem>("ImportItemScanned", item =>
    {
        InvokeAsync(() =>
        {
            _importItems.Add(item);
            StateHasChanged();
        });
    });
}
```

#### Summary Statistics Panel

```razor
<MudPaper Class="pa-3 mb-3">
    <MudGrid>
        <MudItem xs="3">
            <MudStack Spacing="1">
                <MudIcon Icon="@Icons.Material.Filled.CheckCircle" Color="Color.Success" />
                <MudText Typo="Typo.h6">@_stats.CompleteCount</MudText>
                <MudText Typo="Typo.caption">Complete</MudText>
            </MudStack>
        </MudItem>
        <MudItem xs="3">
            <MudStack Spacing="1">
                <MudIcon Icon="@Icons.Material.Filled.Warning" Color="Color.Warning" />
                <MudText Typo="Typo.h6">@_stats.NeedsReviewCount</MudText>
                <MudText Typo="Typo.caption">Needs Review</MudText>
            </MudStack>
        </MudItem>
        <MudItem xs="3">
            <MudStack Spacing="1">
                <MudIcon Icon="@Icons.Material.Filled.Info" Color="Color.Info" />
                <MudText Typo="Typo.h6">@_stats.PartialCount</MudText>
                <MudText Typo="Typo.caption">Partial</MudText>
            </MudStack>
        </MudItem>
        <MudItem xs="3">
            <MudStack Spacing="1">
                <MudIcon Icon="@Icons.Material.Filled.VideoLibrary" />
                <MudText Typo="Typo.h6">@_importItems.Count</MudText>
                <MudText Typo="Typo.caption">Total</MudText>
            </MudStack>
        </MudItem>
    </MudGrid>
</MudPaper>
```

## Implementation Phases

### Phase 1: NFO Integration (Week 1-2)
- [ ] **BREAKING**: Remove customfield1/2/3 URL parsing
- [ ] Add NFO discovery logic to `LibraryImportService`
- [ ] Integrate `ReadNfoAsync` into scan workflow
- [ ] Add database migration for new fields
- [ ] Update `LibraryImportItem` entity
- [ ] Test NFO parsing with various formats
- [ ] Update commit phase to apply NFO metadata
- [ ] Create NFO migration documentation

### Phase 2: Enhanced Filename Parsing (Week 2-3)
- [ ] Implement enhanced filename parser
- [ ] Add featured artist extraction
- [ ] Support multiple filename patterns
- [ ] Add comprehensive unit tests
- [ ] Update existing filename parser calls

### Phase 3: Metadata Cache Integration (Week 3-4)
- [ ] Add cache queries during scan phase
- [ ] Store cache results in import items
- [ ] Implement confidence-based auto-apply logic
- [ ] Add cache metadata to commit phase
- [ ] Test with various confidence scenarios

### Phase 4: UI Enhancements (Week 4-5)
- [ ] **BREAKING**: Remove expansion panel UI
- [ ] Implement new table/spreadsheet layout
- [ ] Add status icon indicators (color-coded)
- [ ] Create candidate selector dialog
- [ ] Add delete buttons for import items
- [ ] Add real-time updates via SignalR
- [ ] Add summary statistics panel
- [ ] Test pagination and performance

### Phase 5: Testing & Polish (Week 5-6)
- [ ] Integration tests for full import workflow
- [ ] Test with real-world NFO files
- [ ] Test with various filename patterns
- [ ] Performance testing with large libraries
- [ ] User acceptance testing
- [ ] Documentation updates

## Testing Strategy

### Unit Tests

```csharp
// Fuzzbin.Tests/Services/LibraryImportServiceTests.cs

[Fact]
public async Task FindNfoFile_ShouldDiscoverSameBasename()
{
    // Arrange
    var videoPath = "/library/Artist - Title.mp4";
    // Create temp NFO file
    
    // Act
    var nfoPath = await _service.FindNfoFileAsync(videoPath, CancellationToken.None);
    
    // Assert
    Assert.NotNull(nfoPath);
    Assert.EndsWith("Artist - Title.nfo", nfoPath);
}

[Fact]
public void InferFromFilenameEnhanced_ShouldExtractFeaturedArtists()
{
    // Arrange
    var filename = "Taylor Swift feat. Ed Sheeran - End Game (2017).mp4";
    
    // Act
    var (artist, title, year, featured) = InferFromFilenameEnhanced(filename);
    
    // Assert
    Assert.Equal("Taylor Swift", artist);
    Assert.Equal("End Game", title);
    Assert.Equal(2017, year);
    Assert.Contains("Ed Sheeran", featured);
}

[Fact]
public async Task ApplyNfoMetadata_ShouldParseAndApply()
{
    // Arrange
    var item = new LibraryImportItem();
    var nfoPath = CreateTestNfoFile();
    
    // Act
    var applied = await _service.ApplyNfoMetadataAsync(item, nfoPath, CancellationToken.None);
    
    // Assert
    Assert.True(applied);
    Assert.Equal("Test Artist", item.Artist);
    Assert.Equal("Test Title", item.Title);
    Assert.NotNull(item.NfoMetadataJson);
}
```

### Integration Tests

```csharp
// Fuzzbin.Tests/Integration/LibraryImportIntegrationTests.cs

[Fact]
public async Task ImportWithNfo_ShouldApplyAllMetadata()
{
    // Arrange: Create test directory with video + NFO
    var testDir = CreateTestLibrary();
    
    // Act: Start import scan
    var session = await _importService.StartImportAsync(new LibraryImportRequest
    {
        RootPath = testDir,
        RefreshMetadata = true
    });
    
    // Assert: NFO metadata was discovered
    var items = await _importService.GetItemsAsync(session.Id);
    var item = items.First();
    Assert.Equal("NFO", item.MetadataSource);
    Assert.NotNull(item.NfoMetadataJson);
}

[Fact]
public async Task CommitWithNfo_ShouldCreateVideoWithGenresAndTags()
{
    // Arrange: Import session with NFO-sourced item
    var session = await SetupImportSessionWithNfo();
    
    // Act: Commit import
    await _importService.CommitAsync(session.Id);
    
    // Assert: Video has genres and tags from NFO
    var videos = await _videoRepository.GetAllAsync();
    var video = videos.First();
    Assert.NotEmpty(video.Genres);
    Assert.NotEmpty(video.Tags);
    Assert.NotEmpty(video.FeaturedArtists);
}
```

### Test NFO Files

Create test fixtures in `Fuzzbin.Tests/Fixtures/Nfo/`:

```xml
<!-- basic-musicvideo.nfo -->
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<musicvideo>
    <title>End Game (feat. Ed Sheeran)</title>
    <artist>Taylor Swift feat. Future</artist>
    <album>Reputation</album>
    <year>2017</year>
    <genre>Pop</genre>
    <genre>Electronic</genre>
    <tag>upbeat</tag>
    <tag>dance</tag>
    <studio>Big Machine Records</studio>
    <label>Republic Records</label>
    <director>Joseph Kahn</director>
    <plot>Official music video for End Game featuring Ed Sheeran and Future.</plot>
    <imvdbid>12345</imvdbid>
    <musicbrainzrecordingid>abc-123-def</musicbrainzrecordingid>
    <runtime>240</runtime>
    <!-- Non-Kodi extension: source URLs for video sources -->
    <sources>
        <url>https://www.youtube.com/watch?v=dfnCAmr569k</url>
        <url>https://vimeo.com/123456789</url>
    </sources>
</musicvideo>
```

**Expected Parsing Result:**
- Primary Artist: "Taylor Swift"
- Featured Artists: ["Future", "Ed Sheeran"] (from artist field + title field)
- Clean Title: "End Game"
- Source URLs: 2 URLs stored for verification

## Performance Considerations

### Caching Strategy
- Cache parsed NFO files in memory during scan (if rescanning same directory)
- Batch metadata cache queries (max 10 concurrent)
- Use CancellationToken for long-running operations

### Database Optimization
- Bulk insert import items (already implemented)
- Index on `LibraryImportItem.MetadataSource`
- Index on `LibraryImportItem.SessionId` (already exists)

### UI Responsiveness
- Use SignalR for real-time scan progress
- Paginate import item list (already implemented)
- Lazy-load metadata previews

## Breaking Changes

### ⚠️ This is a Breaking Change Release

**Impact:**
1. **NFO CustomFields Removed**: `customfield1`, `customfield2`, `customfield3` are no longer parsed
   - **Migration Required**: Update existing NFO files to use `<sources><url>` format
   - Old NFO files with URLs in custom fields will not import source URLs

2. **Import UI Completely Redesigned**: Expansion panel UI removed
   - New table/spreadsheet view with different interaction patterns
   - Existing import sessions will open but may display differently

3. **Database Schema Changes**: New fields added to `LibraryImportItem`
   - Migration will be applied automatically on first startup
   - Existing import sessions remain in database but won't have new metadata

**Migration Path for Existing NFO Files:**

If you have existing NFO files using customfields for URLs, you must update them:

```bash
# Find NFO files with customfields containing URLs
grep -r "customfield.*http" /path/to/library/*.nfo

# Manual update required for each file:
# 1. Remove: <customfield1>https://...</customfield1>
# 2. Add: <sources><url>https://...</url></sources>
```

**Automated Migration Script (Python example):**
```python
import os
import xml.etree.ElementTree as ET
import re

def migrate_nfo_file(nfo_path):
    tree = ET.parse(nfo_path)
    root = tree.getroot()
    
    urls = []
    # Extract URLs from customfields
    for i in range(1, 4):
        field = root.find(f'customfield{i}')
        if field is not None and field.text:
            if re.match(r'https?://', field.text):
                urls.append(field.text)
                root.remove(field)  # Remove old field
    
    # Add sources element if URLs found
    if urls:
        sources = ET.Element('sources')
        for url in urls:
            url_elem = ET.SubElement(sources, 'url')
            url_elem.text = url
        root.append(sources)
        
        tree.write(nfo_path, encoding='UTF-8', xml_declaration=True)
        print(f"Migrated: {nfo_path}")

# Run migration
for root, dirs, files in os.walk('/path/to/library'):
    for file in files:
        if file.endswith('.nfo'):
            migrate_nfo_file(os.path.join(root, file))
```

**No Rollback**: Once migrated, database cannot be downgraded to previous version.

## Documentation Updates

1. **BREAKING CHANGES Document:**
   - Create `BREAKING_CHANGES.md` with migration guide
   - Document customfield → sources migration
   - Document UI changes from expansion panels to table
   - Include release notes with upgrade instructions

2. **User Guide:**
   - How to prepare NFO files for import
   - Supported NFO schema elements (sources element)
   - Filename conventions best practices
   - Migration from old NFO format

3. **API Documentation:**
   - Update `ILibraryImportService` interface docs
   - Document new `NfoMetadataDto` and `CacheMetadataDto` classes
   - Remove `CustomFields` dictionary from `NfoData` class

4. **Developer Guide:**
   - NFO parsing internals
   - Adding new metadata sources
   - Extending filename patterns

## Success Metrics

- [ ] 95%+ NFO files correctly parsed
- [ ] Featured artists extracted in 80%+ of applicable filenames
- [ ] Metadata confidence scores visible in UI
- [ ] Import time increase < 20% with NFO parsing enabled
- [ ] User satisfaction with metadata accuracy

## Future Enhancements (Post-MVP)

1. **NFO Generation during Import:**
   - Option to create NFO files for videos without them
   - Use metadata cache results

2. **Batch NFO Export:**
   - Export NFO files for entire library
   - Update existing NFO files with new metadata

3. **Advanced Duplicate Detection:**
   - Audio fingerprinting (AcoustID)
   - Video fingerprinting

4. **Machine Learning:**
   - Train model on user corrections
   - Improve confidence scoring

5. **Multi-Language Support:**
   - Parse NFO files in different languages
   - Support i18n metadata fields

---

## Design Decisions (Confirmed)

1. ✅ **NFO Priority:** NFO metadata ALWAYS overrides filename parsing when present
   
2. ✅ **Featured Artists:** Trust NFO data. Support feat. patterns in both `<artist>` and `<title>` fields
   - `<artist>Taylor Swift feat. Ed Sheeran</artist>` → Primary: "Taylor Swift", Featured: ["Ed Sheeran"]
   - `<title>End Game (feat. Ed Sheeran)</title>` → Clean title: "End Game", Featured: ["Ed Sheeran"]

3. ✅ **Confidence Threshold:** 90% (0.90) is the auto-apply threshold

4. ✅ **Source URLs:** 
   - Support custom `<sources><url>` element (non-Kodi extension)
   - URLs point to video sources (YouTube, etc.), NOT metadata sources
   - Store in `VideoSourceVerification` for future verification (not auto-verify during import)
   - **BREAKING**: No support for customfield1/2/3 - must use `<sources>` format

5. ✅ **UI Mode:** Table/spreadsheet layout with:
   - Color/icon indicators for "complete" vs "needs review"
   - Pagination as metadata loads
   - Button to pop open candidate selector for "needs review" items
   - Delete button to remove videos from import

6. ✅ **Cache Query Strategy:** Query cache if:
   - No NFO file present, OR
   - NFO file is incomplete (missing required fields like artist, title, year, or genres)
