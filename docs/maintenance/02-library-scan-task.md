# Library Scan Maintenance Task

## Overview

The Library Scan task automatically discovers video files in the library directory, imports new videos that aren't in the database, and marks videos as "missing" when their files are no longer present.

**Task Name**: `LibraryScan`  
**Default Schedule**: Every maintenance run (8 hours)  
**Default Status**: Enabled

---

## Functionality

### 1. File Discovery

Scan the configured library root directory for video files:
- Recursively traverse all subdirectories
- Match files by extension: `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.flv`, `.wmv`
- Ignore hidden files and directories (starting with `.`)
- Respect system ignore patterns (e.g., `.fuzzbin-ignore` file)

### 2. New File Import

For each discovered file not in the database:
- Extract metadata using existing `MetadataService`
- Calculate file hash for duplicate detection
- Create `Video` entity with metadata
- Optionally enrich with online metadata (configurable)
- Add to database

### 3. Missing File Detection

For each video in the database:
- Check if file exists at expected path
- If missing and not already marked:
  - Set `IsMissing = true`
  - Set `MissingDetectedAt = DateTime.UtcNow`
  - Keep all metadata intact
- If found and was marked missing:
  - Clear `IsMissing = false`
  - Clear `MissingDetectedAt = null`
  - Update file stats (size, modified date)

### 4. Statistics Collection

Track and report:
- Total files scanned
- New videos imported
- Videos marked as missing
- Videos restored (no longer missing)
- Files skipped (duplicates, errors)
- Scan duration

---

## Implementation

**Location**: `Fuzzbin.Services/Maintenance/LibraryScanMaintenanceTask.cs`

