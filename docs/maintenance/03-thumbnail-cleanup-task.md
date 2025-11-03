# Thumbnail Cleanup Maintenance Task

## Overview

The Thumbnail Cleanup task identifies and removes orphaned thumbnails—thumbnail files that no longer correspond to any video in the library. This prevents disk space waste from accumulating over time as videos are deleted or moved.

**Task Name**: `ThumbnailCleanup`  
**Default Schedule**: Every maintenance run (8 hours)  
**Default Status**: Enabled

---

## Functionality

### 1. Orphaned Thumbnail Detection

A thumbnail is considered orphaned if:
- The thumbnail file exists on disk
- No active `Video` entity references this thumbnail path
- OR the referenced video is marked as deleted (`IsActive = false`)

### 2. Cleanup Strategy

**Safe Cleanup** (default):
- Only delete thumbnails for videos deleted > 7 days ago
- Provides grace period for potential restores

**Aggressive Cleanup** (optional):
- Immediately delete orphaned thumbnails
- Useful for one-time cleanup or when confident in video deletions

### 3. Statistics Collection

Track and report:
- Total thumbnails scanned
- Orphaned thumbnails found
- Thumbnails deleted
- Disk space reclaimed (bytes)
- Cleanup duration

---

## Implementation

**Location**: `Fuzzbin.Services/Maintenance/ThumbnailCleanupMaintenanceTask.cs`

