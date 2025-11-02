# Metadata Cache Integration Strategy for Fuzzbin

## Executive Summary

This document outlines the strategy for integrating a comprehensive metadata caching system into Fuzzbin that will replace and enhance existing metadata search, manipulation, and retrieval functionality across MusicBrainz, IMVDb, and YouTube (via yt-dlp).

**Key Objectives:**
- Implement persistent database-backed caching with configurable TTL (default 336h, max 720h, min 0)
- Unify metadata retrieval with intelligent candidate ranking and scoring
- Present aggregated results when multiple candidates exist
- Implement robust retry logic (3 attempts with 2s/4s delays)
- Avoid caching incomplete or failed results
- Prioritize IMVDb data when conflicts occur

---

## 1. Current State Analysis

### 1.1 Existing Infrastructure

**Database:**
- Entity Framework Core with SQLite
- [`ApplicationDbContext`](Fuzzbin.Data/Context/ApplicationDbContext.cs) manages all entities
- Current relevant entities: [`Video`](Fuzzbin.Core/Entities/Video.cs), [`Configuration`](Fuzzbin.Core/Entities/Configuration.cs)

**Metadata Services:**
- [`MetadataService`](Fuzzbin.Services/MetadataService.cs): Current implementation with basic IMVDb/MusicBrainz calls
- [`ExternalSearchService`](Fuzzbin.Services/ExternalSearchService.cs): Handles search across IMVDb and yt-dlp
- Uses `IMemoryCache` for temporary caching (5-minute TTL for metadata settings)
- Direct HTTP calls to MusicBrainz (lines 434-519) without retry logic
- IMVDb integration via Refit with [`IImvdbApi`](Fuzzbin.Services/External/Imvdb/IImvdbApi.cs)

**Configuration:**
- [`Configuration`](Fuzzbin.Core/Entities/Configuration.cs) entity stores key-value pairs by category
- [`MetadataSettingsProvider`](Fuzzbin.Services/MetadataSettingsProvider.cs) provides cached settings access
- IMVDb configuration uses `ImvdbOptions` with cache duration support

**Normalization:**
- [`ImvdbMapper`](Fuzzbin.Services/External/Imvdb/ImvdbMapper.cs) provides basic normalization (`NormalizeKey`, `NormalizeSimple`)
- FuzzySharp library used for token-set matching (Fuzz.TokenSetRatio)

### 1.2 Gaps & Limitations

1. **No persistent caching** - Memory cache only, lost on restart
2. **No unified query resolution** - Each service queries independently
3. **No retry logic** - Single HTTP attempts, fails on transient errors
4. **Incomplete scoring** - Basic FuzzySharp matching without duration/year/channel signals
5. **No candidate ranking** - Returns single "best match" or multiple unranked results
6. **No aggregate presentation** - Results shown per-provider, not merged
7. **MusicBrainz not properly integrated** - Basic implementation without caching or enrichment
8. **Rate limiting not enforced** - Comments mention 1 req/sec but no enforcement

---

## 2. Database Schema Integration

### 2.1 New Entity Framework Entities

All entities will extend [`BaseEntity`](Fuzzbin.Core/Entities/BaseEntity.cs) which provides `Id`, `CreatedAt`, `UpdatedAt`, and `IsActive`.

#### Core Query & Cache Tracking

**[`Query`](Fuzzbin.Core/Entities/Query.cs)** (NEW)
```csharp
public class Query : BaseEntity
{
    public string RawTitle { get; set; } = string.Empty;
    public string RawArtist { get; set; } = string.Empty;
    public string NormTitle { get; set; } = string.Empty;
    public string NormArtist { get; set; } = string.Empty;
    public string NormComboKey { get; set; } = string.Empty; // Unique index
    
    // Navigation
    public virtual ICollection<QuerySourceCache> SourceCaches { get; set; } = new List<QuerySourceCache>();
    public virtual QueryResolution? Resolution { get; set; }
}
```

**[`QuerySourceCache`](Fuzzbin.Core/Entities/QuerySourceCache.cs)** (NEW)
```csharp
public class QuerySourceCache : BaseEntity
{
    public Guid QueryId { get; set; }
    public string Source { get; set; } = string.Empty; // 'musicbrainz', 'imvdb', 'youtube'
    public DateTime LastCheckedAt { get; set; }
    public string? ResultEtag { get; set; }
    public int? HttpStatus { get; set; }
    public string? Notes { get; set; }
    
    // Navigation
    public virtual Query Query { get; set; } = null!;
}
```

#### MusicBrainz Entities

**[`MbArtist`](Fuzzbin.Core/Entities/MbArtist.cs)** (NEW)
```csharp
public class MbArtist : BaseEntity
{
    public string Mbid { get; set; } = string.Empty; // Unique
    public string Name { get; set; } = string.Empty;
    public string? SortName { get; set; }
    public string? Disambiguation { get; set; }
    public string? Country { get; set; }
    public DateTime LastSeenAt { get; set; }
    
    // Navigation
    public virtual ICollection<MbRecordingArtist> RecordingArtists { get; set; } = new List<MbRecordingArtist>();
}
```

**[`MbRecording`](Fuzzbin.Core/Entities/MbRecording.cs)** (NEW)
```csharp
public class MbRecording : BaseEntity
{
    public string Mbid { get; set; } = string.Empty; // Unique
    public string Title { get; set; } = string.Empty;
    public int? LengthMs { get; set; }
    public DateTime LastSeenAt { get; set; }
    
    // Navigation
    public virtual ICollection<MbRecordingArtist> Artists { get; set; } = new List<MbRecordingArtist>();
    public virtual ICollection<MbRecordingRelease> Releases { get; set; } = new List<MbRecordingRelease>();
    public virtual ICollection<MbTag> Tags { get; set; } = new List<MbTag>();
    public virtual ICollection<MbRecordingCandidate> Candidates { get; set; } = new List<MbRecordingCandidate>();
}
```

**[`MbReleaseGroup`](Fuzzbin.Core/Entities/MbReleaseGroup.cs)** (NEW)
```csharp
public class MbReleaseGroup : BaseEntity
{
    public string Mbid { get; set; } = string.Empty; // Unique
    public string Title { get; set; } = string.Empty;
    public string? PrimaryType { get; set; }
    public string? FirstReleaseDate { get; set; }
    public DateTime LastSeenAt { get; set; }
    
    // Navigation
    public virtual ICollection<MbReleaseToGroup> Releases { get; set; } = new List<MbReleaseToGroup>();
    public virtual ICollection<MbTag> Tags { get; set; } = new List<MbTag>();
}
```

**[`MbRelease`](Fuzzbin.Core/Entities/MbRelease.cs)** (NEW)
```csharp
public class MbRelease : BaseEntity
{
    public string Mbid { get; set; } = string.Empty; // Unique
    public string Title { get; set; } = string.Empty;
    public string? Date { get; set; }
    public string? Country { get; set; }
    public string? Barcode { get; set; }
    public string? RecordLabel { get; set; }
    public DateTime LastSeenAt { get; set; }
    
    // Navigation
    public virtual ICollection<MbRecordingRelease> Recordings { get; set; } = new List<MbRecordingRelease>();
    public virtual ICollection<MbReleaseToGroup> ReleaseGroups { get; set; } = new List<MbReleaseToGroup>();
}
```

**Join Tables:**
```csharp
public class MbRecordingArtist
{
    public Guid RecordingId { get; set; }
    public Guid ArtistId { get; set; }
    public int ArtistOrder { get; set; }
    public bool IsJoinPhraseFeat { get; set; }
    
    public virtual MbRecording Recording { get; set; } = null!;
    public virtual MbArtist Artist { get; set; } = null!;
}

public class MbRecordingRelease
{
    public Guid RecordingId { get; set; }
    public Guid ReleaseId { get; set; }
    public int? TrackNumber { get; set; }
    public int? DiscNumber { get; set; }
    
    public virtual MbRecording Recording { get; set; } = null!;
    public virtual MbRelease Release { get; set; } = null!;
}

public class MbReleaseToGroup
{
    public Guid ReleaseId { get; set; }
    public Guid ReleaseGroupId { get; set; }
    
    public virtual MbRelease Release { get; set; } = null!;
    public virtual MbReleaseGroup ReleaseGroup { get; set; } = null!;
}
```

**[`MbTag`](Fuzzbin.Core/Entities/MbTag.cs)** (NEW)
```csharp
public class MbTag
{
    public Guid Id { get; set; }
    public string EntityType { get; set; } = string.Empty; // 'artist', 'recording', 'release_group'
    public Guid EntityId { get; set; } // References Id in respective entity
    public string Tag { get; set; } = string.Empty;
    public int? Count { get; set; }
}
```

**[`MbRecordingCandidate`](Fuzzbin.Core/Entities/MbRecordingCandidate.cs)** (NEW)
```csharp
public class MbRecordingCandidate : BaseEntity
{
    public Guid QueryId { get; set; }
    public Guid RecordingId { get; set; }
    public string TitleNorm { get; set; } = string.Empty;
    public string ArtistNorm { get; set; } = string.Empty;
    public double TextScore { get; set; }
    public double? YearScore { get; set; }
    public double? DurationScore { get; set; }
    public double OverallScore { get; set; }
    public int Rank { get; set; }
    public bool Selected { get; set; }
    
    // Navigation
    public virtual Query Query { get; set; } = null!;
    public virtual MbRecording Recording { get; set; } = null!;
}
```

#### IMVDb Entities

**[`ImvdbArtist`](Fuzzbin.Core/Entities/ImvdbArtist.cs)** (NEW)
```csharp
public class ImvdbArtist : BaseEntity
{
    public int ImvdbId { get; set; } // IMVDb numeric ID, unique
    public string Name { get; set; } = string.Empty;
    public DateTime LastSeenAt { get; set; }
    
    // Navigation
    public virtual ICollection<ImvdbVideoArtist> VideoArtists { get; set; } = new List<ImvdbVideoArtist>();
}
```

**[`ImvdbVideo`](Fuzzbin.Core/Entities/ImvdbVideo.cs)** (NEW)
```csharp
public class ImvdbVideo : BaseEntity
{
    public int ImvdbId { get; set; } // IMVDb numeric ID, unique
    public string? SongTitle { get; set; }
    public string? VideoTitle { get; set; }
    public string? ReleaseDate { get; set; }
    public string? DirectorCredit { get; set; }
    public bool HasSources { get; set; }
    public DateTime LastSeenAt { get; set; }
    
    // Navigation
    public virtual ICollection<ImvdbVideoArtist> Artists { get; set; } = new List<ImvdbVideoArtist>();
    public virtual ICollection<ImvdbVideoSource> Sources { get; set; } = new List<ImvdbVideoSource>();
    public virtual ICollection<ImvdbVideoCandidate> Candidates { get; set; } = new List<ImvdbVideoCandidate>();
}
```

**[`ImvdbVideoArtist`](Fuzzbin.Core/Entities/ImvdbVideoArtist.cs)** (NEW)
```csharp
public class ImvdbVideoArtist
{
    public Guid VideoId { get; set; }
    public Guid ArtistId { get; set; }
    public string Role { get; set; } = string.Empty; // 'primary', 'featured'
    public int ArtistOrder { get; set; }
    
    public virtual ImvdbVideo Video { get; set; } = null!;
    public virtual ImvdbArtist Artist { get; set; } = null!;
}
```