```csharp
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.Maintenance;

/// <summary>
/// Scans the library directory for new files and missing videos
/// </summary>
public class LibraryScanMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILibraryPathManager _libraryPathManager;
    private readonly IMetadataService _metadataService;
    private readonly ILogger<LibraryScanMaintenanceTask> _logger;
    
    private static readonly string[] VideoExtensions = 
    {
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv"
    };
    
    public string TaskName => "LibraryScan";
    public string Description => "Scan library for new and missing videos";
    
    public bool IsEnabled
    {
        get
        {
            var config = _unitOfWork.Configurations
                .FirstOrDefault(c => c.Category == "Maintenance" 
                    && c.Key == "LibraryScan.Enabled");
            return config?.Value != "false"; // Enabled by default
        }
    }
    
    public LibraryScanMaintenanceTask(
        IUnitOfWork unitOfWork,
        ILibraryPathManager libraryPathManager,
        IMetadataService metadataService,
        ILogger<LibraryScanMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _libraryPathManager = libraryPathManager;
        _metadataService = metadataService;
        _logger = logger;
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        var metrics = new Dictionary<string, object>();
        
        try
        {
            var libraryRoot = await _libraryPathManager.GetLibraryRootAsync(cancellationToken);
            
            if (string.IsNullOrWhiteSpace(libraryRoot) || !Directory.Exists(libraryRoot))
            {
                return new MaintenanceTaskResult
                {
                    Success = false,
                    ErrorMessage = $"Library root not found or not configured: {libraryRoot}",
                    Duration = stopwatch.Elapsed
                };
            }
            
            _logger.LogInformation("Starting library scan in: {LibraryRoot}", libraryRoot);
            
            // Step 1: Discover all video files
            var discoveredFiles = DiscoverVideoFiles(libraryRoot, cancellationToken);
            metrics["filesScanned"] = discoveredFiles.Count;
            
            // Step 2: Get all existing videos from database
            var existingVideos = await _unitOfWork.Videos
                .Where(v => v.IsActive)
                .ToListAsync(cancellationToken);
            
            // Step 3: Import new files
            var importResult = await ImportNewFilesAsync(
                discoveredFiles, 
                existingVideos, 
                libraryRoot,
                cancellationToken);
            
            metrics["imported"] = importResult.ImportedCount;
            metrics["skipped"] = importResult.SkippedCount;
            metrics["importErrors"] = importResult.ErrorCount;
            
            // Step 4: Mark missing videos
            var missingResult = await UpdateMissingStatusAsync(
                discoveredFiles, 
                existingVideos,
                libraryRoot,
                cancellationToken);
            
            metrics["markedMissing"] = missingResult.MarkedMissingCount;
            metrics["restored"] = missingResult.RestoredCount;
            
            stopwatch.Stop();
            
            var summary = $"Scanned {discoveredFiles.Count} files: " +
                         $"{importResult.ImportedCount} imported, " +
                         $"{missingResult.MarkedMissingCount} marked missing, " +
                         $"{missingResult.RestoredCount} restored, " +
                         $"{importResult.ErrorCount} errors";
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = summary,
                ItemsProcessed = discoveredFiles.Count,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during library scan");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
    }
    
    private List<string> DiscoverVideoFiles(string rootPath, CancellationToken cancellationToken)
    {
        var files = new List<string>();
        
        try
        {
            var searchOption = GetRecursiveSearchOption();
            
            foreach (var extension in VideoExtensions)
            {
                if (cancellationToken.IsCancellationRequested)
                    break;
                
                try
                {
                    var matchingFiles = Directory.GetFiles(rootPath, $"*{extension}", searchOption)
                        .Where(f => !IsIgnoredFile(f));
                    
                    files.AddRange(matchingFiles);
                }
                catch (UnauthorizedAccessException ex)
                {
                    _logger.LogWarning(ex, "Access denied to directory during scan");
                }
            }
            
            _logger.LogInformation("Discovered {FileCount} video files", files.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error discovering video files in: {RootPath}", rootPath);
        }
        
        return files;
    }
    
    private bool IsIgnoredFile(string filePath)
    {
        // Ignore hidden files/directories
        var fileName = Path.GetFileName(filePath);
        if (fileName.StartsWith("."))
            return true;
        
        // Ignore files in hidden directories
        var directoryPath = Path.GetDirectoryName(filePath);
        if (directoryPath?.Split(Path.DirectorySeparatorChar).Any(d => d.StartsWith(".")) == true)
            return true;
        
        return false;
    }
    
    private SearchOption GetRecursiveSearchOption()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "LibraryScan.Recursive");
        
        return config?.Value == "false" 
            ? SearchOption.TopDirectoryOnly 
            : SearchOption.AllDirectories;
    }
    
    private async Task<ImportResult> ImportNewFilesAsync(
        List<string> discoveredFiles,
        List<Video> existingVideos,
        string libraryRoot,
        CancellationToken cancellationToken)
    {
        var result = new ImportResult();
        var enrichOnline = GetEnrichOnlineMetadataOption();
        
        // Build index of existing files for fast lookup
        var existingPaths = new HashSet<string>(
            existingVideos
                .Where(v => !string.IsNullOrWhiteSpace(v.FilePath))
                .Select(v => Path.Combine(libraryRoot, v.FilePath!)),
            StringComparer.OrdinalIgnoreCase);
        
        // Find new files
        var newFiles = discoveredFiles
            .Where(f => !existingPaths.Contains(f))
            .ToList();
        
        _logger.LogInformation("Found {NewFileCount} new files to import", newFiles.Count);
        
        foreach (var filePath in newFiles)
        {
            if (cancellationToken.IsCancellationRequested)
                break;
            
            try
            {
                var relativePath = Path.GetRelativePath(libraryRoot, filePath);
                
                _logger.LogDebug("Importing new file: {RelativePath}", relativePath);
                
                // Extract metadata
                var video = await _metadataService.ExtractMetadataAsync(
                    filePath, 
                    cancellationToken);
                
                video.FilePath = relativePath;
                
                // Optionally enrich with online metadata
                if (enrichOnline && 
                    !string.IsNullOrWhiteSpace(video.Artist) && 
                    !string.IsNullOrWhiteSpace(video.Title))
                {
                    try
                    {
                        video = await _metadataService.EnrichVideoMetadataAsync(
                            video,
                            fetchOnlineMetadata: true,
                            cancellationToken: cancellationToken);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, 
                            "Failed to enrich online metadata for: {RelativePath}", 
                            relativePath);
                        // Continue with local metadata only
                    }
                }
                
                await _unitOfWork.Videos.AddAsync(video);
                await _unitOfWork.SaveChangesAsync();
                
                result.ImportedCount++;
                
                _logger.LogInformation("Imported: {Artist} - {Title}", 
                    video.Artist, video.Title);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to import file: {FilePath}", filePath);
                result.ErrorCount++;
            }
        }
        
        return result;
    }
    
    private bool GetEnrichOnlineMetadataOption()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "LibraryScan.EnrichOnline");
        
        return config?.Value == "true"; // Disabled by default (can be slow)
    }
    
    private async Task<MissingResult> UpdateMissingStatusAsync(
        List<string> discoveredFiles,
        List<Video> existingVideos,
        string libraryRoot,
        CancellationToken cancellationToken)
    {
        var result = new MissingResult();
        
        // Build set of discovered files for fast lookup
        var discoveredSet = new HashSet<string>(discoveredFiles, StringComparer.OrdinalIgnoreCase);
        
        foreach (var video in existingVideos)
        {
            if (cancellationToken.IsCancellationRequested)
                break;
            
            if (string.IsNullOrWhiteSpace(video.FilePath))
                continue;
            
            var fullPath = Path.Combine(libraryRoot, video.FilePath);
            var fileExists = discoveredSet.Contains(fullPath);
            
            // Mark as missing
            if (!fileExists && !video.IsMissing)
            {
                video.IsMissing = true;
                video.MissingDetectedAt = DateTime.UtcNow;
                result.MarkedMissingCount++;
                
                _logger.LogWarning("Video file missing: {FilePath} ({Artist} - {Title})",
                    video.FilePath, video.Artist, video.Title);
            }
            // Restore (file returned)
            else if (fileExists && video.IsMissing)
            {
                video.IsMissing = false;
                video.MissingDetectedAt = null;
                result.RestoredCount++;
                
                _logger.LogInformation("Video file restored: {FilePath} ({Artist} - {Title})",
                    video.FilePath, video.Artist, video.Title);
            }
        }
        
        if (result.MarkedMissingCount > 0 || result.RestoredCount > 0)
        {
            await _unitOfWork.SaveChangesAsync();
        }
        
        return result;
    }
    
    private class ImportResult
    {
        public int ImportedCount { get; set; }
        public int SkippedCount { get; set; }
        public int ErrorCount { get; set; }
    }
    
    private class MissingResult
    {
        public int MarkedMissingCount { get; set; }
        public int RestoredCount { get; set; }
    }
}
```