```csharp
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Services.Maintenance;

/// <summary>
/// Cleans up orphaned thumbnail files
/// </summary>
public class ThumbnailCleanupMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IConfiguration _configuration;
    private readonly ILogger<ThumbnailCleanupMaintenanceTask> _logger;
    private readonly string _thumbnailDirectory;
    
    public string TaskName => "ThumbnailCleanup";
    public string Description => "Remove orphaned thumbnail files";
    
    public bool IsEnabled
    {
        get
        {
            var config = _unitOfWork.Configurations
                .FirstOrDefault(c => c.Category == "Maintenance" 
                    && c.Key == "ThumbnailCleanup.Enabled");
            return config?.Value != "false"; // Enabled by default
        }
    }
    
    public ThumbnailCleanupMaintenanceTask(
        IUnitOfWork unitOfWork,
        IConfiguration configuration,
        ILogger<ThumbnailCleanupMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _configuration = configuration;
        _logger = logger;
        
        var webRootPath = configuration["WebRootPath"] 
            ?? Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "wwwroot");
        _thumbnailDirectory = Path.Combine(webRootPath, "thumbnails");
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        var metrics = new Dictionary<string, object>();
        
        try
        {
            if (!Directory.Exists(_thumbnailDirectory))
            {
                return new MaintenanceTaskResult
                {
                    Success = true,
                    Summary = "Thumbnail directory does not exist, nothing to clean",
                    ItemsProcessed = 0,
                    Duration = stopwatch.Elapsed
                };
            }
            
            _logger.LogInformation("Starting thumbnail cleanup in: {ThumbnailDirectory}", 
                _thumbnailDirectory);
            
            // Step 1: Get all thumbnail files
            var thumbnailFiles = Directory.GetFiles(_thumbnailDirectory, "*.*", SearchOption.AllDirectories)
                .Where(f => IsImageFile(f))
                .ToList();
            
            metrics["totalThumbnails"] = thumbnailFiles.Count;
            _logger.LogInformation("Found {ThumbnailCount} thumbnail files", thumbnailFiles.Count);
            
            // Step 2: Get all active videos with thumbnails
            var activeVideos = await _unitOfWork.Videos
                .Where(v => v.IsActive && !string.IsNullOrWhiteSpace(v.ThumbnailPath))
                .ToListAsync(cancellationToken);
            
            var activeThumbnailPaths = new HashSet<string>(
                activeVideos.Select(v => NormalizeThumbnailPath(v.ThumbnailPath!)),
                StringComparer.OrdinalIgnoreCase);
            
            // Step 3: Get deleted videos (for grace period check)
            var gracePeriodDays = GetGracePeriodDays();
            var gracePeriodThreshold = DateTime.UtcNow.AddDays(-gracePeriodDays);
            
            var recentlyDeletedVideos = await _unitOfWork.Videos
                .Where(v => !v.IsActive 
                    && !string.IsNullOrWhiteSpace(v.ThumbnailPath)
                    && v.UpdatedAt > gracePeriodThreshold)
                .ToListAsync(cancellationToken);
            
            var gracePeriodThumbnails = new HashSet<string>(
                recentlyDeletedVideos.Select(v => NormalizeThumbnailPath(v.ThumbnailPath!)),
                StringComparer.OrdinalIgnoreCase);
            
            // Step 4: Identify and delete orphaned thumbnails
            var orphanedFiles = new List<string>();
            long bytesReclaimed = 0;
            
            foreach (var thumbnailFile in thumbnailFiles)
            {
                if (cancellationToken.IsCancellationRequested)
                    break;
                
                var normalizedPath = NormalizeThumbnailPath(thumbnailFile);
                
                // Keep if referenced by active video
                if (activeThumbnailPaths.Contains(normalizedPath))
                    continue;
                
                // Keep if in grace period
                if (gracePeriodThumbnails.Contains(normalizedPath))
                {
                    _logger.LogDebug("Keeping thumbnail in grace period: {Path}", normalizedPath);
                    continue;
                }
                
                // This is an orphaned thumbnail
                orphanedFiles.Add(thumbnailFile);
                
                try
                {
                    var fileInfo = new FileInfo(thumbnailFile);
                    var fileSize = fileInfo.Length;
                    
                    File.Delete(thumbnailFile);
                    bytesReclaimed += fileSize;
                    
                    _logger.LogDebug("Deleted orphaned thumbnail: {Path} ({Size} bytes)",
                        normalizedPath, fileSize);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Failed to delete orphaned thumbnail: {Path}", 
                        thumbnailFile);
                }
            }
            
            // Step 5: Clean up empty directories
            CleanupEmptyDirectories(_thumbnailDirectory);
            
            stopwatch.Stop();
            
            metrics["orphanedThumbnails"] = orphanedFiles.Count;
            metrics["bytesReclaimed"] = bytesReclaimed;
            metrics["mbReclaimed"] = Math.Round(bytesReclaimed / 1024.0 / 1024.0, 2);
            
            var summary = $"Scanned {thumbnailFiles.Count} thumbnails, " +
                         $"removed {orphanedFiles.Count} orphaned files, " +
                         $"reclaimed {metrics["mbReclaimed"]} MB";
            
            _logger.LogInformation(summary);
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = summary,
                ItemsProcessed = thumbnailFiles.Count,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during thumbnail cleanup");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
    }
    
    private bool IsImageFile(string filePath)
    {
        var extension = Path.GetExtension(filePath).ToLowerInvariant();
        return extension == ".jpg" || extension == ".jpeg" || 
               extension == ".png" || extension == ".webp";
    }
    
    private string NormalizeThumbnailPath(string path)
    {
        // Convert to absolute path if relative
        if (!Path.IsPathRooted(path))
        {
            path = Path.Combine(_thumbnailDirectory, path);
        }
        
        return Path.GetFullPath(path);
    }
    
    private int GetGracePeriodDays()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "ThumbnailCleanup.GracePeriodDays");
        
        if (int.TryParse(config?.Value, out var days) && days >= 0)
        {
            return days;
        }
        
        return 7; // Default: 7 days
    }
    
    private void CleanupEmptyDirectories(string rootDirectory)
    {
        try
        {
            var directories = Directory.GetDirectories(rootDirectory, "*", SearchOption.AllDirectories)
                .OrderByDescending(d => d.Length) // Process deepest first
                .ToList();
            
            foreach (var directory in directories)
            {
                try
                {
                    if (!Directory.EnumerateFileSystemEntries(directory).Any())
                    {
                        Directory.Delete(directory);
                        _logger.LogDebug("Removed empty directory: {Directory}", directory);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Failed to remove directory: {Directory}", directory);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error cleaning up empty directories");
        }
    }
}
```

---

## Configuration

### Configuration Keys

```csharp
// Enable/disable the task
Category: "Maintenance"
Key: "ThumbnailCleanup.Enabled"
Value: "true"
Description: "Enable automatic cleanup of orphaned thumbnails"

// Grace period for deleted videos
Category: "Maintenance"
Key: "ThumbnailCleanup.GracePeriodDays"
Value: "7"
Description: "Days to wait before deleting thumbnails of deleted videos (0 for immediate)"
```

---

## Integration with Existing Services

### ThumbnailService

The existing `ThumbnailService` generates thumbnails. This maintenance task complements it by cleaning up old ones.

**No changes needed** to `ThumbnailService`, but consider:
- Logging thumbnail creation with video ID for better tracking
- Updating thumbnail path atomically when regenerating

### Video Deletion Flow

When a video is deleted, its thumbnail is **not immediately deleted**:
1. Video is marked as `IsActive = false`
2. Thumbnail remains on disk
3. Maintenance task removes it after grace period

This allows:
- Potential video restoration
- Caching during the deletion process
- Batch cleanup for efficiency