**[`ImvdbVideoSource`](Fuzzbin.Core/Entities/ImvdbVideoSource.cs)** (NEW)
```csharp
public class ImvdbVideoSource
{
    public Guid Id { get; set; }
    public Guid VideoId { get; set; }
    public string Source { get; set; } = string.Empty; // 'youtube', 'vimeo'
    public string ExternalId { get; set; } = string.Empty;
    public bool IsOfficial { get; set; }
    
    public virtual ImvdbVideo Video { get; set; } = null!;
}
```

**[`ImvdbVideoCandidate`](Fuzzbin.Core/Entities/ImvdbVideoCandidate.cs)** (NEW)
```csharp
public class ImvdbVideoCandidate : BaseEntity
{
    public Guid QueryId { get; set; }
    public Guid VideoId { get; set; }
    public string TitleNorm { get; set; } = string.Empty;
    public string ArtistNorm { get; set; } = string.Empty;
    public double TextScore { get; set; }
    public double SourceBonus { get; set; }
    public double OverallScore { get; set; }
    public int Rank { get; set; }
    public bool Selected { get; set; }
    
    // Navigation
    public virtual Query Query { get; set; } = null!;
    public virtual ImvdbVideo Video { get; set; } = null!;
}
```

#### YouTube Entities

**[`YtVideo`](Fuzzbin.Core/Entities/YtVideo.cs)** (NEW)
```csharp
public class YtVideo : BaseEntity
{
    public string VideoId { get; set; } = string.Empty; // YouTube ID, unique
    public string Title { get; set; } = string.Empty;
    public string? ChannelId { get; set; }
    public string? ChannelName { get; set; }
    public int? DurationSeconds { get; set; }
    public int? Width { get; set; }
    public int? Height { get; set; }
    public long? ViewCount { get; set; }
    public string? PublishedAt { get; set; }
    public string? ThumbnailUrl { get; set; }
    public string? ThumbnailPath { get; set; }
    public bool? IsOfficialChannel { get; set; }
    public DateTime LastSeenAt { get; set; }
    
    // Navigation
    public virtual ICollection<YtVideoCandidate> Candidates { get; set; } = new List<YtVideoCandidate>();
}
```

**[`YtVideoCandidate`](Fuzzbin.Core/Entities/YtVideoCandidate.cs)** (NEW)
```csharp
public class YtVideoCandidate : BaseEntity
{
    public Guid QueryId { get; set; }
    public string VideoId { get; set; } = string.Empty; // FK to YtVideo.VideoId
    public string TitleNorm { get; set; } = string.Empty;
    public string ArtistNorm { get; set; } = string.Empty;
    public double TextScore { get; set; }
    public double? ChannelBonus { get; set; }
    public double? DurationScore { get; set; }
    public double OverallScore { get; set; }
    public int Rank { get; set; }
    public bool Selected { get; set; }
    
    // Navigation
    public virtual Query Query { get; set; } = null!;
    public virtual YtVideo Video { get; set; } = null!;
}
```

#### Cross-Linking & Resolution

**[`MvLink`](Fuzzbin.Core/Entities/MvLink.cs)** (NEW)
```csharp
public class MvLink : BaseEntity
{
    public Guid? ImvdbVideoId { get; set; }
    public Guid? MbRecordingId { get; set; }
    public string? YtVideoId { get; set; }
    public string LinkType { get; set; } = string.Empty; // 'imvdb_to_mb', 'imvdb_to_yt', 'mb_to_yt', 'triad'
    public double Confidence { get; set; }
    public string? Notes { get; set; }
    
    // Navigation
    public virtual ImvdbVideo? ImvdbVideo { get; set; }
    public virtual MbRecording? MbRecording { get; set; }
    public virtual YtVideo? YtVideo { get; set; }
}
```

**[`QueryResolution`](Fuzzbin.Core/Entities/QueryResolution.cs)** (NEW)
```csharp
public class QueryResolution : BaseEntity
{
    public Guid QueryId { get; set; }
    public bool MvExists { get; set; }
    public string ChosenSource { get; set; } = string.Empty; // 'imvdb', 'youtube', 'none'
    public Guid? MvLinkId { get; set; }
    public DateTime ResolvedAt { get; set; }
    
    // Navigation
    public virtual Query Query { get; set; } = null!;
    public virtual MvLink? MvLink { get; set; }
}
```

### 2.2 DbContext Configuration

Update [`ApplicationDbContext`](Fuzzbin.Data/Context/ApplicationDbContext.cs):

```csharp
// Add DbSets
public DbSet<Query> Queries { get; set; } = null!;
public DbSet<QuerySourceCache> QuerySourceCaches { get; set; } = null!;
public DbSet<MbArtist> MbArtists { get; set; } = null!;
public DbSet<MbRecording> MbRecordings { get; set; } = null!;
public DbSet<MbRelease> MbReleases { get; set; } = null!;
public DbSet<MbReleaseGroup> MbReleaseGroups { get; set; } = null!;
public DbSet<MbTag> MbTags { get; set; } = null!;
public DbSet<MbRecordingCandidate> MbRecordingCandidates { get; set; } = null!;
public DbSet<ImvdbArtist> ImvdbArtists { get; set; } = null!;
public DbSet<ImvdbVideo> ImvdbVideos { get; set; } = null!;
public DbSet<ImvdbVideoCandidate> ImvdbVideoCandidates { get; set; } = null!;
public DbSet<YtVideo> YtVideos { get; set; } = null!;
public DbSet<YtVideoCandidate> YtVideoCandidates { get; set; } = null!;
public DbSet<MvLink> MvLinks { get; set; } = null!;
public DbSet<QueryResolution> QueryResolutions { get; set; } = null!;

protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    base.OnModelCreating(modelBuilder);
    
    // Query entity
    modelBuilder.Entity<Query>(entity =>
    {
        entity.HasIndex(e => e.NormComboKey).IsUnique();
        entity.HasIndex(e => e.NormTitle);
        entity.HasIndex(e => e.NormArtist);
    });
    
    // MusicBrainz entities with MBID unique indexes
    modelBuilder.Entity<MbArtist>(entity =>
    {
        entity.HasIndex(e => e.Mbid).IsUnique();
        entity.HasIndex(e => e.Name);
    });
    
    modelBuilder.Entity<MbRecording>(entity =>
    {
        entity.HasIndex(e => e.Mbid).IsUnique();
    });
    
    // Many-to-many join tables
    modelBuilder.Entity<MbRecordingArtist>()
        .HasKey(ra => new { ra.RecordingId, ra.ArtistId });
        
    // ... (similar configurations for other entities)
    
    // IMVDb unique constraints
    modelBuilder.Entity<ImvdbArtist>(entity =>
    {
        entity.HasIndex(e => e.ImvdbId).IsUnique();
    });
    
    modelBuilder.Entity<ImvdbVideo>(entity =>
    {
        entity.HasIndex(e => e.ImvdbId).IsUnique();
    });
    
    // YouTube unique constraint
    modelBuilder.Entity<YtVideo>(entity =>
    {
        entity.HasIndex(e => e.VideoId).IsUnique();
    });
    
    // QueryResolution one-to-one with Query
    modelBuilder.Entity<QueryResolution>()
        .HasOne(qr => qr.Query)
        .WithOne(q => q.Resolution)
        .HasForeignKey<QueryResolution>(qr => qr.QueryId);
}
```

### 2.3 Migration Strategy

**Create Migration:**
```bash
dotnet ef migrations add AddMetadataCacheSchema --project Fuzzbin.Data --startup-project Fuzzbin.Web
```

**Migration Checklist:**
- [ ] All new entities added to DbContext
- [ ] Unique indexes on external IDs (Mbid, ImvdbId, VideoId)
- [ ] Composite keys for join tables
- [ ] Foreign key cascades configured appropriately
- [ ] Index on `Query.NormComboKey` for fast cache lookups

---

## 3. Configuration Management

### 3.1 Cache TTL Configuration

**Configuration Entity Values:**
```csharp
// Category: "ExternalCache"
Key = "CacheTtlHours"
Value = "336"  // Default 14 days
Description = "Cache lifetime for external metadata sources in hours (Default: 336, Max: 720, Min: 0)"

Key = "MusicBrainzUserAgent"
Value = "Fuzzbin/1.0 (https://github.com/fuzzbin)"
Description = "User-Agent string for MusicBrainz API requests (required)"
```

### 3.2 Options Pattern

**[`ExternalCacheOptions.cs`](Fuzzbin.Services/Models/ExternalCacheOptions.cs)** (NEW)
```csharp
namespace Fuzzbin.Services.Models;

public class ExternalCacheOptions
{
    public int CacheTtlHours { get; set; } = 336;
    public int MaxCacheTtlHours { get; set; } = 720;
    public int MinCacheTtlHours { get; set; } = 0;
    public string MusicBrainzUserAgent { get; set; } = "Fuzzbin/1.0";
    public int RetryCount { get; set; } = 3;
    public int RetryDelaySeconds1 { get; set; } = 2;
    public int RetryDelaySeconds2 { get; set; } = 4;
    
    public TimeSpan GetCacheDuration()
    {
        var clamped = Math.Clamp(CacheTtlHours, MinCacheTtlHours, MaxCacheTtlHours);
        return clamped == 0 ? TimeSpan.Zero : TimeSpan.FromHours(clamped);
    }
    
    public bool IsCacheEnabled() => CacheTtlHours > 0;
}
```

**[`ExternalCacheSettingsProvider.cs`](Fuzzbin.Services/ExternalCacheSettingsProvider.cs)** (NEW)
```csharp
public sealed class ExternalCacheSettingsProvider : IExternalCacheSettingsProvider
{
    private const string CacheKey = "Fuzzbin.ExternalCacheSettings";
    private static readonly TimeSpan CacheDuration = TimeSpan.FromMinutes(5);
    
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly IMemoryCache _cache;
    private readonly ILogger<ExternalCacheSettingsProvider> _logger;
    
    public ExternalCacheOptions GetSettings()
    {
        return _cache.GetOrCreate(CacheKey, entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = CacheDuration;
            return LoadSettings();
        }) ?? new ExternalCacheOptions();
    }
    
    public void Invalidate() => _cache.Remove(CacheKey);
    
    private ExternalCacheOptions LoadSettings()
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
            
            var ttlHours = ReadInt(unitOfWork, "ExternalCache", "CacheTtlHours", 336);
            var userAgent = ReadString(unitOfWork, "ExternalCache", "MusicBrainzUserAgent", 
                "Fuzzbin/1.0 (https://github.com/fuzzbin)");
            
            return new ExternalCacheOptions
            {
                CacheTtlHours = ttlHours,
                MusicBrainzUserAgent = userAgent
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load external cache settings");
            return new ExternalCacheOptions();
        }
    }
}
```

### 3.3 Service Registration

Update [`Program.cs`](Fuzzbin.Web/Program.cs):

```csharp
// After line 220 (after IMetadataSettingsProvider registration)
builder.Services.AddSingleton<IExternalCacheSettingsProvider, ExternalCacheSettingsProvider>();

// Configure options
builder.Services.AddOptions<ExternalCacheOptions>()
    .Configure<IExternalCacheSettingsProvider>((options, provider) =>
    {
        var settings = provider.GetSettings();
        options.CacheTtlHours = settings.CacheTtlHours;
        options.MusicBrainzUserAgent = settings.MusicBrainzUserAgent;
    });
```

---

## 4. Query Normalization Service

### 4.1 Implementation

**[`QueryNormalizer.cs`](Fuzzbin.Services/Metadata/QueryNormalizer.cs)** (NEW)

Implement the normalizer from [`docs/cache/normalizer.md`](docs/cache/normalizer.md) exactly as specified:

```csharp
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;

namespace Fuzzbin.Services.Metadata;

public static class QueryNormalizer
{
    private static readonly Regex MultiSpace = new Regex(@"\s+", RegexOptions.Compiled);
    private static readonly Regex PunctToSpace = new Regex(@"[^\p{L}\p{Nd}]+", RegexOptions.Compiled);
    private static readonly Regex FeatRegex = new Regex(@"\b(feat\.?|ft\.?|featuring)\b", 
        RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly Regex TrimFeatTrail = new Regex(@"\b(feat\.?|ft\.?|featuring)\b.*$", 
        RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly HashSet<string> StopSingles = new HashSet<string>(StringComparer.OrdinalIgnoreCase) 
    {
        "a"
    };

    public static string NormalizeTitle(string input)
        => NormalizeCore(input, removeTrailingFeat: true);

    public static string NormalizeArtist(string input)
        => NormalizeCore(input, removeTrailingFeat: false);

    public static (string NormTitle, string NormArtist, string ComboKey) NormalizePair(string title, string artist)
    {
        var nt = NormalizeTitle(title ?? string.Empty);
        var na = NormalizeArtist(artist ?? string.Empty);
        var combo = $"{na}||{nt}";
        return (nt, na, combo);
    }

    private static string NormalizeCore(string input, bool removeTrailingFeat)
    {
        if (string.IsNullOrWhiteSpace(input)) return string.Empty;

        // Unicode → NFKD, strip diacritics
        string nfkd = input.Normalize(NormalizationForm.FormD);
        var sb = new StringBuilder(nfkd.Length);
        foreach (var ch in nfkd)
        {
            var uc = CharUnicodeInfo.GetUnicodeCategory(ch);
            if (uc != UnicodeCategory.NonSpacingMark && uc != UnicodeCategory.EnclosingMark)
                sb.Append(ch);
        }
        string noDiacritics = sb.ToString().Normalize(NormalizationForm.FormC);

        string s = FeatRegex.Replace(noDiacritics, " feat ");

        if (removeTrailingFeat)
        {
            s = TrimFeatTrail.Replace(s, string.Empty);
        }

        s = PunctToSpace.Replace(s, " ").ToLowerInvariant();

        var tokens = MultiSpace.Split(s).Where(t => t.Length > 0).ToList();
        if (tokens.Count == 0) return string.Empty;

        tokens = tokens.Where(t => !(t.Length == 1 && StopSingles.Contains(t))).ToList();

        s = string.Join(" ", tokens);

        return s.Trim();
    }
}
```

---

## 5. Candidate Scoring Service

### 5.1 Implementation

**[`CandidateScorer.cs`](Fuzzbin.Services/Metadata/CandidateScorer.cs)** (NEW)

Implement the scorer from [`docs/cache/scoring-function.md`](docs/cache/scoring-function.md) exactly as specified. This includes:

- `ScoreBreakdown` record
- `ScoringWeights` class
- `CandidateScorer` static class with `Score()` method
- All helper methods for text/duration/year/channel/penalty scoring

Key integration points:
- Use `QueryNormalizer` for all normalization needs
- Accept nullable parameters for optional scoring signals
- Return `ScoreBreakdown` for transparency and debugging

---

## 6. HTTP Client & Retry Infrastructure

### 6.1 Polly Retry Policies

**Install NuGet Packages:**
```xml
<PackageReference Include="Polly" Version="8.0.0" />
<PackageReference Include="Polly.Extensions.Http" Version="3.0.0" />
```

**[`RetryPolicyFactory.cs`](Fuzzbin.Services/Http/RetryPolicyFactory.cs)** (NEW)
```csharp
using Polly;
using Polly.Extensions.Http;

namespace Fuzzbin.Services.Http;

public static class RetryPolicyFactory
{
    public static IAsyncPolicy<HttpResponseMessage> CreateExternalApiRetryPolicy()
    {
        return HttpPolicyExtensions
            .HandleTransientHttpError()
            .OrResult(msg => (int)msg.StatusCode == 429) // Rate limit
            .WaitAndRetryAsync(
                retryCount: 3,
                sleepDurationProvider: retryAttempt => retryAttempt switch
                {
                    1 => TimeSpan.FromSeconds(2),
                    2 => TimeSpan.FromSeconds(4),
                    _ => TimeSpan.FromSeconds(8)
                },
                onRetry: (outcome, timespan, retryCount, context) =>
                {
                    var logger = context.GetLogger();
                    logger?.LogWarning(
                        "Retry {RetryCount} after {Delay}s due to {Reason}",
                        retryCount,
                        timespan.TotalSeconds,
                        outcome.Exception?.Message ?? outcome.Result?.ReasonPhrase ?? "unknown");
                });
    }
}
```

### 6.2 Rate Limiting for MusicBrainz

**[`MusicBrainzRateLimiter.cs`](Fuzzbin.Services/Http/MusicBrainzRateLimiter.cs)** (NEW)
```csharp
using System.Threading.RateLimiting;

namespace Fuzzbin.Services.Http;

public sealed class MusicBrainzRateLimiter : IDisposable
{
    private readonly RateLimiter _rateLimiter;
    
    public MusicBrainzRateLimiter()
    {
        // 1 request per second for MusicBrainz
        _rateLimiter = new SlidingWindowRateLimiter(new SlidingWindowRateLimiterOptions
        {
            Window = TimeSpan.FromSeconds(1),
            PermitLimit = 1,
            SegmentsPerWindow = 1,
            QueueProcessingOrder = QueueProcessingOrder.OldestFirst,
            QueueLimit = 10
        });
    }
    
    public async Task<RateLimitLease> AcquireAsync(CancellationToken cancellationToken = default)
    {
        return await _rateLimiter.AcquireAsync(1, cancellationToken);
    }
    
    public void Dispose() => _rateLimiter.Dispose();
}
```

**[`MusicBrainzHttpMessageHandler.cs`](Fuzzbin.Services/Http/MusicBrainzHttpMessageHandler.cs)** (NEW)
```csharp
namespace Fuzzbin.Services.Http;

public class MusicBrainzHttpMessageHandler : DelegatingHandler
{
    private readonly MusicBrainzRateLimiter _rateLimiter;
    private readonly ILogger<MusicBrainzHttpMessageHandler> _logger;
    
    public MusicBrainzHttpMessageHandler(
        MusicBrainzRateLimiter rateLimiter,
        ILogger<MusicBrainzHttpMessageHandler> logger)
    {
        _rateLimiter = rateLimiter;
        _logger = logger;
    }
    
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        using var lease = await _rateLimiter.AcquireAsync(cancellationToken);
        
        if (!lease.IsAcquired)
        {
            _logger.LogWarning("Rate limit exceeded for MusicBrainz request");
            throw new HttpRequestException("Rate limit exceeded for MusicBrainz");
        }
        
        _logger.LogDebug("MusicBrainz rate limit acquired, making request to {Uri}", request.RequestUri);
        return await base.SendAsync(request, cancellationToken);
    }
}
```

### 6.3 HttpClient Registration

Update [`Program.cs`](Fuzzbin.Web/Program.cs):

```csharp
// After line 262 (after AddHttpClient)
builder.Services.AddSingleton<MusicBrainzRateLimiter>();
builder.Services.AddTransient<MusicBrainzHttpMessageHandler>();

builder.Services.AddHttpClient("MusicBrainz", (sp, client) =>
{
    var options = sp.GetRequiredService<IOptions<ExternalCacheOptions>>().Value;
    client.BaseAddress = new Uri("https://musicbrainz.org/ws/2/");
    client.Timeout = TimeSpan.FromSeconds(30);
    client.DefaultRequestHeaders.UserAgent.ParseAdd(options.MusicBrainzUserAgent);
})
.AddHttpMessageHandler<MusicBrainzHttpMessageHandler>()
.AddPolicyHandler(RetryPolicyFactory.CreateExternalApiRetryPolicy());

// For IMVDb and YouTube, use simple retry without rate limiting
builder.Services.AddHttpClient("ImvdbEnriched")
    .AddPolicyHandler(RetryPolicyFactory.CreateExternalApiRetryPolicy());
    
builder.Services.AddHttpClient("YouTubeDlp")
    .AddPolicyHandler(RetryPolicyFactory.CreateExternalApiRetryPolicy());
```

---

## 7. Service Layer Architecture

### 7.1 Unified Metadata Cache Service

**[`IMetadataCacheService.cs`](Fuzzbin.Core/Interfaces/IMetadataCacheService.cs)** (NEW)
```csharp
namespace Fuzzbin.Core.Interfaces;

public interface IMetadataCacheService
{
    /// <summary>
    /// Searches for metadata across all sources with intelligent caching and candidate ranking
    /// </summary>
    Task<MetadataCacheResult> SearchAsync(
        string artist,
        string title,
        int? knownDurationSeconds = null,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Gets aggregated candidate results for manual selection
    /// </summary>
    Task<List<AggregatedCandidate>> GetCandidatesAsync(
        string artist,
        string title,
        int maxResults = 10,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Applies selected candidate to a video entity
    /// </summary>
    Task<Video> ApplyMetadataAsync(
        Video video,
        AggregatedCandidate candidate,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Checks if query has cached results (without triggering new searches)
    /// </summary>
    Task<bool> IsCachedAsync(
        string artist,
        string title,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Clears all cached metadata (useful for settings changes)
    /// </summary>
    Task ClearCacheAsync(CancellationToken cancellationToken = default);
}

public class MetadataCacheResult
{
    public bool Found { get; set; }
    public AggregatedCandidate? BestMatch { get; set; }
    public List<AggregatedCandidate> AlternativeCandidates { get; set; } = new();
    public bool RequiresManualSelection { get; set; }
    public Dictionary<string, string> SourceNotes { get; set; } = new();
}

public class AggregatedCandidate
{
    public string Title { get; set; } = string.Empty;
    public string Artist { get; set; } = string.Empty;
    public string? FeaturedArtists { get; set; }
    public int? Year { get; set; }
    public List<string> Genres { get; set; } = new();
    public string? RecordLabel { get; set; }
    public string? Director { get; set; }
    public double OverallConfidence { get; set; }
    public string PrimarySource { get; set; } = string.Empty; // 'imvdb', 'musicbrainz', 'youtube'
    
    // Source-specific data (for applying to video)
    public Guid? QueryId { get; set; }
    public Guid? ImvdbVideoId { get; set; }
    public Guid? MbRecordingId { get; set; }
    public string? YtVideoId { get; set; }
    public Guid? MvLinkId { get; set; }
}
```

### 7.2 Service Implementation Structure

**[`MetadataCacheService.cs`](Fuzzbin.Services/MetadataCacheService.cs)** (NEW)

