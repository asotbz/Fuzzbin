# Cache Maintenance Tasks

## Overview

Two maintenance tasks handle cache lifecycle: purging expired entries and collecting statistics for historical analysis.

---

## Task 1: Cache Purge

Removes expired metadata cache entries based on configured TTL.

**Task Name**: `CachePurge`  
**Default Schedule**: Every maintenance run (8 hours)  
**Default Status**: Enabled

### Functionality

#### 1. Expire Cache Entries

Based on `ExternalCacheOptions.CacheTtlHours` configuration:
- Query entries from `QuerySourceCache` table
- Check `LastCheckedAt` timestamp
- Delete entries older than TTL
- Cascade delete related candidate records

#### 2. Orphaned Entity Cleanup

Clean up orphaned metadata entities:
- `MbRecording`, `MbArtist`, `MbRelease`, etc. with no active links
- `ImvdbVideo`, `ImvdbArtist` with no active links
- `YtVideo` with no active links

#### 3. Statistics

Track:
- Total cache entries checked
- Entries expired and deleted
- Orphaned entities removed
- Database space reclaimed

### Implementation

**Location**: `Fuzzbin.Services/Maintenance/CachePurgeMaintenanceTask.cs`

```csharp
using System;
using System.Collections.Generic;
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
/// Purges expired metadata cache entries
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
            // Only enabled if caching is enabled
            var options = _cacheSettings.GetSettings();
            return options.IsCacheEnabled();
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
        var metrics = new Dictionary<string, object>();
        
        try
        {
            var options = _cacheSettings.GetSettings();
            var ttl = options.GetCacheDuration();
            
            if (ttl == TimeSpan.Zero)
            {
                return new MaintenanceTaskResult
                {
                    Success = true,
                    Summary = "Cache is disabled, nothing to purge",
                    ItemsProcessed = 0,
                    Duration = stopwatch.Elapsed
                };
            }
            
            var expirationThreshold = DateTime.UtcNow - ttl;
            
            _logger.LogInformation(
                "Starting cache purge for entries older than {Threshold} (TTL: {TTL:g})",
                expirationThreshold, ttl);
            
            // Step 1: Purge MusicBrainz candidates
            var mbPurged = await PurgeMbCandidatesAsync(expirationThreshold, cancellationToken);
            metrics["mbCandidatesPurged"] = mbPurged;
            
            // Step 2: Purge IMVDb candidates
            var imvdbPurged = await PurgeImvdbCandidatesAsync(expirationThreshold, cancellationToken);
            metrics["imvdbCandidatesPurged"] = imvdbPurged;
            
            // Step 3: Purge YouTube candidates
            var ytPurged = await PurgeYtCandidatesAsync(expirationThreshold, cancellationToken);
            metrics["ytCandidatesPurged"] = ytPurged;
            
            // Step 4: Purge QuerySourceCache entries
            var sourceCachePurged = await PurgeQuerySourceCachesAsync(expirationThreshold, cancellationToken);
            metrics["sourceCachesPurged"] = sourceCachePurged;
            
            // Step 5: Clean up orphaned queries (no active cache or resolution)
            var queriesPurged = await PurgeOrphanedQueriesAsync(cancellationToken);
            metrics["queriesPurged"] = queriesPurged;
            
            // Step 6: Clean up orphaned entities
            var orphanedEntities = await PurgeOrphanedEntitiesAsync(cancellationToken);
            metrics["orphanedEntitiesPurged"] = orphanedEntities;
            
            stopwatch.Stop();
            
            var totalPurged = mbPurged + imvdbPurged + ytPurged + sourceCachePurged + 
                            queriesPurged + orphanedEntities;
            
            var summary = $"Purged {totalPurged} cache entries: " +
                         $"{mbPurged} MB, {imvdbPurged} IMVDb, {ytPurged} YT, " +
                         $"{sourceCachePurged} source caches, {queriesPurged} queries, " +
                         $"{orphanedEntities} orphaned entities";
            
            _logger.LogInformation(summary);
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = summary,
                ItemsProcessed = totalPurged,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during cache purge");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
    }
    
    private async Task<int> PurgeMbCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        // Find expired MusicBrainz candidates via QuerySourceCache
        var expiredQueries = await _unitOfWork.QuerySourceCaches
            .Where(qsc => qsc.Source == "musicbrainz" && qsc.LastCheckedAt < threshold)
            .Select(qsc => qsc.QueryId)
            .Distinct()
            .ToListAsync(ct);
        
        if (!expiredQueries.Any())
            return 0;
        
        var candidates = await _unitOfWork.MbRecordingCandidates
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            _unitOfWork.MbRecordingCandidates.Remove(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} MusicBrainz candidates", candidates.Count);
        return candidates.Count;
    }
    
    private async Task<int> PurgeImvdbCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.QuerySourceCaches
            .Where(qsc => qsc.Source == "imvdb" && qsc.LastCheckedAt < threshold)
            .Select(qsc => qsc.QueryId)
            .Distinct()
            .ToListAsync(ct);
        
        if (!expiredQueries.Any())
            return 0;
        
        var candidates = await _unitOfWork.ImvdbVideoCandidates
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            _unitOfWork.ImvdbVideoCandidates.Remove(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} IMVDb candidates", candidates.Count);
        return candidates.Count;
    }
    
    private async Task<int> PurgeYtCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.QuerySourceCaches
            .Where(qsc => qsc.Source == "youtube" && qsc.LastCheckedAt < threshold)
            .Select(qsc => qsc.QueryId)
            .Distinct()
            .ToListAsync(ct);
        
        if (!expiredQueries.Any())
            return 0;
        
        var candidates = await _unitOfWork.YtVideoCandidates
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            _unitOfWork.YtVideoCandidates.Remove(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} YouTube candidates", candidates.Count);
        return candidates.Count;
    }
    
    private async Task<int> PurgeQuerySourceCachesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredCaches = await _unitOfWork.QuerySourceCaches
            .Where(qsc => qsc.LastCheckedAt < threshold)
            .ToListAsync(ct);
        
        if (!expiredCaches.Any())
            return 0;
        
        foreach (var cache in expiredCaches)
        {
            _unitOfWork.QuerySourceCaches.Remove(cache);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} QuerySourceCache entries", expiredCaches.Count);
        return expiredCaches.Count;
    }
    
    private async Task<int> PurgeOrphanedQueriesAsync(CancellationToken ct)
    {
        // Queries with no active source caches and no resolution
        var orphanedQueries = await _unitOfWork.Queries
            .Where(q => !q.SourceCaches.Any() && q.Resolution == null)
            .ToListAsync(ct);
        
        if (!orphanedQueries.Any())
            return 0;
        
        foreach (var query in orphanedQueries)
        {
            _unitOfWork.Queries.Remove(query);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} orphaned queries", orphanedQueries.Count);
        return orphanedQueries.Count;
    }
    
    private async Task<int> PurgeOrphanedEntitiesAsync(CancellationToken ct)
    {
        var totalPurged = 0;
        
        // MusicBrainz recordings with no candidates or links
        var orphanedRecordings = await _unitOfWork.MbRecordings
            .Where(r => !r.Candidates.Any() && !r.MvLinks.Any())
            .ToListAsync(ct);
        
        foreach (var recording in orphanedRecordings)
        {
            _unitOfWork.MbRecordings.Remove(recording);
        }
        totalPurged += orphanedRecordings.Count;
        
        // IMVDb videos with no candidates or links
        var orphanedImvdbVideos = await _unitOfWork.ImvdbVideos
            .Where(v => !v.Candidates.Any() && !v.MvLinks.Any())
            .ToListAsync(ct);
        
        foreach (var video in orphanedImvdbVideos)
        {
            _unitOfWork.ImvdbVideos.Remove(video);
        }
        totalPurged += orphanedImvdbVideos.Count;
        
        // YouTube videos with no candidates or links
        var orphanedYtVideos = await _unitOfWork.YtVideos
            .Where(v => !v.Candidates.Any() && !v.MvLinks.Any())
            .ToListAsync(ct);
        
        foreach (var video in orphanedYtVideos)
        {
            _unitOfWork.YtVideos.Remove(video);
        }
        totalPurged += orphanedYtVideos.Count;
        
        if (totalPurged > 0)
        {
            await _unitOfWork.SaveChangesAsync();
            _logger.LogInformation("Purged {Count} orphaned entities", totalPurged);
        }
        
        return totalPurged;
    }
}
```