---

## UI Integration

### Settings Page

Add thumbnail cleanup configuration:

```razor
<MudExpansionPanel Text="Thumbnail Cleanup" Icon="@Icons.Material.Filled.Image">
    <MudSwitch @bind-Checked="_thumbnailCleanupEnabled"
               Label="Enable automatic thumbnail cleanup"
               Color="Color.Primary" />
    
    <MudNumericField @bind-Value="_thumbnailGracePeriodDays"
                     Label="Grace period (days)"
                     Min="0"
                     Max="30"
                     HelperText="Wait this many days before deleting thumbnails of deleted videos" />
    
    <MudButton Variant="Variant.Outlined"
               StartIcon="@Icons.Material.Filled.CleaningServices"
               OnClick="RunThumbnailCleanup">
        Run Cleanup Now
    </MudButton>
    
    <MudText Typo="Typo.caption" Class="mt-2">
        Removes orphaned thumbnail files to free up disk space.
    </MudText>
</MudExpansionPanel>
```

### Manual Cleanup Trigger

```csharp
private async Task RunThumbnailCleanup()
{
    try
    {
        _isLoading = true;
        
        var response = await Http.PostAsync("/api/maintenance/run-task/ThumbnailCleanup", null);
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<MaintenanceTaskResult>();
            Snackbar.Add(result?.Summary ?? "Cleanup completed", Severity.Success);
        }
        else
        {
            Snackbar.Add("Cleanup failed", Severity.Error);
        }
    }
    catch (Exception ex)
    {
        Snackbar.Add($"Error: {ex.Message}", Severity.Error);
    }
    finally
    {
        _isLoading = false;
    }
}
```

### Thumbnail Manager Page

Add cleanup statistics display:

```razor
<MudCard Class="mb-4">
    <MudCardHeader>
        <CardHeaderContent>
            <MudText Typo="Typo.h6">Cleanup Statistics</MudText>
        </CardHeaderContent>
    </MudCardHeader>
    <MudCardContent>
        <MudGrid>
            <MudItem xs="12" sm="6" md="3">
                <MudText Typo="Typo.caption">Last Cleanup</MudText>
                <MudText Typo="Typo.body1">@_lastCleanup?.ToString("g")</MudText>
            </MudItem>
            <MudItem xs="12" sm="6" md="3">
                <MudText Typo="Typo.caption">Files Removed</MudText>
                <MudText Typo="Typo.body1">@_filesRemoved</MudText>
            </MudItem>
            <MudItem xs="12" sm="6" md="3">
                <MudText Typo="Typo.caption">Space Reclaimed</MudText>
                <MudText Typo="Typo.body1">@_spaceReclaimed MB</MudText>
            </MudItem>
            <MudItem xs="12" sm="6" md="3">
                <MudText Typo="Typo.caption">Total Thumbnails</MudText>
                <MudText Typo="Typo.body1">@_totalThumbnails</MudText>
            </MudItem>
        </MudGrid>
    </MudCardContent>
</MudCard>
```

---

## Testing

### Unit Tests