```csharp
public class MetadataCacheService : IMetadataCacheService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IMusicBrainzClient _mbClient;
    private readonly IImvdbClient _imvdbClient;
    private readonly IYtDlpService _ytDlpService;
    private readonly IExternalCacheSettingsProvider _settingsProvider;
    private readonly ILogger<MetadataCacheService> _logger;
    
    public async Task<MetadataCacheResult> SearchAsync(
        string artist,
        string title,
        int? knownDurationSeconds = null,
        CancellationToken cancellationToken = default)
    {
        // 1. Normalize query and check/create Query entity
        var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(title, artist);
        var query = await GetOrCreateQueryAsync(artist, title, normTitle, normArtist, comboKey, cancellationToken);
        
        // 2. Check if cache is still valid
        var settings = _settingsProvider.GetSettings();
        if (!settings.IsCacheEnabled())
        {
            // Cache disabled, always fetch fresh
            await FetchAllSourcesAsync(query, artist, title, knownDurationSeconds, cancellationToken);
        }
        else
        {
            var cacheExpiry = DateTime.UtcNow - settings.GetCacheDuration();
            var needsRefresh = await NeedsRefreshAsync(query.Id, cacheExpiry, cancellationToken);
            
            if (needsRefresh)
            {
                await FetchAllSourcesAsync(query, artist, title, knownDurationSeconds, cancellationToken);
            }
        }
        
        // 3. Aggregate candidates from all sources
        var candidates = await AggregateAndRankCandidatesAsync(query.Id, cancellationToken);
        
        // 4. Determine best match and if manual selection needed
        var result = new MetadataCacheResult
        {
            Found = candidates.Any(),
            BestMatch = candidates.FirstOrDefault(),
            AlternativeCandidates = candidates.Skip(1).Take(4).ToList(),
            RequiresManualSelection = candidates.Any() && candidates.First().OverallConfidence < 0.9
        };
        
        return result;
    }
    
    private async Task FetchAllSourcesAsync(
        Query query,
        string rawArtist,
        string rawTitle,
        int? knownDurationSeconds,
        CancellationToken cancellationToken)
    {
        // Execute in parallel with proper error handling
        var mbTask = FetchMusicBrainzAsync(query, rawArtist, rawTitle, cancellationToken);
        var imvdbTask = FetchImvdbAsync(query, rawArtist, rawTitle, cancellationToken);
        
        await Task.WhenAll(mbTask, imvdbTask);
        
        // Only fetch YouTube if IMVDb didn't provide sources
        var imvdbHasSources = await CheckImvdbHasSourcesAsync(query.Id, cancellationToken);
        if (!imvdbHasSources)
        {
            await FetchYouTubeAsync(query, rawArtist, rawTitle, knownDurationSeconds, cancellationToken);
        }
    }
    
    private async Task<List<AggregatedCandidate>> AggregateAndRankCandidatesAsync(
        Guid queryId,
        CancellationToken cancellationToken)
    {
        // 1. Get all candidates from all sources
        var mbCandidates = await _unitOfWork.MbRecordingCandidates
            .Where(c => c.QueryId == queryId && c.Rank <= 5)
            .Include(c => c.Recording)
                .ThenInclude(r => r.Artists)
                    .ThenInclude(ra => ra.Artist)
            .Include(c => c.Recording)
                .ThenInclude(r => r.Releases)
                    .ThenInclude(rr => rr.Release)
                        .ThenInclude(rel => rel.ReleaseGroups)
                            .ThenInclude(rtg => rtg.ReleaseGroup)
            .ToListAsync(cancellationToken);
        
        var imvdbCandidates = await _unitOfWork.ImvdbVideoCandidates
            .Where(c => c.QueryId == queryId && c.Rank <= 5)
            .Include(c => c.Video)
                .ThenInclude(v => v.Artists)
                    .ThenInclude(va => va.Artist)
            .Include(c => c.Video)
                .ThenInclude(v => v.Sources)
            .ToListAsync(cancellationToken);
        
        var ytCandidates = await _unitOfWork.YtVideoCandidates
            .Where(c => c.QueryId == queryId && c.Rank <= 5)
            .Include(c => c.Video)
            .ToListAsync(cancellationToken);
        
        // 2. Convert to aggregated form and merge duplicates
        var aggregated = new List<AggregatedCandidate>();
        
        // Process IMVDb first (highest priority per spec)
        foreach (var candidate in imvdbCandidates)
        {
            aggregated.Add(MapImvdbToAggregated(candidate));
        }
        
        // Add MusicBrainz enrichment or new candidates
        foreach (var candidate in mbCandidates)
        {
            var existing = FindMatchingCandidate(aggregated, candidate.TitleNorm, candidate.ArtistNorm);
            if (existing != null)
            {
                EnrichWithMusicBrainz(existing, candidate);
            }
            else
            {
                aggregated.Add(MapMbToAggregated(candidate));
            }
        }
        
        // Add YouTube if not already matched
        foreach (var candidate in ytCandidates)
        {
            var existing = FindMatchingCandidate(aggregated, candidate.TitleNorm, candidate.ArtistNorm);
            if (existing == null)
            {
                aggregated.Add(MapYtToAggregated(candidate));
            }
        }
        
        // 3. Sort by overall confidence
        return aggregated
            .OrderByDescending(c => c.OverallConfidence)
            .ToList();
    }
}
```

---

## 8. JSON Parser Enhancements

### 8.1 Parser Gap Analysis

Based on review of the API response examples in [`docs/cache/imvdb-examples.md`](docs/cache/imvdb-examples.md) and [`docs/cache/musicbrainz-examples.md`](docs/cache/musicbrainz-examples.md), the current JSON parsers in [`IImvdbApi.cs`](Fuzzbin.Services/External/Imvdb/IImvdbApi.cs) and [`MetadataService.cs`](Fuzzbin.Services/MetadataService.cs) require significant enhancements to support the cache integration strategy.

**Critical Finding:** Without these parser enhancements, the cache system cannot properly populate entity relationships, compute accurate scores, or track official sources.

### 8.2 IMVDb Parser Enhancements

#### 8.2.1 Current Gaps

The existing [`IImvdbApi.cs`](Fuzzbin.Services/External/Imvdb/IImvdbApi.cs) parser is missing:

**From Search Response:**
1. **`video_title`** - Separate from `song_title` (currently conflated as `title`)
2. **`has_sources`** - Boolean indicating YouTube/Vimeo availability (**blocks line 254**)
3. **`artists` array** - Structured data with `id`, `name`, `role`, `order` (**blocks lines 264-275**)
4. **`thumbnail` object** - Width/height metadata (currently flat string)
5. **`release_date`** - String date field

**From Video Detail Response:**
1. **`runtime_seconds`** - Duration metadata
2. **`directors` array** - Structured director data with IDs
3. **`sources` array** - **CRITICAL - blocks lines 278-289 and scoring on line 301**:
   - `source` ('youtube', 'vimeo')
   - `external_id` (YouTube video ID)
   - `url`
   - `is_official` (**Required for scoring bonus**)

#### 8.2.2 Enhanced Response Models

**[`ImvdbResponseModels.cs`](Fuzzbin.Services/External/Imvdb/ImvdbResponseModels.cs)** (NEW)

```csharp
using System.Collections.Generic;
using Refit;

namespace Fuzzbin.Services.External.Imvdb;

// Enhanced search response
public class ImvdbSearchResponse
{
    [AliasAs("page")] public int Page { get; set; }
    [AliasAs("per_page")] public int PerPage { get; set; }
    [AliasAs("total_results")] public int TotalResults { get; set; }
    [AliasAs("results")] public List<ImvdbVideoSummary> Results { get; set; } = new();
}

public class ImvdbVideoSummary
{
    [AliasAs("id")] public long Id { get; set; }  // Changed to long for 64-bit IDs
    [AliasAs("url")] public string? Url { get; set; }
    [AliasAs("song_title")] public string? SongTitle { get; set; }
    [AliasAs("video_title")] public string? VideoTitle { get; set; }  // NEW
    [AliasAs("release_date")] public string? ReleaseDate { get; set; }  // NEW
    [AliasAs("has_sources")] public bool HasSources { get; set; }  // NEW - CRITICAL
    [AliasAs("artists")] public List<ImvdbArtistCredit> Artists { get; set; } = new();  // NEW
    [AliasAs("thumbnail")] public ImvdbThumbnail? Thumbnail { get; set; }  // Enhanced
}

// NEW: Structured artist credit
public class ImvdbArtistCredit
{
    [AliasAs("id")] public int Id { get; set; }
    [AliasAs("name")] public string Name { get; set; } = string.Empty;
    [AliasAs("role")] public string Role { get; set; } = string.Empty;  // 'primary', 'featured'
    [AliasAs("order")] public int Order { get; set; }
}

// NEW: Structured thumbnail
public class ImvdbThumbnail
{
    [AliasAs("url")] public string? Url { get; set; }
    [AliasAs("width")] public int? Width { get; set; }
    [AliasAs("height")] public int? Height { get; set; }
}

// Enhanced detail response
public class ImvdbVideoResponse
{
    [AliasAs("id")] public long Id { get; set; }
    [AliasAs("url")] public string? Url { get; set; }
    [AliasAs("song_title")] public string? SongTitle { get; set; }
    [AliasAs("video_title")] public string? VideoTitle { get; set; }  // NEW
    [AliasAs("release_date")] public string? ReleaseDate { get; set; }
    [AliasAs("runtime_seconds")] public int? RuntimeSeconds { get; set; }  // NEW
    [AliasAs("thumbnail")] public ImvdbThumbnail? Thumbnail { get; set; }
    
    [AliasAs("artists")] public List<ImvdbArtistCredit> Artists { get; set; } = new();
    [AliasAs("directors")] public List<ImvdbDirector> Directors { get; set; } = new();  // Enhanced
    [AliasAs("sources")] public List<ImvdbSource> Sources { get; set; } = new();  // NEW - CRITICAL
}

// NEW: Structured director
public class ImvdbDirector
{
    [AliasAs("id")] public int Id { get; set; }
    [AliasAs("name")] public string Name { get; set; } = string.Empty;
}

// NEW: Structured source - CRITICAL for cache strategy
public class ImvdbSource
{
    [AliasAs("source")] public string Source { get; set; } = string.Empty;  // 'youtube', 'vimeo'
    [AliasAs("external_id")] public string ExternalId { get; set; } = string.Empty;
    [AliasAs("url")] public string Url { get; set; } = string.Empty;
    [AliasAs("is_official")] public bool IsOfficial { get; set; }  // CRITICAL for scoring
}
```

#### 8.2.3 Enhanced API Interface

**[`IImvdbApi.cs`](Fuzzbin.Services/External/Imvdb/IImvdbApi.cs)** (UPDATE)

```csharp
using System.Threading;
using System.Threading.Tasks;
using Refit;

namespace Fuzzbin.Services.External.Imvdb;

public interface IImvdbApi
{
    [Get("/search/videos")]
    Task<ImvdbSearchResponse> SearchVideosAsync(
        [AliasAs("q")] string query,
        [AliasAs("page")] int page = 1,
        [AliasAs("per_page")] int perPage = 20,
        CancellationToken cancellationToken = default);

    [Get("/video/{id}")]
    Task<ImvdbVideoResponse> GetVideoAsync(
        string id,
        [AliasAs("include")] string? include = "artists,directors,sources",  // NEW: include parameter
        CancellationToken cancellationToken = default);
}
```

### 8.3 MusicBrainz Parser Enhancements

#### 8.3.1 Current Gaps

The existing MusicBrainz parser in [`MetadataService.cs`](Fuzzbin.Services/MetadataService.cs:429-520) is severely incomplete:

**Missing from Recording Search:**
1. **`score`** - MusicBrainz relevance score (should inform ranking)
2. **Full `artist-credit` array** - Currently only parses first artist:
   - Missing `joinphrase` field (**blocks line 170: `IsJoinPhraseFeat`**)
   - Missing support for multiple artists
3. **Complete `releases` array** - Currently only first release:
   - Missing `track-count`, `country`, `barcode` (**blocks lines 153-154**)
4. **Nested `release-group` data** - **CRITICAL for year scoring**:
   - `first-release-date` (**blocks line 137 and year scoring on line 218**)
   - `primary-type` (Album, Single, EP)
5. **`tags` array** - Completely missing (**blocks lines 125, 206-207**)
6. **`genres` array** - Completely missing (**blocks genre tracking**)

**Not Implemented:**
- Release Group lookup endpoint
- Artist lookup endpoint
- Proper `inc` parameter support

#### 8.3.2 Enhanced Response Models