### Configuration

```csharp
// Task is auto-enabled when cache is enabled
// Uses ExternalCacheOptions.CacheTtlHours for expiration threshold
```

---

## Task 2: Cache Statistics Collection

Collects and stores cache performance metrics for historical analysis.

**Task Name**: `CacheStats`  
**Default Schedule**: Every maintenance run (8 hours)  
**Default Status**: Enabled

### Functionality

#### 1. Collect Current Stats

Snapshot current cache state:
- Total queries cached
- Cache entries per source (MB, IMVDb, YouTube)
- Candidates per query (min/max/avg)
- Hit rate (queries with resolutions)
- Cache size (database rows)

#### 2. Store Historical Data

Insert into `CacheStatSnapshot` table:
- Timestamp
- Metric values
- Calculated derivatives (hit rate %, growth rate)

#### 3. Purge Old Stats

Remove statistics older than retention period (default: 14 days)

### Implementation

**Location**: `Fuzzbin.Services/Maintenance/CacheStatsMaintenanceTask.cs`

```csharp
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Services.Maintenance;

/// <summary>
/// Collects cache statistics for historical analysis
/// </summary>
public class CacheStatsMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<CacheStatsMaintenanceTask> _logger;
    
    public string TaskName => "CacheStats";
    public string Description => "Collect cache performance statistics";
    
    public bool IsEnabled
    {
        get
        {
            var config = _unitOfWork.Configurations
                .FirstOrDefault(c => c.Category == "Maintenance" 
                    && c.Key == "CacheStats.Enabled");
            return config?.Value != "false"; // Enabled by default
        }
    }
    
    public CacheStatsMaintenanceTask(
        IUnitOfWork unitOfWork,
        ILogger<CacheStatsMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        
        try
        {
            _logger.LogInformation("Collecting cache statistics");
            
            // Collect current stats
            var snapshot = await CollectSnapshotAsync(cancellationToken);
            
            // Store in database
            await _unitOfWork.CacheStatSnapshots.AddAsync(snapshot);
            await _unitOfWork.SaveChangesAsync();
            
            // Purge old stats
            var retentionDays = GetRetentionDays();
            var threshold = DateTime.UtcNow.AddDays(-retentionDays);
            
            var oldStats = await _unitOfWork.CacheStatSnapshots
                .Where(s => s.SnapshotAt < threshold)
                .ToListAsync(cancellationToken);
            
            foreach (var stat in oldStats)
            {
                _unitOfWork.CacheStatSnapshots.Remove(stat);
            }
            
            if (oldStats.Any())
            {
                await _unitOfWork.SaveChangesAsync();
            }
            
            stopwatch.Stop();
            
            var summary = $"Collected cache stats: " +
                         $"{snapshot.TotalQueries} queries, " +
                         $"{snapshot.HitRatePercent:F1}% hit rate, " +
                         $"purged {oldStats.Count} old stats";
            
            _logger.LogInformation(summary);
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = summary,
                ItemsProcessed = 1,
                Duration = stopwatch.Elapsed,
                Metrics = new Dictionary<string, object>
                {
                    ["totalQueries"] = snapshot.TotalQueries,
                    ["hitRate"] = snapshot.HitRatePercent,
                    ["oldStatsPurged"] = oldStats.Count
                }
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error collecting cache statistics");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed
            };
        }
    }
    
    private async Task<CacheStatSnapshot> CollectSnapshotAsync(CancellationToken ct)
    {
        var totalQueries = await _unitOfWork.Queries.CountAsync(ct);
        
        var mbSourceCaches = await _unitOfWork.QuerySourceCaches
            .Where(qsc => qsc.Source == "musicbrainz")
            .CountAsync(ct);
        
        var imvdbSourceCaches = await _unitOfWork.QuerySourceCaches
            .Where(qsc => qsc.Source == "imvdb")
            .CountAsync(ct);
        
        var ytSourceCaches = await _unitOfWork.QuerySourceCaches
            .Where(qsc => qsc.Source == "youtube")
            .CountAsync(ct);
        
        var totalResolutions = await _unitOfWork.QueryResolutions.CountAsync(ct);
        
        var mbCandidates = await _unitOfWork.MbRecordingCandidates.CountAsync(ct);
        var imvdbCandidates = await _unitOfWork.ImvdbVideoCandidates.CountAsync(ct);
        var ytCandidates = await _unitOfWork.YtVideoCandidates.CountAsync(ct);
        
        var hitRatePercent = totalQueries > 0 
            ? (double)totalResolutions / totalQueries * 100.0 
            : 0.0;
        
        var avgCandidatesPerQuery = totalQueries > 0
            ? (double)(mbCandidates + imvdbCandidates + ytCandidates) / totalQueries
            : 0.0;
        
        return new CacheStatSnapshot
        {
            SnapshotAt = DateTime.UtcNow,
            TotalQueries = totalQueries,
            MbSourceCaches = mbSourceCaches,
            ImvdbSourceCaches = imvdbSourceCaches,
            YtSourceCaches = ytSourceCaches,
            TotalResolutions = totalResolutions,
            MbCandidates = mbCandidates,
            ImvdbCandidates = imvdbCandidates,
            YtCandidates = ytCandidates,
            HitRatePercent = Math.Round(hitRatePercent, 2),
            AvgCandidatesPerQuery = Math.Round(avgCandidatesPerQuery, 2)
        };
    }
    
    private int GetRetentionDays()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "CacheStats.RetentionDays");
        
        if (int.TryParse(config?.Value, out var days) && days > 0)
        {
            return days;
        }
        
        return 14; // Default: 14 days
    }
}
```