---

## Configuration

### Required Configuration Keys

```csharp
// Enable/disable the task
Category: "Maintenance"
Key: "LibraryScan.Enabled"
Value: "true"
Description: "Enable automatic library scanning for new and missing videos"

// Recursive directory scan
Category: "Maintenance"
Key: "LibraryScan.Recursive"
Value: "true"
Description: "Scan subdirectories recursively"

// Online metadata enrichment (slower)
Category: "Maintenance"
Key: "LibraryScan.EnrichOnline"
Value: "false"
Description: "Enrich imported videos with online metadata (IMVDb, MusicBrainz)"
```

---

## Database Schema Changes

Add missing-related fields to `Video` entity:

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

**Migration**:
```bash
dotnet ef migrations add AddVideoMissingFields --project Fuzzbin.Data --startup-project Fuzzbin.Web
```

---

## UI Integration

### Videos Page

**Display missing videos** with visual indicator:

```razor
@if (video.IsMissing)
{
    <MudChip Color="Color.Warning" Size="Size.Small" Icon="@Icons.Material.Filled.Warning">
        Missing
    </MudChip>
}
```

**Filter missing videos**:
```csharp
var missingVideos = await _unitOfWork.Videos
    .Where(v => v.IsMissing)
    .ToListAsync();
```

**Allow management of missing videos**:
- Delete from library (keeps in database but deletes entry)
- Re-scan to check if file returned
- Edit metadata to update file path

### Settings Page

Add configuration UI for library scan options:

```razor
<MudExpansionPanel Text="Library Scanning" Icon="@Icons.Material.Filled.FolderOpen">
    <MudSwitch @bind-Checked="_libraryScanEnabled"
               Label="Enable automatic library scanning"
               Color="Color.Primary" />
    
    <MudSwitch @bind-Checked="_libraryScanRecursive"
               Label="Scan subdirectories recursively"
               Color="Color.Primary" />
    
    <MudSwitch @bind-Checked="_enrichOnlineMetadata"
               Label="Enrich with online metadata (slower)"
               Color="Color.Secondary" />
    
    <MudText Typo="Typo.caption" Class="mt-2">
        Automatically imports new videos and marks missing files during maintenance runs.
    </MudText>
</MudExpansionPanel>
```

---

## Testing

### Unit Tests

```csharp
[Fact]
public async Task LibraryScan_ImportsNewFiles()
{
    // Arrange: Create test library with new video files
    var libraryPath = CreateTestLibrary(newFileCount: 5);
    var task = CreateTask(libraryPath);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.Equal(5, result.Metrics["imported"]);
}

[Fact]
public async Task LibraryScan_MarksMissingVideos()
{
    // Arrange: Video in database but file deleted
    var video = CreateTestVideo("test.mp4");
    await _unitOfWork.Videos.AddAsync(video);
    DeleteFile(video.FilePath);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    var updatedVideo = await _unitOfWork.Videos.GetByIdAsync(video.Id);
    Assert.True(updatedVideo.IsMissing);
    Assert.NotNull(updatedVideo.MissingDetectedAt);
}

[Fact]
public async Task LibraryScan_RestoresMissingVideos()
{
    // Arrange: Video marked missing but file restored
    var video = CreateTestVideo("test.mp4");
    video.IsMissing = true;
    video.MissingDetectedAt = DateTime.UtcNow.AddDays(-1);
    await _unitOfWork.Videos.AddAsync(video);
    RestoreFile(video.FilePath);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    var updatedVideo = await _unitOfWork.Videos.GetByIdAsync(video.Id);
    Assert.False(updatedVideo.IsMissing);
    Assert.Null(updatedVideo.MissingDetectedAt);
}
```

---

## Performance Considerations

### Large Libraries

For libraries with thousands of files:
- Consider batch processing (process in chunks of 100)
- Add progress reporting via `IJobProgressNotifier`
- Implement timeout safeguards
- Consider making this a background job instead of synchronous maintenance task

### Optimization Tips

1. **Use file system caching**: Store last scan results to detect changes
2. **Skip unchanged directories**: Track directory modification times
3. **Parallel processing**: Import multiple files concurrently
4. **Incremental scans**: Only scan recently modified directories

---

## Error Handling

### Common Errors

1. **Access Denied**: Log warning and continue with accessible directories
2. **Corrupt Files**: Log error and skip file, don't fail entire scan
3. **Metadata Extraction Failure**: Import with minimal metadata
4. **Database Errors**: Retry once, then log and continue

### Recovery

- Task failures don't affect other maintenance tasks
- Next scheduled run will retry the scan
- Manual trigger available via API for immediate retry