**[`MusicBrainzResponseModels.cs`](Fuzzbin.Services/External/MusicBrainz/MusicBrainzResponseModels.cs)** (NEW)

```csharp
using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Fuzzbin.Services.External.MusicBrainz;

// Complete recording search response
public class MbRecordingSearchResponse
{
    [JsonPropertyName("created")] public DateTime? Created { get; set; }
    [JsonPropertyName("count")] public int Count { get; set; }
    [JsonPropertyName("offset")] public int Offset { get; set; }
    [JsonPropertyName("recordings")] public List<MbRecording> Recordings { get; set; } = new();
}

public class MbRecording
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    [JsonPropertyName("length")] public int? Length { get; set; }  // milliseconds
    [JsonPropertyName("score")] public int Score { get; set; }  // NEW - MusicBrainz relevance
    [JsonPropertyName("artist-credit")] public List<MbArtistCredit> ArtistCredit { get; set; } = new();
    [JsonPropertyName("releases")] public List<MbRelease> Releases { get; set; } = new();
    [JsonPropertyName("tags")] public List<MbTag> Tags { get; set; } = new();  // NEW
    [JsonPropertyName("genres")] public List<MbTag> Genres { get; set; } = new();  // NEW
}

// Enhanced artist credit with join phrases
public class MbArtistCredit
{
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;  // Credited name
    [JsonPropertyName("joinphrase")] public string? JoinPhrase { get; set; }  // NEW - " feat. ", " & ", etc.
    [JsonPropertyName("artist")] public MbArtist Artist { get; set; } = new();
}

public class MbArtist
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;
    [JsonPropertyName("sort-name")] public string SortName { get; set; } = string.Empty;
    [JsonPropertyName("disambiguation")] public string? Disambiguation { get; set; }  // NEW
    [JsonPropertyName("country")] public string? Country { get; set; }  // NEW
}

// Enhanced release with full data
public class MbRelease
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    [JsonPropertyName("date")] public string? Date { get; set; }
    [JsonPropertyName("country")] public string? Country { get; set; }  // NEW
    [JsonPropertyName("barcode")] public string? Barcode { get; set; }  // NEW
    [JsonPropertyName("track-count")] public int? TrackCount { get; set; }  // NEW
    [JsonPropertyName("label-info")] public List<MbLabelInfo>? LabelInfo { get; set; }  // NEW
    [JsonPropertyName("release-group")] public MbReleaseGroup? ReleaseGroup { get; set; }  // Enhanced
}

// NEW: Label info data
public class MbLabelInfo
{
    [JsonPropertyName("catalog-number")] public string? CatalogNumber { get; set; }
    [JsonPropertyName("label")] public MbLabel? Label { get; set; }
}

public class MbLabel
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;
}

// NEW: Release group data - CRITICAL for year scoring
public class MbReleaseGroup
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    [JsonPropertyName("first-release-date")] public string? FirstReleaseDate { get; set; }  // CRITICAL
    [JsonPropertyName("primary-type")] public string? PrimaryType { get; set; }  // Album, Single, EP
    [JsonPropertyName("tags")] public List<MbTag> Tags { get; set; } = new();
    [JsonPropertyName("genres")] public List<MbTag> Genres { get; set; } = new();
}

// NEW: Tag/Genre data
public class MbTag
{
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;
    [JsonPropertyName("count")] public int? Count { get; set; }
}
```

#### 8.3.3 New MusicBrainz Client Interface

**[`IMusicBrainzClient.cs`](Fuzzbin.Services/External/MusicBrainz/IMusicBrainzClient.cs)** (NEW)

```csharp
using System.Threading;
using System.Threading.Tasks;

namespace Fuzzbin.Services.External.MusicBrainz;

public interface IMusicBrainzClient
{
    /// <summary>
    /// Search for recordings by artist and title
    /// </summary>
    Task<MbRecordingSearchResponse?> SearchRecordingsAsync(
        string artist,
        string title,
        int limit = 5,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get detailed recording information by MBID
    /// </summary>
    Task<MbRecording?> GetRecordingAsync(
        string mbid,
        string[]? include = null,  // artist-credits, releases, release-groups, tags, genres
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get release group information by MBID
    /// </summary>
    Task<MbReleaseGroup?> GetReleaseGroupAsync(
        string mbid,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get artist information by MBID
    /// </summary>
    Task<MbArtist?> GetArtistAsync(
        string mbid,
        CancellationToken cancellationToken = default);
}
```

#### 8.3.4 MusicBrainz Client Implementation

**[`MusicBrainzClient.cs`](Fuzzbin.Services/External/MusicBrainz/MusicBrainzClient.cs)** (NEW)

```csharp
using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Web;
using Microsoft.Extensions.Logging;

namespace Fuzzbin.Services.External.MusicBrainz;

public class MusicBrainzClient : IMusicBrainzClient
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<MusicBrainzClient> _logger;
    private readonly JsonSerializerOptions _jsonOptions;

    public MusicBrainzClient(
        IHttpClientFactory httpClientFactory,
        ILogger<MusicBrainzClient> logger)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };
    }

    public async Task<MbRecordingSearchResponse?> SearchRecordingsAsync(
        string artist,
        string title,
        int limit = 5,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var query = $"artist:\"{artist}\" AND recording:\"{title}\"";
            var url = $"recording?query={HttpUtility.UrlEncode(query)}&fmt=json&limit={limit}" +
                     "&inc=artist-credits+releases+release-groups+labels+tags+genres";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("MusicBrainz search failed with status {Status}", response.StatusCode);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<MbRecordingSearchResponse>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error searching MusicBrainz for {Artist} - {Title}", artist, title);
            return null;
        }
    }

    public async Task<MbRecording?> GetRecordingAsync(
        string mbid,
        string[]? include = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var includeParam = include != null && include.Length > 0
                ? $"&inc={string.Join("+", include)}"
                : "&inc=artist-credits+releases+release-groups+labels+tags+genres";

            var url = $"recording/{mbid}?fmt=json{includeParam}";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("MusicBrainz recording lookup failed with status {Status}", response.StatusCode);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<MbRecording>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz recording {Mbid}", mbid);
            return null;
        }
    }

    public async Task<MbReleaseGroup?> GetReleaseGroupAsync(
        string mbid,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = $"release-group/{mbid}?fmt=json&inc=tags+genres";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("MusicBrainz release-group lookup failed with status {Status}", response.StatusCode);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<MbReleaseGroup>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz release-group {Mbid}", mbid);
            return null;
        }
    }

    public async Task<MbArtist?> GetArtistAsync(
        string mbid,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = $"artist/{mbid}?fmt=json&inc=aliases+tags+genres";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("MusicBrainz artist lookup failed with status {Status}", response.StatusCode);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<MbArtist>(json, _jsonOptions);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz artist {Mbid}", mbid);
            return null;
        }
    }
}
```

### 8.4 Parser Enhancement Priority

#### Critical (Blocks Core Functionality)
1. **IMVDb `sources` array** - Required for [`ImvdbVideoSource`](Fuzzbin.Core/Entities/ImvdbVideoSource.cs:278-289) entities and `is_official` scoring
2. **IMVDb `has_sources` field** - Required for [`ImvdbVideo.HasSources`](Fuzzbin.Core/Entities/ImvdbVideo.cs:254) population
3. **MusicBrainz `first-release-date`** - Required for year scoring ([`MbReleaseGroup.FirstReleaseDate`](Fuzzbin.Core/Entities/MbReleaseGroup.cs:137))
4. **MusicBrainz full `artist-credit` array** - Required for [`IsJoinPhraseFeat`](Fuzzbin.Core/Entities/MbRecordingArtist.cs:170) detection

#### High Priority (Needed for Full Feature Set)
5. **IMVDb structured `artists` array** - Required for [`ImvdbVideoArtist`](Fuzzbin.Core/Entities/ImvdbVideoArtist.cs:264-275) join table
6. **MusicBrainz `tags`/`genres` arrays** - Required for [`MbTag`](Fuzzbin.Core/Entities/MbTag.cs:197-207) entities
7. **MusicBrainz complete `releases` array** - Required for track numbers and full relationship mapping

#### Medium Priority (Improves Data Quality)
8. **IMVDb structured `thumbnail` object** - Better structured data
9. **IMVDb `video_title` vs `song_title` distinction** - More accurate field mapping
10. **MusicBrainz `score` field** - Can inform initial ranking

### 8.5 Integration into Roadmap

**Update Phase 3: External Client Services (Week 2)**

Original checklist:
- [ ] Create `IMusicBrainzClient` interface
- [ ] Implement `MusicBrainzClient` with response parsing
- [ ] Create `IImvdbClient` interface (enhanced from existing)
- [ ] Implement `ImvdbClient` with enhanced functionality
- [ ] Update `YtDlpService` for new integration points
- [ ] Add unit tests for all clients

**Enhanced checklist:**
- [ ] **Create complete MusicBrainz response models** (`MusicBrainzResponseModels.cs`)
- [ ] **Create enhanced IMVDb response models** (`ImvdbResponseModels.cs`)
- [ ] Create `IMusicBrainzClient` interface
- [ ] **Implement `MusicBrainzClient` with full API support** (search, recording, release-group, artist)
- [ ] **Update `IImvdbApi` interface** to support `include` parameter
- [ ] **Update existing IMVDb Refit models** to use enhanced response classes
- [ ] Create `IImvdbClient` wrapper interface (if needed for additional logic)
- [ ] Update `YtDlpService` for new integration points
- [ ] **Add parser tests validating all fields from example responses**
- [ ] Add unit tests for all clients

### 8.6 Testing Requirements

**Parser Validation Tests** (NEW)

```csharp
[Fact]
public void ImvdbVideoResponse_ParsesSourcesArray()
{
    var json = File.ReadAllText("testdata/imvdb-video-detail.json");
    var response = JsonSerializer.Deserialize<ImvdbVideoResponse>(json);
    
    Assert.NotNull(response);
    Assert.NotEmpty(response.Sources);
    Assert.Equal("youtube", response.Sources[0].Source);
    Assert.Equal("XcATvu5f9vE", response.Sources[0].ExternalId);
    Assert.True(response.Sources[0].IsOfficial);
}

[Fact]
public void MbRecording_ParsesReleaseGroupFirstReleaseDate()
{
    var json = File.ReadAllText("testdata/mb-recording-search.json");
    var response = JsonSerializer.Deserialize<MbRecordingSearchResponse>(json);
    
    Assert.NotNull(response);
    Assert.NotEmpty(response.Recordings);
    var recording = response.Recordings[0];
    Assert.NotNull(recording.Releases[0].ReleaseGroup);
    Assert.Equal("2002-04-30", recording.Releases[0].ReleaseGroup.FirstReleaseDate);
}

[Fact]
public void MbArtistCredit_ParsesJoinPhrase()
{
    var json = File.ReadAllText("testdata/mb-recording-with-featuring.json");
    var response = JsonSerializer.Deserialize<MbRecordingSearchResponse>(json);
    
    Assert.NotNull(response);
    var recording = response.Recordings[0];
    Assert.True(recording.ArtistCredit.Count > 1);
    Assert.Contains("feat", recording.ArtistCredit[1].JoinPhrase?.ToLower());
}
```

### 8.7 Migration from Existing Parser

**Backward Compatibility Strategy:**

1. Create new response models alongside existing ones
2. Update API interfaces to use new models
3. Create mapper utilities to convert from new models to existing `ImvdbMetadata` / `MusicBrainzMetadata` DTOs (for existing code)
4. Gradually migrate consumers to use new models directly
5. Deprecate old models once migration complete

---

## 9. Implementation Roadmap