### Configuration

```csharp
Category: "Maintenance"
Key: "CacheStats.Enabled"
Value: "true"
Description: "Enable cache statistics collection"

Category: "Maintenance"
Key: "CacheStats.RetentionDays"
Value: "14"
Description: "Days to retain cache statistics (older stats are purged)"
```

---

## Database Schema

### CacheStatSnapshot Entity

**Location**: `Fuzzbin.Core/Entities/CacheStatSnapshot.cs`

```csharp
namespace Fuzzbin.Core.Entities;

/// <summary>
/// Snapshot of cache statistics at a point in time
/// </summary>
public class CacheStatSnapshot : BaseEntity
{
    /// <summary>
    /// When this snapshot was taken
    /// </summary>
    public DateTime SnapshotAt { get; set; }
    
    /// <summary>
    /// Total queries in cache
    /// </summary>
    public int TotalQueries { get; set; }
    
    /// <summary>
    /// MusicBrainz source cache entries
    /// </summary>
    public int MbSourceCaches { get; set; }
    
    /// <summary>
    /// IMVDb source cache entries
    /// </summary>
    public int ImvdbSourceCaches { get; set; }
    
    /// <summary>
    /// YouTube source cache entries
    /// </summary>
    public int YtSourceCaches { get; set; }
    
    /// <summary>
    /// Total query resolutions
    /// </summary>
    public int TotalResolutions { get; set; }
    
    /// <summary>
    /// MusicBrainz candidates
    /// </summary>
    public int MbCandidates { get; set; }
    
    /// <summary>
    /// IMVDb candidates
    /// </summary>
    public int ImvdbCandidates { get; set; }
    
    /// <summary>
    /// YouTube candidates
    /// </summary>
    public int YtCandidates { get; set; }
    
    /// <summary>
    /// Cache hit rate percentage
    /// </summary>
    public double HitRatePercent { get; set; }
    
    /// <summary>
    /// Average candidates per query
    /// </summary>
    public double AvgCandidatesPerQuery { get; set; }
}
```

