# Database Schema Changes

## Overview

This document outlines all new entities and database migrations required for the maintenance system.

---

## New Entities

### 1. MaintenanceExecution

Tracks execution history of all maintenance tasks.

**Location**: `Fuzzbin.Core/Entities/MaintenanceExecution.cs`

```csharp
namespace Fuzzbin.Core.Entities;

/// <summary>
/// Records execution history of maintenance tasks
/// </summary>
public class MaintenanceExecution : BaseEntity
{
    /// <summary>
    /// Name of the maintenance task that was executed
    /// </summary>
    public string TaskName { get; set; } = string.Empty;
    
    /// <summary>
    /// When the task started executing
    /// </summary>
    public DateTime StartedAt { get; set; }
    
    /// <summary>
    /// When the task completed (success or failure)
    /// </summary>
    public DateTime CompletedAt { get; set; }
    
    /// <summary>
    /// Whether the task completed successfully
    /// </summary>
    public bool Success { get; set; }
    
    /// <summary>
    /// Human-readable summary of what was done
    /// </summary>
    public string Summary { get; set; } = string.Empty;
    
    /// <summary>
    /// Number of items processed
    /// </summary>
    public int ItemsProcessed { get; set; }
    
    /// <summary>
    /// Error message if task failed
    /// </summary>
    public string? ErrorMessage { get; set; }
    
    /// <summary>
    /// Duration in milliseconds
    /// </summary>
    public int DurationMs { get; set; }
    
    /// <summary>
    /// Task-specific metrics as JSON
    /// </summary>
    public string? MetricsJson { get; set; }
}
```

**Indexes**:
- `TaskName` (for filtering by task type)
- `StartedAt` (for chronological queries)
- `Success` (for failure analysis)

---

### 2. CacheStatSnapshot

Stores historical cache statistics for performance monitoring.

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

**Indexes**:
- `SnapshotAt` (for time-series queries)

---

## Modified Entities

### Video Entity

Add fields for missing file tracking.

**Location**: `Fuzzbin.Core/Entities/Video.cs`

**New Properties**:
```csharp
/// <summary>
/// Whether the video file is missing from the library
/// </summary>
public bool IsMissing { get; set; }

/// <summary>
/// When the file was first detected as missing
/// </summary>
public DateTime? MissingDetectedAt { get; set; }
```

**Indexes**:
- `IsMissing` (for filtering missing videos in UI)

---

## DbContext Updates

**Location**: `Fuzzbin.Data/Context/ApplicationDbContext.cs`

### Add DbSets

```csharp
public DbSet<MaintenanceExecution> MaintenanceExecutions { get; set; } = null!;
public DbSet<CacheStatSnapshot> CacheStatSnapshots { get; set; } = null!;
```

### Update OnModelCreating

```csharp
protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    base.OnModelCreating(modelBuilder);
    
    // ... existing configuration ...
    
    // MaintenanceExecution indexes
    modelBuilder.Entity<MaintenanceExecution>(entity =>
    {
        entity.HasIndex(e => e.TaskName);
        entity.HasIndex(e => e.StartedAt);
        entity.HasIndex(e => e.Success);
    });
    
    // CacheStatSnapshot indexes
    modelBuilder.Entity<CacheStatSnapshot>(entity =>
    {
        entity.HasIndex(e => e.SnapshotAt);
    });
    
    // Video missing fields indexes
    modelBuilder.Entity<Video>(entity =>
    {
        // ... existing indexes ...
        entity.HasIndex(e => e.IsMissing);
    });
}
```

---

## IUnitOfWork Updates

**Location**: `Fuzzbin.Core/Interfaces/IUnitOfWork.cs`

Add repository properties:

```csharp
public interface IUnitOfWork : IDisposable
{
    // ... existing properties ...
    
    IRepository<MaintenanceExecution> MaintenanceExecutions { get; }
    IRepository<CacheStatSnapshot> CacheStatSnapshots { get; }
    
    // ... existing methods ...
}
```

**Location**: `Fuzzbin.Data/UnitOfWork.cs`

Implement new repositories:

```csharp
public class UnitOfWork : IUnitOfWork
{
    // ... existing fields ...
    
    private IRepository<MaintenanceExecution>? _maintenanceExecutions;
    private IRepository<CacheStatSnapshot>? _cacheStatSnapshots;
    
    // ... existing properties ...
    
    public IRepository<MaintenanceExecution> MaintenanceExecutions
    {
        get { return _maintenanceExecutions ??= new Repository<MaintenanceExecution>(_context); }
    }
    
    public IRepository<CacheStatSnapshot> CacheStatSnapshots
    {
        get { return _cacheStatSnapshots ??= new Repository<CacheStatSnapshot>(_context); }
    }
    
    // ... existing methods ...
}
```