### Phase 1: Foundation (Week 1)
- [x] Complete analysis of existing infrastructure
- [x] Complete JSON parser gap analysis (Section 8)
- [ ] Create all new Entity classes
- [ ] Update DbContext with new DbSets and configurations
- [ ] Generate and test EF Core migration
- [ ] Implement `QueryNormalizer` service
- [ ] Implement `CandidateScorer` service
- [ ] Add unit tests for normalization and scoring

### Phase 2: HTTP & Retry Infrastructure (Week 1-2)
- [ ] Install Polly NuGet packages
- [ ] Implement `RetryPolicyFactory`
- [ ] Implement `MusicBrainzRateLimiter`
- [ ] Implement `MusicBrainzHttpMessageHandler`
- [ ] Register HttpClients in Program.cs
- [ ] Add integration tests for retry logic

### Phase 3: External Client Services & Parser Enhancements (Week 2) **CRITICAL**
- [ ] **Create `MusicBrainzResponseModels.cs` with complete models** (Section 8.3.2)
- [ ] **Create `ImvdbResponseModels.cs` with enhanced models** (Section 8.2.2)
- [ ] **Create `IMusicBrainzClient` interface** (Section 8.3.3)
- [ ] **Implement `MusicBrainzClient` with full API support** (Section 8.3.4):
  - [ ] Search recordings with all fields
  - [ ] Get recording by MBID
  - [ ] Get release-group by MBID
  - [ ] Get artist by MBID
- [ ] **Update `IImvdbApi` interface to support `include` parameter** (Section 8.2.3)
- [ ] **Update existing IMVDb Refit models** to use enhanced response classes
- [ ] Create `IImvdbClient` wrapper interface (if needed)
- [ ] Update `YtDlpService` for new integration points
- [ ] **Add parser validation tests** (Section 8.6):
  - [ ] Test IMVDb sources array parsing
  - [ ] Test MusicBrainz release-group date parsing
  - [ ] Test artist-credit join phrase parsing
  - [ ] Test tags/genres array parsing
- [ ] Add unit tests for all clients

### Phase 4: Cache Service Implementation (Week 3)
- [ ] Implement `IMetadataCacheService` interface
- [ ] Implement `MetadataCacheService` core logic
- [ ] Implement source-specific fetch methods
- [ ] Implement candidate aggregation logic
- [ ] Implement cache expiry checking
- [ ] Add comprehensive integration tests

### Phase 5: UI Integration (Week 3-4)
- [ ] Add cache TTL configuration to Settings page
- [ ] Create candidate selection dialog component
- [ ] Update video enrichment UI to use new service
- [ ] Add cache clear functionality to Settings
- [ ] Update library import to use new service
- [ ] Add UI indicators for cache status

### Phase 6: Migration & Testing (Week 4)
- [ ] Create data migration script for existing Video metadata
- [ ] Implement backward compatibility layer
- [ ] Perform end-to-end testing
- [ ] Load testing with cache enabled/disabled
- [ ] Document API changes and new features
- [ ] Create user documentation

### Phase 7: Deployment & Monitoring (Week 4+)
- [ ] Deploy to staging environment
- [ ] Monitor cache hit rates
- [ ] Monitor API error rates and retries
- [ ] Gather user feedback on candidate selection
- [ ] Performance optimization based on metrics
- [ ] Production deployment

---

## 9. Key Integration Points

### 9.1 Replace Existing Calls

**Current [`MetadataService.EnrichVideoMetadataWithResultAsync()`](Fuzzbin.Services/MetadataService.cs:725)**
```csharp
// OLD CODE (lines 776-821)
if (fetchOnlineMetadata && !string.IsNullOrWhiteSpace(video.Artist) && !string.IsNullOrWhiteSpace(video.Title))
{
    var imvdbMetadata = await GetImvdbMetadataAsync(video.Artist, video.Title, cancellationToken);
    // ... apply metadata
    
    var mbMetadata = await GetMusicBrainzMetadataAsync(video.Artist, video.Title, cancellationToken);
    // ... apply metadata
}

// NEW CODE
if (fetchOnlineMetadata && !string.IsNullOrWhiteSpace(video.Artist) && !string.IsNullOrWhiteSpace(video.Title))
{
    var cacheResult = await _metadataCacheService.SearchAsync(
        video.Artist, 
        video.Title, 
        video.Duration,
        cancellationToken);
    
    if (cacheResult.Found && cacheResult.BestMatch != null)
    {
        if (cacheResult.RequiresManualSelection)
        {
            result.RequiresManualReview = true;
            result.MatchConfidence = cacheResult.BestMatch.OverallConfidence;
        }
        else
        {
            video = await _metadataCacheService.ApplyMetadataAsync(
                video, 
                cacheResult.BestMatch, 
                cancellationToken);
            result.MetadataApplied = true;
        }
    }
}
```

### 9.2 Update ExternalSearchService

**[`ExternalSearchService.SearchAsync()`](Fuzzbin.Services/ExternalSearchService.cs:37)** should delegate to cache service and format results for UI:

```csharp
public async Task<ExternalSearchResult> SearchAsync(
    ExternalSearchQuery query, 
    CancellationToken cancellationToken = default)
{
    var candidates = await _metadataCacheService.GetCandidatesAsync(
        query.Artist ?? string.Empty,
        query.Title ?? string.Empty,
        query.MaxResults,
        cancellationToken);
    
    var result = new ExternalSearchResult
    {
        Items = candidates.Select(c => new ExternalSearchItem
        {
            Title = c.Title,
            Artist = c.Artist,
            Source = MapSourceToEnum(c.PrimarySource),
            Confidence = c.OverallConfidence,
            // ... map other fields
        }).ToList()
    };
    
    return result;
}
```

### 9.3 Library Import Integration

**[`LibraryImportService`](Fuzzbin.Services/LibraryImportService.cs)** should use cache service during import:

```csharp
// After video creation, enrich with cached metadata
var cacheResult = await _metadataCacheService.SearchAsync(
    video.Artist,
    video.Title,
    video.Duration,
    cancellationToken);

if (cacheResult.Found && cacheResult.BestMatch != null && !cacheResult.RequiresManualSelection)
{
    video = await _metadataCacheService.ApplyMetadataAsync(
        video,
        cacheResult.BestMatch,
        cancellationToken);
}
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

**Normalizer Tests:**
```csharp
[Fact]
public void NormalizePair_RemovesFeaturedArtistsFromTitle()
{
    var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(
        "Still Fly (feat. Mannie Fresh)", 
        "Big Tymers");
    
    Assert.Equal("still fly", normTitle);
    Assert.Contains("big tymers", normArtist);
}
```

**Scorer Tests:**
```csharp
[Fact]
public void Score_ReturnsHighConfidence_ForExactMatch()
{
    var score = CandidateScorer.Score(
        normQueryTitle: "still fly",
        normQueryArtist: "big tymers",
        candidateTitleNorm: "still fly",
        candidateArtistNorm: "big tymers",
        candidateDurationSec: 224,
        mbReferenceDurationSec: 224,
        candidateYear: 2002,
        mbEarliestYear: 2002,
        hasOfficialSourceFromImvdb: true);
    
    Assert.True(score.Overall >= 0.95);
}
```

### 10.2 Integration Tests

**Cache Persistence Tests:**
```csharp
[Fact]
public async Task SearchAsync_UsesCachedResults_WhenValid()
{
    // First search - populates cache
    await _service.SearchAsync("Big Tymers", "Still Fly");
    
    // Second search - should use cache (no HTTP calls)
    var result = await _service.SearchAsync("Big Tymers", "Still Fly");
    
    Assert.True(result.Found);
    // Verify no HTTP calls were made
}
```

### 10.3 End-to-End Tests

**Full Metadata Enrichment Flow:**
1. Create video with minimal data
2. Trigger enrichment
3. Verify all sources queried
4. Verify candidates ranked correctly
5. Verify best match applied
6. Verify cache populated

---

## 11. Monitoring & Metrics

### 11.1 Key Metrics to Track

- Cache hit rate (%)
- Average confidence score of applied metadata
- Manual selection rate (%)
- API error rates by source
- Retry attempt distribution
- Cache size and growth rate
- Query normalization collision rate

### 11.2 Logging Strategy

```csharp
_logger.LogInformation(
    "Metadata search for {Artist} - {Title}: Found={Found}, Confidence={Confidence:P0}, Source={Source}, Cached={Cached}",
    artist, title, result.Found, result.BestMatch?.OverallConfidence, result.BestMatch?.PrimarySource, wasCached);
```

---

## 12. Configuration UI

### 12.1 Settings Page Updates

Add section to [`Settings.razor`](Fuzzbin.Web/Components/Pages/Settings.razor):

```razor
<MudExpansionPanel Text="External Metadata Cache" Icon="@Icons.Material.Filled.Storage">
    <MudNumericField @bind-Value="_cacheTtlHours"
                     Label="Cache Lifetime (hours)"
                     HelperText="How long to keep cached metadata. Default: 336 (14 days), Max: 720 (30 days), Min: 0 (disabled)"
                     Min="0"
                     Max="720"
                     Step="24" />
    
    <MudText Typo="Typo.caption" Class="mb-4">
        Caches metadata from MusicBrainz, IMVDb, and YouTube to reduce API calls and improve performance.
        Set to 0 to disable caching (always fetch fresh data).
    </MudText>
    
    <MudStack Row="true" Spacing="2">
        <MudButton Variant="Variant.Outlined"
                   Color="Color.Info"
                   StartIcon="@Icons.Material.Filled.Info"
                   OnClick="ShowCacheStats">
            View Cache Statistics
        </MudButton>
        
        <MudButton Variant="Variant.Outlined"
                   Color="Color.Warning"
                   StartIcon="@Icons.Material.Filled.DeleteSweep"
                   OnClick="ClearMetadataCache">
            Clear All Cached Data
        </MudButton>
    </MudStack>
</MudExpansionPanel>
```

---

## 13. Success Criteria

### 13.1 Functional Requirements
- ✅ All external service calls are cached with configurable TTL
- ✅ Cache survives application restart
- ✅ Failed/incomplete results are not cached
- ✅ 3 retry attempts with 2s/4s delays
- ✅ Multiple candidates presented when confidence < 0.9
- ✅ IMVDb data takes precedence in conflicts
- ✅ Aggregated candidate view shows all metadata fields

### 13.2 Performance Requirements
- Cache hit rate > 80% after initial library enrichment
- API error rate < 5%
- Average enrichment time < 2s (cached) or < 10s (fresh)
- Database query time < 100ms for cache lookups

### 13.3 User Experience
- Settings UI clearly explains cache configuration
- Manual candidate selection shows ranked options
- Cache clear provides confirmation and feedback

---

## 14. Next Steps

To begin implementation:

1. **Review this strategy document** with stakeholders
2. **Ask clarifying questions** about any ambiguous requirements
3. **Switch to Code mode** to begin Phase 1 implementation
4. **Create feature branch** for metadata cache integration
5. **Implement incrementally** following the roadmap phases

**Recommended approach:** Start with Phase 1 (database schema) as it's foundational and enables parallel work on other phases once merged.

---

## 15. Background Maintenance System

### 15.1 Overview

A unified background maintenance system automatically performs periodic housekeeping tasks to maintain database health and performance. The initial implementation includes cache purging, with an extensible architecture to support additional maintenance operations like library rescanning, thumbnail cleanup, and orphaned file detection.

**Key Features:**
- Configurable maintenance interval (default: 8 hours)
- Extensible task registration system
- Sequential task execution with progress tracking
- Per-task enable/disable configuration
- Manual trigger support via API

### 15.2 Architecture

#### 15.2.1 Maintenance Task Interface

**[`IMaintenanceTask.cs`](Fuzzbin.Core/Interfaces/IMaintenanceTask.cs)** (NEW)

```csharp
namespace Fuzzbin.Core.Interfaces;