Add to `ApplicationDbContext`:

```csharp
public DbSet<CacheStatSnapshot> CacheStatSnapshots { get; set; } = null!;
```

**Migration**:
```bash
dotnet ef migrations add AddCacheStatSnapshot --project Fuzzbin.Data --startup-project Fuzzbin.Web
```

---

## UI Integration

### Cache Statistics Dashboard

**Location**: Add to existing `CacheStatsDialog.razor` or create new page

```razor
<MudCard>
    <MudCardHeader>
        <CardHeaderContent>
            <MudText Typo="Typo.h6">Historical Cache Performance</MudText>
        </CardHeaderContent>
    </MudCardHeader>
    <MudCardContent>
        @if (_chartData != null)
        {
            <ApexChart TItem="CacheStatSnapshot"
                       Options="_chartOptions"
                       @ref="_chart">
                <ApexPointSeries TItem="CacheStatSnapshot"
                                Items="_chartData"
                                SeriesType="SeriesType.Line"
                                Name="Hit Rate %"
                                XValue="@(e => e.SnapshotAt)"
                                YValue="@(e => (decimal)e.HitRatePercent)" />
                                
                <ApexPointSeries TItem="CacheStatSnapshot"
                                Items="_chartData"
                                SeriesType="SeriesType.Line"
                                Name="Total Queries"
                                XValue="@(e => e.SnapshotAt)"
                                YValue="@(e => e.TotalQueries)" />
            </ApexChart>
        }
    </MudCardContent>
</MudCard>

@code {
    private List<CacheStatSnapshot>? _chartData;
    private ApexChart<CacheStatSnapshot>? _chart;
    
    protected override async Task OnInitializedAsync()
    {
        await LoadHistoricalStats();
    }
    
    private async Task LoadHistoricalStats()
    {
        try
        {
            _chartData = await Http.GetFromJsonAsync<List<CacheStatSnapshot>>(
                "/api/cache/stats/history?days=7");
        }
        catch (Exception ex)
        {
            Snackbar.Add($"Error loading stats: {ex.Message}", Severity.Error);
        }
    }
}
```