```csharp
[Fact]
public async Task ThumbnailCleanup_RemovesOrphanedThumbnails()
{
    // Arrange: Create orphaned thumbnail files
    var thumbnailDir = CreateTestThumbnailDirectory();
    CreateOrphanedThumbnail(thumbnailDir, "orphan1.jpg");
    CreateOrphanedThumbnail(thumbnailDir, "orphan2.jpg");
    
    var task = CreateTask(thumbnailDir);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.Equal(2, result.Metrics["orphanedThumbnails"]);
    Assert.False(File.Exists(Path.Combine(thumbnailDir, "orphan1.jpg")));
    Assert.False(File.Exists(Path.Combine(thumbnailDir, "orphan2.jpg")));
}

[Fact]
public async Task ThumbnailCleanup_KeepsActiveThumbnails()
{
    // Arrange: Active video with thumbnail
    var thumbnailDir = CreateTestThumbnailDirectory();
    var thumbnailPath = Path.Combine(thumbnailDir, "active.jpg");
    CreateThumbnailFile(thumbnailPath);
    
    var video = new Video
    {
        IsActive = true,
        ThumbnailPath = "active.jpg"
    };
    await _unitOfWork.Videos.AddAsync(video);
    
    var task = CreateTask(thumbnailDir);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.Equal(0, result.Metrics["orphanedThumbnails"]);
    Assert.True(File.Exists(thumbnailPath));
}

[Fact]
public async Task ThumbnailCleanup_RespectsGracePeriod()
{
    // Arrange: Recently deleted video
    var thumbnailDir = CreateTestThumbnailDirectory();
    var thumbnailPath = Path.Combine(thumbnailDir, "recent.jpg");
    CreateThumbnailFile(thumbnailPath);
    
    var video = new Video
    {
        IsActive = false,
        ThumbnailPath = "recent.jpg",
        UpdatedAt = DateTime.UtcNow.AddDays(-3) // Within 7-day grace period
    };
    await _unitOfWork.Videos.AddAsync(video);
    
    var task = CreateTask(thumbnailDir, gracePeriodDays: 7);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.Equal(0, result.Metrics["orphanedThumbnails"]);
    Assert.True(File.Exists(thumbnailPath)); // Should be kept
}

[Fact]
public async Task ThumbnailCleanup_DeletesAfterGracePeriod()
{
    // Arrange: Old deleted video
    var thumbnailDir = CreateTestThumbnailDirectory();
    var thumbnailPath = Path.Combine(thumbnailDir, "old.jpg");
    CreateThumbnailFile(thumbnailPath);
    
    var video = new Video
    {
        IsActive = false,
        ThumbnailPath = "old.jpg",
        UpdatedAt = DateTime.UtcNow.AddDays(-10) // Beyond 7-day grace period
    };
    await _unitOfWork.Videos.AddAsync(video);
    
    var task = CreateTask(thumbnailDir, gracePeriodDays: 7);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.Equal(1, result.Metrics["orphanedThumbnails"]);
    Assert.False(File.Exists(thumbnailPath));
}

[Fact]
public async Task ThumbnailCleanup_RemovesEmptyDirectories()
{
    // Arrange: Empty subdirectories after cleanup
    var thumbnailDir = CreateTestThumbnailDirectory();
    var subDir = Path.Combine(thumbnailDir, "artist", "album");
    Directory.CreateDirectory(subDir);
    var orphanPath = Path.Combine(subDir, "orphan.jpg");
    CreateThumbnailFile(orphanPath);
    
    var task = CreateTask(thumbnailDir);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.False(Directory.Exists(subDir)); // Empty directory removed
}
```

### Integration Tests

```csharp
[Fact]
public async Task ThumbnailCleanup_WorksWithRealThumbnailService()
{
    // Arrange: Generate real thumbnail, then delete video
    var video = await CreateTestVideoWithThumbnail();
    var thumbnailPath = video.ThumbnailPath;
    
    // Delete video
    video.IsActive = false;
    await _unitOfWork.SaveChangesAsync();
    
    // Wait past grace period (or set to 0)
    await Task.Delay(100);
    
    // Act
    var task = _serviceProvider.GetRequiredService<ThumbnailCleanupMaintenanceTask>();
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.False(File.Exists(thumbnailPath));
}
```

---

## Performance Considerations

### Large Thumbnail Directories

For thousands of thumbnails:
- Process in batches of 500-1000
- Add cancellation token checks
- Consider parallel file deletion (with caution)
- Log progress periodically

### Disk I/O Optimization

- Use `FileInfo` properties to check files without opening
- Batch database queries to minimize round trips
- Use `HashSet` for O(1) lookups

---

## Error Handling

### Common Errors

1. **File in use**: Skip and retry on next run
2. **Permission denied**: Log warning and continue
3. **Directory locked**: Skip directory cleanup, clean files only
4. **Database connection**: Fail safely, don't delete any files

### Safety Measures

- Never delete files if database query fails
- Always verify file is truly orphaned before deleting
- Log all deletions for potential recovery
- Consider backup/archive option before deletion

---

## Optional Enhancements

### Archive Instead of Delete

Instead of immediate deletion, move to archive directory:

```csharp
private void ArchiveThumbnail(string thumbnailPath)
{
    var archiveDir = Path.Combine(_thumbnailDirectory, "_archive");
    Directory.CreateDirectory(archiveDir);
    
    var archivePath = Path.Combine(archiveDir, 
        $"{DateTime.UtcNow:yyyyMMdd}_{Path.GetFileName(thumbnailPath)}");
    
    File.Move(thumbnailPath, archivePath);
}
```

### Dry Run Mode

Allow preview of what would be deleted:

```csharp
Category: "Maintenance"
Key: "ThumbnailCleanup.DryRun"
Value: "false"
Description: "Preview cleanup without deleting files"
```

### Thumbnail Health Check

Verify thumbnails are valid images:

```csharp
private bool IsThumbnailCorrupt(string path)
{
    try
    {
        using var image = Image.Load(path);
        return false;
    }
    catch
    {
        return true;
    }
}
```