/// <summary>
/// Interface for background maintenance tasks that can be scheduled and executed periodically
/// </summary>
public interface IMaintenanceTask
{
    /// <summary>
    /// Unique identifier for this maintenance task
    /// </summary>
    string TaskName { get; }
    
    /// <summary>
    /// Human-readable description of what this task does
    /// </summary>
    string Description { get; }
    
    /// <summary>
    /// Whether this task is enabled and should be executed
    /// </summary>
    bool IsEnabled { get; }
    
    /// <summary>
    /// Executes the maintenance task
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Result summary of the maintenance operation</returns>
    Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken);
}

public class MaintenanceTaskResult
{
    public bool Success { get; set; }
    public string Summary { get; set; } = string.Empty;
    public int ItemsProcessed { get; set; }
    public TimeSpan Duration { get; set; }
    public string? ErrorMessage { get; set; }
}
```

#### 15.2.2 Cache Purge Maintenance Task

**[`CachePurgeMaintenanceTask.cs`](Fuzzbin.Services/Maintenance/CachePurgeMaintenanceTask.cs)** (NEW)

```csharp
using System;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.Maintenance;

/// <summary>
/// Maintenance task that purges expired cache entries based on configured TTL
/// </summary>
public class CachePurgeMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IExternalCacheSettingsProvider _cacheSettings;
    private readonly ILogger<CachePurgeMaintenanceTask> _logger;
    
    public string TaskName => "CachePurge";
    public string Description => "Purge expired metadata cache entries";
    
    public bool IsEnabled
    {
        get
        {
            var settings = _cacheSettings.GetSettings();
            return settings.IsCacheEnabled() && settings.EnableAutomaticPurge;
        }
    }
    
    public CachePurgeMaintenanceTask(
        IUnitOfWork unitOfWork,
        IExternalCacheSettingsProvider cacheSettings,
        ILogger<CachePurgeMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _cacheSettings = cacheSettings;
        _logger = logger;
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        var stats = new PurgeStatistics();
        
        try
        {
            var settings = _cacheSettings.GetSettings();
            
            if (!settings.IsCacheEnabled())
            {
                return new MaintenanceTaskResult
                {
                    Success = true,
                    Summary = "Cache disabled - no purge performed",
                    Duration = stopwatch.Elapsed
                };
            }
            
            var expirationThreshold = DateTime.UtcNow - settings.GetCacheDuration();
            
            _logger.LogInformation(
                "Starting cache purge. TTL: {TtlHours}h, Expiration threshold: {Threshold}",
                settings.CacheTtlHours,
                expirationThreshold);
            
            // Step 1: Delete expired candidates
            stats.MbCandidatesDeleted = await PurgeMbCandidatesAsync(expirationThreshold, cancellationToken);
            stats.ImvdbCandidatesDeleted = await PurgeImvdbCandidatesAsync(expirationThreshold, cancellationToken);
            stats.YtCandidatesDeleted = await PurgeYtCandidatesAsync(expirationThreshold, cancellationToken);
            
            // Step 2: Delete expired QuerySourceCache entries
            stats.SourceCachesDeleted = await PurgeQuerySourceCachesAsync(expirationThreshold, cancellationToken);
            
            // Step 3: Delete expired QueryResolution entries
            stats.QueryResolutionsDeleted = await PurgeQueryResolutionsAsync(expirationThreshold, cancellationToken);
            
            // Step 4: Delete expired Query entities
            stats.QueriesDeleted = await PurgeQueriesAsync(expirationThreshold, cancellationToken);
            
            // Step 5: Clean up orphaned source entities
            stats.OrphanedMbRecordings = await PurgeOrphanedMbRecordingsAsync(cancellationToken);
            stats.OrphanedImvdbVideos = await PurgeOrphanedImvdbVideosAsync(cancellationToken);
            stats.OrphanedYtVideos = await PurgeOrphanedYtVideosAsync(cancellationToken);
            
            // Step 6: Clean up orphaned MvLinks
            stats.OrphanedMvLinks = await PurgeOrphanedMvLinksAsync(cancellationToken);
            
            stopwatch.Stop();
            
            var summary = stats.GetSummary();
            var totalItems = stats.GetTotalCount();
            
            _logger.LogInformation(
                "Cache purge completed in {Duration}ms: {Summary}",
                stopwatch.ElapsedMilliseconds,
                summary);
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = summary,
                ItemsProcessed = totalItems,
                Duration = stopwatch.Elapsed
            };
        }
        catch (Exception ex)
        {
            stopwatch.Stop();
            _logger.LogError(ex, "Cache purge failed");
            
            return new MaintenanceTaskResult
            {
                Success = false,
                Summary = "Cache purge failed",
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed
            };
        }
    }
    
    // Purge implementation methods (same as before)
    private async Task<int> PurgeMbCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.Queries
            .GetQueryable()
            .Where(q => q.SourceCaches.All(sc => sc.LastCheckedAt < threshold))
            .Select(q => q.Id)
            .ToListAsync(ct);
        
        if (!expiredQueries.Any()) return 0;
        
        var candidates = await _unitOfWork.MbRecordingCandidates
            .GetQueryable()
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            await _unitOfWork.MbRecordingCandidates.DeleteAsync(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return candidates.Count;
    }
    
    private async Task<int> PurgeImvdbCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.Queries
            .GetQueryable()
            .Where(q => q.SourceCaches.All(sc => sc.LastCheckedAt < threshold))
            .Select(q => q.Id)
            .ToListAsync(ct);
        
        if (!expiredQueries.Any()) return 0;
        
        var candidates = await _unitOfWork.ImvdbVideoCandidates
            .GetQueryable()
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            await _unitOfWork.ImvdbVideoCandidates.DeleteAsync(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return candidates.Count;
    }
    
    private async Task<int> PurgeYtCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.Queries
            .GetQueryable()
            .Where(q => q.SourceCaches.All(sc => sc.LastCheckedAt < threshold))
            .Select(q => q.Id)
            .ToListAsync(ct);
        
        if (!expiredQueries.Any()) return 0;
        
        var candidates = await _unitOfWork.YtVideoCandidates
            .GetQueryable()
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            await _unitOfWork.YtVideoCandidates.DeleteAsync(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return candidates.Count;
    }
    
    private async Task<int> PurgeQuerySourceCachesAsync(DateTime threshold, CancellationToken ct)
    {
        var expired = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(sc => sc.LastCheckedAt < threshold)
            .ToListAsync(ct);
        
        foreach (var cache in expired)
        {
            await _unitOfWork.QuerySourceCaches.DeleteAsync(cache);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return expired.Count;
    }
    
    private async Task<int> PurgeQueryResolutionsAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.Queries
            .GetQueryable()
            .Where(q => q.SourceCaches.All(sc => sc.LastCheckedAt < threshold))
            .Select(q => q.Id)
            .ToListAsync(ct);
        
        if (!expiredQueries.Any()) return 0;
        
        var resolutions = await _unitOfWork.QueryResolutions
            .GetQueryable()
            .Where(qr => expiredQueries.Contains(qr.QueryId))
            .ToListAsync(ct);
        
        foreach (var resolution in resolutions)
        {
            await _unitOfWork.QueryResolutions.DeleteAsync(resolution);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return resolutions.Count;
    }
    
    private async Task<int> PurgeQueriesAsync(DateTime threshold, CancellationToken ct)
    {
        var expired = await _unitOfWork.Queries
            .GetQueryable()
            .Include(q => q.SourceCaches)
            .Where(q => q.SourceCaches.All(sc => sc.LastCheckedAt < threshold))
            .ToListAsync(ct);
        
        foreach (var query in expired)
        {
            await _unitOfWork.Queries.DeleteAsync(query);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return expired.Count;
    }
    
    private async Task<int> PurgeOrphanedMbRecordingsAsync(CancellationToken ct)
    {
        var orphaned = await _unitOfWork.MbRecordings
            .GetQueryable()
            .Where(r => !r.Candidates.Any())
            .ToListAsync(ct);
        
        foreach (var recording in orphaned)
        {
            await DeleteMbRecordingRelationsAsync(recording.Id, ct);
            await _unitOfWork.MbRecordings.DeleteAsync(recording);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return orphaned.Count;
    }
    
    private async Task DeleteMbRecordingRelationsAsync(Guid recordingId, CancellationToken ct)
    {
        // Note: This assumes IUnitOfWork has a method to get DbContext or queryable for join tables
        // Implementation details depend on your UnitOfWork design
        // For now, this is pseudocode - actual implementation needs access to join table repositories
    }
    
    private async Task<int> PurgeOrphanedImvdbVideosAsync(CancellationToken ct)
    {
        var orphaned = await _unitOfWork.ImvdbVideos
            .GetQueryable()
            .Where(v => !v.Candidates.Any())
            .ToListAsync(ct);
        
        foreach (var video in orphaned)
        {
            await _unitOfWork.ImvdbVideos.DeleteAsync(video);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return orphaned.Count;
    }
    
    private async Task<int> PurgeOrphanedYtVideosAsync(CancellationToken ct)
    {
        var orphaned = await _unitOfWork.YtVideos
            .GetQueryable()
            .Where(v => !v.Candidates.Any())
            .ToListAsync(ct);
        
        foreach (var video in orphaned)
        {
            await _unitOfWork.YtVideos.DeleteAsync(video);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return orphaned.Count;
    }
    
    private async Task<int> PurgeOrphanedMvLinksAsync(CancellationToken ct)
    {
        // Simplified - actual implementation needs proper join queries
        var orphaned = await _unitOfWork.MvLinks
            .GetQueryable()
            .ToListAsync(ct); // Would need proper filtering
        
        foreach (var link in orphaned)
        {
            await _unitOfWork.MvLinks.DeleteAsync(link);
        }
        
        await _unitOfWork.SaveChangesAsync();
        return orphaned.Count;
    }
    
    private class PurgeStatistics
    {
        public int MbCandidatesDeleted { get; set; }
        public int ImvdbCandidatesDeleted { get; set; }
        public int YtCandidatesDeleted { get; set; }
        public int SourceCachesDeleted { get; set; }
        public int QueryResolutionsDeleted { get; set; }
        public int QueriesDeleted { get; set; }
        public int OrphanedMbRecordings { get; set; }
        public int OrphanedImvdbVideos { get; set; }
        public int OrphanedYtVideos { get; set; }
        public int OrphanedMvLinks { get; set; }
        
        public int GetTotalCount() =>
            MbCandidatesDeleted + ImvdbCandidatesDeleted + YtCandidatesDeleted +
            SourceCachesDeleted + QueryResolutionsDeleted + QueriesDeleted +
            OrphanedMbRecordings + OrphanedImvdbVideos + OrphanedYtVideos + OrphanedMvLinks;
        
        public string GetSummary()
        {
            var total = GetTotalCount();
            return $"Purged {total} total entries: " +
                   $"{QueriesDeleted} queries, " +
                   $"{SourceCachesDeleted} source caches, " +
                   $"{MbCandidatesDeleted + ImvdbCandidatesDeleted + YtCandidatesDeleted} candidates, " +
                   $"{OrphanedMbRecordings + OrphanedImvdbVideos + OrphanedYtVideos} orphaned metadata";
        }
    }
}
```

#### 15.2.3 Maintenance Scheduler Service

**[`MaintenanceSchedulerService.cs`](Fuzzbin.Services/MaintenanceSchedulerService.cs)** (NEW)

```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services;

/// <summary>
/// Background service that executes registered maintenance tasks on a configurable schedule
/// </summary>
public class MaintenanceSchedulerService : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<MaintenanceSchedulerService> _logger;
    private readonly TimeSpan _maintenanceInterval;
    private readonly TimeSpan _initialDelay = TimeSpan.FromMinutes(5);
    
    public MaintenanceSchedulerService(
        IServiceScopeFactory scopeFactory,
        IExternalCacheSettingsProvider settingsProvider,
        ILogger<MaintenanceSchedulerService> logger)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
        
        var settings = settingsProvider.GetSettings();
        _maintenanceInterval = settings.GetMaintenanceInterval();
    }
    
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation(
            "Maintenance scheduler started. Initial delay: {InitialDelay}, Interval: {Interval}",
            _initialDelay,
            _maintenanceInterval);
        
        // Wait initial delay before first run
        await Task.Delay(_initialDelay, stoppingToken);
        
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await RunMaintenanceTasksAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during maintenance execution");
            }
            
            // Wait for next scheduled run
            await Task.Delay(_maintenanceInterval, stoppingToken);
        }
        
        _logger.LogInformation("Maintenance scheduler stopped");
    }
    
    private async Task RunMaintenanceTasksAsync(CancellationToken cancellationToken)
    {
        using var scope = _scopeFactory.CreateScope();
        
        // Discover all registered maintenance tasks
        var tasks = scope.ServiceProvider.GetServices<IMaintenanceTask>().ToList();
        
        if (!tasks.Any())
        {
            _logger.LogWarning("No maintenance tasks registered");
            return;
        }
        
        _logger.LogInformation(
            "Starting maintenance run with {TaskCount} registered tasks",
            tasks.Count);
        
        var results = new List<(string TaskName, MaintenanceTaskResult Result)>();
        
        foreach (var task in tasks)
        {
            if (cancellationToken.IsCancellationRequested)
                break;
            
            try
            {
                if (!task.IsEnabled)
                {
                    _logger.LogDebug(
                        "Skipping disabled maintenance task: {TaskName}",
                        task.TaskName);
                    continue;
                }
                
                _logger.LogInformation(
                    "Executing maintenance task: {TaskName} - {Description}",
                    task.TaskName,
                    task.Description);
                
                var result = await task.ExecuteAsync(cancellationToken);
                results.Add((task.TaskName, result));
                
                if (result.Success)
                {
                    _logger.LogInformation(
                        "Maintenance task {TaskName} completed in {Duration}ms: {Summary}",
                        task.TaskName,
                        result.Duration.TotalMilliseconds,
                        result.Summary);
                }
                else
                {
                    _logger.LogError(
                        "Maintenance task {TaskName} failed: {Error}",
                        task.TaskName,
                        result.ErrorMessage);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(
                    ex,
                    "Unhandled exception in maintenance task: {TaskName}",
                    task.TaskName);
                
                results.Add((task.TaskName, new MaintenanceTaskResult
                {
                    Success = false,
                    ErrorMessage = ex.Message,
                    Duration = TimeSpan.Zero
                }));
            }
        }
        
        // Log summary
        var successful = results.Count(r => r.Result.Success);
        var failed = results.Count - successful;
        var totalItems = results.Sum(r => r.Result.ItemsProcessed);
        var totalDuration = TimeSpan.FromMilliseconds(results.Sum(r => r.Result.Duration.TotalMilliseconds));
        
        _logger.LogInformation(
            "Maintenance run completed. Success: {Successful}/{Total}, " +
            "Failed: {Failed}, Items processed: {Items}, Duration: {Duration}ms",
            successful,
            results.Count,
            failed,
            totalItems,
            totalDuration.TotalMilliseconds);
    }
}
```

### 15.3 Configuration

#### 15.3.1 Update ExternalCacheOptions

**[`ExternalCacheOptions.cs`](Fuzzbin.Services/Models/ExternalCacheOptions.cs)**

```csharp
public class ExternalCacheOptions
{
    public int CacheTtlHours { get; set; } = 336;
    public int MaxCacheTtlHours { get; set; } = 720;
    public int MinCacheTtlHours { get; set; } = 0;
    public string MusicBrainzUserAgent { get; set; } = "Fuzzbin/1.0";
    public int RetryCount { get; set; } = 3;
    public int RetryDelaySeconds1 { get; set; } = 2;
    public int RetryDelaySeconds2 { get; set; } = 4;
    