### API Endpoints

Add to `Program.cs`:

```csharp
// GET /api/cache/stats/history - Get historical cache statistics
app.MapGet("/api/cache/stats/history", async (
    IUnitOfWork unitOfWork,
    int days = 7) =>
{
    var threshold = DateTime.UtcNow.AddDays(-days);
    
    var stats = await unitOfWork.CacheStatSnapshots
        .Where(s => s.SnapshotAt >= threshold)
        .OrderBy(s => s.SnapshotAt)
        .ToListAsync();
    
    return Results.Ok(stats);
})
.WithName("GetCacheStatsHistory")
.RequireAuthorization();
```

---

## Testing

### Cache Purge Tests

```csharp
[Fact]
public async Task CachePurge_RemovesExpiredEntries()
{
    // Arrange: Create expired cache entries
    var oldTimestamp = DateTime.UtcNow.AddDays(-15);
    var query = new Query { /* ... */ };
    var cache = new QuerySourceCache
    {
        QueryId = query.Id,
        Source = "musicbrainz",
        LastCheckedAt = oldTimestamp
    };
    
    await _unitOfWork.Queries.AddAsync(query);
    await _unitOfWork.QuerySourceCaches.AddAsync(cache);
    await _unitOfWork.SaveChangesAsync();
    
    // Act
    var task = new CachePurgeMaintenanceTask(_unitOfWork, _settingsProvider, _logger);
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.True((int)result.Metrics["sourceCachesPurged"] > 0);
}

[Fact]
public async Task CachePurge_KeepsRecentEntries()
{
    // Arrange: Create recent cache entries
    var recentTimestamp = DateTime.UtcNow.AddHours(-1);
    var cache = new QuerySourceCache { LastCheckedAt = recentTimestamp };
    
    // Act & Assert
    // Recent entries should not be purged
}
```

### Cache Stats Tests

```csharp
[Fact]
public async Task CacheStats_CollectsSnapshot()
{
    // Arrange: Create test cache data
    await CreateTestCacheData();
    
    // Act
    var task = new CacheStatsMaintenanceTask(_unitOfWork, _logger);
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    
    var snapshot = await _unitOfWork.CacheStatSnapshots
        .OrderByDescending(s => s.SnapshotAt)
        .FirstOrDefaultAsync();
    
    Assert.NotNull(snapshot);
    Assert.True(snapshot.TotalQueries > 0);
}

[Fact]
public async Task CacheStats_PurgesOldStats()
{
    // Arrange: Create old stats
    var oldStat = new CacheStatSnapshot
    {
        SnapshotAt = DateTime.UtcNow.AddDays(-20)
    };
    await _unitOfWork.CacheStatSnapshots.AddAsync(oldStat);
    await _unitOfWork.SaveChangesAsync();
    
    // Act
    var task = new CacheStatsMaintenanceTask(_unitOfWork, _logger);
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    var oldStats = await _unitOfWork.CacheStatSnapshots
        .Where(s => s.SnapshotAt < DateTime.UtcNow.AddDays(-14))
        .ToListAsync();
    
    Assert.Empty(oldStats);
}
```