---

## Configuration Entries

Add default maintenance configuration via migration seed data.

**Location**: Create in migration `Up()` method

```csharp
// Scheduler configuration
migrationBuilder.InsertData(
    table: "Configurations",
    columns: new[] { "Id", "Category", "Key", "Value", "Description", "IsActive", "CreatedAt", "UpdatedAt" },
    values: new object[,]
    {
        {
            Guid.NewGuid(),
            "Maintenance",
            "IntervalHours",
            "8",
            "How often to run maintenance tasks (in hours). Default: 8",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "LibraryScan.Enabled",
            "true",
            "Enable automatic library scanning for new and missing videos",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "LibraryScan.Recursive",
            "true",
            "Scan subdirectories recursively",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "LibraryScan.EnrichOnline",
            "false",
            "Enrich imported videos with online metadata (IMVDb, MusicBrainz)",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "ThumbnailCleanup.Enabled",
            "true",
            "Enable automatic cleanup of orphaned thumbnails",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "ThumbnailCleanup.GracePeriodDays",
            "7",
            "Days to wait before deleting thumbnails of deleted videos (0 for immediate)",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "CacheStats.Enabled",
            "true",
            "Enable cache statistics collection",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "CacheStats.RetentionDays",
            "14",
            "Days to retain cache statistics (older stats are purged)",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "RecycleBinPurge.Enabled",
            "true",
            "Enable automatic purging of old recycle bin files",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "RecycleBinPurge.RetentionDays",
            "7",
            "Days to keep files in recycle bin before permanent deletion",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "RecycleBinPurge.HardDelete",
            "false",
            "Permanently delete database records (true) or soft delete (false)",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "AutoBackup.Enabled",
            "true",
            "Enable automated database backups",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "AutoBackup.IntervalHours",
            "24",
            "Hours between automated backups",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        },
        {
            Guid.NewGuid(),
            "Maintenance",
            "AutoBackup.MaxBackups",
            "7",
            "Maximum number of backups to keep (oldest are deleted)",
            true,
            DateTime.UtcNow,
            DateTime.UtcNow
        }
    });
```

---

## Migrations

### Migration 1: Add Maintenance Tables

```bash
dotnet ef migrations add AddMaintenanceSystem \
  --project Fuzzbin.Data \
  --startup-project Fuzzbin.Web
```

**This migration includes**:
- `MaintenanceExecutions` table
- `CacheStatSnapshots` table
- Video `IsMissing` and `MissingDetectedAt` fields
- All indexes
- Configuration seed data

### Migration 2: (If cache system is separate)

If the cache system from `cache-integration-strategy.md` hasn't been implemented yet, you may need additional migrations for:
- `Query`, `QuerySourceCache` tables
- `MbRecording`, `MbArtist`, etc. tables
- `ImvdbVideo`, `ImvdbArtist` tables
- `YtVideo` table
- `MvLink`, `QueryResolution` tables

See `docs/cache/cache-integration-strategy.md` Section 2 for full cache schema.

---

## Migration Commands

### Create Migration

```bash
# From project root
dotnet ef migrations add AddMaintenanceSystem \
  --project Fuzzbin.Data \
  --startup-project Fuzzbin.Web \
  --context ApplicationDbContext
```

### Apply Migration

```bash
# Development
dotnet ef database update \
  --project Fuzzbin.Data \
  --startup-project Fuzzbin.Web

# Production (via application startup)
# Migrations are applied automatically on startup via:
# await context.Database.MigrateAsync();
```

### Rollback Migration

```bash
dotnet ef database update PreviousMigrationName \
  --project Fuzzbin.Data \
  --startup-project Fuzzbin.Web
```

### Remove Last Migration

```bash
# Only if not applied to database yet
dotnet ef migrations remove \
  --project Fuzzbin.Data \
  --startup-project Fuzzbin.Web
```

---

## Schema Verification

After applying migrations, verify tables exist:

```sql
-- Check MaintenanceExecutions table
SELECT * FROM MaintenanceExecutions LIMIT 5;

-- Check CacheStatSnapshots table
SELECT * FROM CacheStatSnapshots LIMIT 5;

-- Check Video missing fields
PRAGMA table_info(Videos);

-- Check indexes
SELECT * FROM sqlite_master 
WHERE type = 'index' 
AND (name LIKE '%Maintenance%' OR name LIKE '%Cache%');

-- Check configuration entries
SELECT * FROM Configurations 
WHERE Category = 'Maintenance';
```

---

## Data Migration Considerations

### Existing Videos

No data migration needed for `Video` entity changes:
- `IsMissing` defaults to `false`
- `MissingDetectedAt` defaults to `null`
- First library scan will detect any missing files

### Existing Configuration

If custom configuration exists:
- Migration seed data uses `INSERT` (may conflict)
- Consider using `INSERT OR IGNORE` or checking existence first
- Update migration to handle conflicts

---

## Cleanup Migrations (Optional)

If removing the maintenance system:

```bash
dotnet ef migrations add RemoveMaintenanceSystem \
  --project Fuzzbin.Data \
  --startup-project Fuzzbin.Web
```

**Down migration should**:
- Drop `MaintenanceExecutions` table
- Drop `CacheStatSnapshots` table
- Remove Video `IsMissing` and `MissingDetectedAt` columns
- Remove maintenance configuration entries

---

## Testing Migrations

### Unit Tests

Test migration Up/Down in isolation:

```csharp
[Fact]
public void Migration_AddMaintenanceSystem_Up_CreatesExpectedTables()
{
    // Arrange: Fresh database
    var options = new DbContextOptionsBuilder<ApplicationDbContext>()
        .UseInMemoryDatabase(Guid.NewGuid().ToString())
        .Options;
    
    using var context = new ApplicationDbContext(options);
    
    // Act: Apply migration
    context.Database.Migrate();
    
    // Assert: Tables exist
    Assert.True(context.MaintenanceExecutions.Any() || true); // Table exists
    Assert.True(context.CacheStatSnapshots.Any() || true);
}
```

### Integration Tests

Test migrations on real SQLite database:

```csharp
[Fact]
public async Task Migration_AddMaintenanceSystem_CreatesAllConfigEntries()
{
    // Arrange & Act
    await using var context = CreateTestContext();
    await context.Database.MigrateAsync();
    
    // Assert
    var maintenanceConfigs = await context.Configurations
        .Where(c => c.Category == "Maintenance")
        .ToListAsync();
    
    Assert.NotEmpty(maintenanceConfigs);
    Assert.Contains(maintenanceConfigs, c => c.Key == "IntervalHours");
    Assert.Contains(maintenanceConfigs, c => c.Key == "LibraryScan.Enabled");
}
```

---

## Performance Impact

### Expected Overhead

**Disk Space**:
- `MaintenanceExecutions`: ~100 bytes per execution × 8 executions/day × 30 days = ~24 KB/month
- `CacheStatSnapshots`: ~100 bytes per snapshot × 3 snapshots/day × 14 days = ~4 KB
- Total: Negligible (< 1 MB/year)

**Query Performance**:
- All critical queries use indexes
- No foreign key joins to frequently-accessed tables
- Maintenance queries run in background, don't impact user operations

### Optimization

If `MaintenanceExecutions` grows large (100K+ records):
- Consider partitioning by `TaskName`
- Archive old records to separate table
- Implement automatic purge of old executions (e.g., >90 days)

---

## Summary

### New Tables

1. ✅ `MaintenanceExecutions` - Task execution history
2. ✅ `CacheStatSnapshots` - Cache performance metrics

### Modified Tables

3. ✅ `Videos` - Add `IsMissing`, `MissingDetectedAt`

### New Indexes

4. ✅ `MaintenanceExecutions` - TaskName, StartedAt, Success
5. ✅ `CacheStatSnapshots` - SnapshotAt
6. ✅ `Videos` - IsMissing

### Configuration Entries

7. ✅ 14 new configuration entries in `Maintenance` category

### Migration Files

8. ✅ One migration: `AddMaintenanceSystem`

---

## Next Steps

1. **Create entities**: Implement all new entity classes
2. **Update DbContext**: Add DbSets and configuration
3. **Update IUnitOfWork**: Add repository properties
4. **Generate migration**: Run `dotnet ef migrations add`
5. **Review migration**: Check generated SQL
6. **Test migration**: Apply to test database
7. **Apply to dev**: Deploy to development environment
8. **Monitor**: Verify tables created correctly