    // Maintenance configuration
    public bool EnableAutomaticPurge { get; set; } = true;
    public int MaintenanceIntervalHours { get; set; } = 8;
    
    public TimeSpan GetCacheDuration()
    {
        var clamped = Math.Clamp(CacheTtlHours, MinCacheTtlHours, MaxCacheTtlHours);
        return clamped == 0 ? TimeSpan.Zero : TimeSpan.FromHours(clamped);
    }
    
    public TimeSpan GetMaintenanceInterval()
    {
        return TimeSpan.FromHours(Math.Max(1, MaintenanceIntervalHours));
    }
    
    public bool IsCacheEnabled() => CacheTtlHours > 0;
}
```

#### 15.3.2 Configuration UI

Add to [`Settings.razor`](Fuzzbin.Web/Components/Pages/Settings.razor):

```razor
<MudExpansionPanel Text="External Metadata Cache" Icon="@Icons.Material.Filled.Storage">
    <MudNumericField @bind-Value="_cacheTtlHours"
                     Label="Cache Lifetime (hours)"
                     HelperText="How long to keep cached metadata. Default: 336 (14 days), Max: 720 (30 days), Min: 0 (disabled)"
                     Min="0"
                     Max="720"
                     Step="24" />
    
    <MudCheckBox @bind-Checked="_enableAutomaticPurge"
                 Label="Enable Automatic Maintenance"
                 Color="Color.Primary">
        Automatically perform background maintenance tasks
    </MudCheckBox>
    
    <MudNumericField @bind-Value="_maintenanceIntervalHours"
                     Label="Background Maintenance Interval (hours)"
                     HelperText="How often to run maintenance tasks (cache purge, cleanup). Default: 8 hours"
                     Min="1"
                     Max="168"
                     Disabled="@(!_enableAutomaticPurge)"
                     Step="1" />
    
    <MudText Typo="Typo.caption" Class="mb-4">
        Background maintenance includes cache purging, orphaned data cleanup, and other housekeeping tasks.
        Tasks run automatically on the configured schedule.
    </MudText>
    
    <MudStack Row="true" Spacing="2">
        <MudButton Variant="Variant.Outlined"
                   Color="Color.Info"
                   StartIcon="@Icons.Material.Filled.Info"
                   OnClick="ShowCacheStats">
            View Cache Statistics
        </MudButton>
        
        <MudButton Variant="Variant.Outlined"
                   Color="Color.Warning"
                   StartIcon="@Icons.Material.Filled.CleaningServices"
                   OnClick="TriggerMaintenance">
            Run Maintenance Now
        </MudButton>
    </MudStack>
</MudExpansionPanel>
```

### 15.4 Service Registration

Update [`Program.cs`](Fuzzbin.Web/Program.cs):

```csharp
// After line 246 - Register maintenance tasks
builder.Services.AddScoped<IMaintenanceTask, CachePurgeMaintenanceTask>();
// Future tasks can be registered here:
// builder.Services.AddScoped<IMaintenanceTask, LibraryRescanMaintenanceTask>();
// builder.Services.AddScoped<IMaintenanceTask, ThumbnailCleanupMaintenanceTask>();

// After line 255 - Register background services
builder.Services.AddHostedService<DownloadBackgroundService>();
builder.Services.AddHostedService<ThumbnailBackgroundService>();
builder.Services.AddHostedService<BackgroundJobProcessorService>();
builder.Services.AddHostedService<MaintenanceSchedulerService>();
```

### 15.5 API Endpoint for Manual Trigger

Add to [`Program.cs`](Fuzzbin.Web/Program.cs) after existing endpoints:

```csharp
// POST /api/maintenance/run - Manual maintenance trigger
app.MapPost("/api/maintenance/run", async (
    IServiceScopeFactory scopeFactory,
    ILogger<Program> logger,
    CancellationToken ct) =>
{
    using var scope = scopeFactory.CreateScope();
    var tasks = scope.ServiceProvider.GetServices<IMaintenanceTask>().ToList();
    
    if (!tasks.Any())
    {
        return Results.NotFound(new { message = "No maintenance tasks configured" });
    }
    
    var results = new List<object>();
    
    foreach (var task in tasks)
    {
        if (!task.IsEnabled) continue;
        
        try
        {
            var result = await task.ExecuteAsync(ct);
            results.Add(new
            {
                taskName = task.TaskName,
                success = result.Success,
                summary = result.Summary,
                itemsProcessed = result.ItemsProcessed,
                durationMs = result.Duration.TotalMilliseconds,
                error = result.ErrorMessage
            });
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Error executing maintenance task {TaskName}", task.TaskName);
            results.Add(new
            {
                taskName = task.TaskName,
                success = false,
                error = ex.Message
            });
        }
    }
    
    return Results.Ok(new
    {
        message = "Maintenance tasks executed",
        tasksRun = results.Count,
        results
    });
})
.WithName("RunMaintenance")
.RequireAuthorization();
```

### 15.6 Future Extensibility Examples

#### 15.6.1 Library Rescan Task (Future)

```csharp
public class LibraryRescanMaintenanceTask : IMaintenanceTask
{
    public string TaskName => "LibraryRescan";
    public string Description => "Rescan video library for new/changed files";
    public bool IsEnabled => _settings.EnableLibraryRescan;
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken ct)
    {
        // Scan library directory
        // Detect new files
        // Update database
        // Return results
    }
}
```

#### 15.6.2 Thumbnail Cleanup Task (Future)

```csharp
public class ThumbnailCleanupMaintenanceTask : IMaintenanceTask
{
    public string TaskName => "ThumbnailCleanup";
    public string Description => "Remove orphaned thumbnail files";
    public bool IsEnabled => true;
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken ct)
    {
        // Find thumbnail files without matching videos
        // Delete orphaned files
        // Return cleanup statistics
    }
}
```

### 15.7 Implementation Checklist

- [ ] Create `IMaintenanceTask` interface
- [ ] Implement `CachePurgeMaintenanceTask` with purge logic
- [ ] Create `MaintenanceSchedulerService` with task discovery
- [ ] Add `MaintenanceIntervalHours` to `ExternalCacheOptions`
- [ ] Update configuration provider to load maintenance settings
- [ ] Register maintenance task and scheduler in `Program.cs`
- [ ] Add maintenance trigger API endpoint
- [ ] Update Settings UI with maintenance controls
- [ ] Write unit tests for cache purge task
- [ ] Write integration tests for scheduler
- [ ] Document extensibility patterns for future tasks
- [ ] Add logging and monitoring

### 15.8 Testing Strategy

```csharp
[Fact]
public async Task CachePurgeTask_RemovesExpiredEntries()
{
    // Arrange: Create expired and valid cache entries
    // Act: Execute maintenance task
    // Assert: Expired deleted, valid remain
}

[Fact]
public async Task MaintenanceScheduler_ExecutesAllEnabledTasks()
{
    // Arrange: Register multiple tasks
    // Act: Run maintenance cycle
    // Assert: All enabled tasks executed
}

[Fact]
public async Task MaintenanceScheduler_SkipsDisabledTasks()
{
    // Arrange: Register tasks with IsEnabled = false
    // Act: Run maintenance cycle
    // Assert: Disabled tasks not executed
}
```

---
