# Recycle Bin and Backup Maintenance Tasks

## Overview

Two maintenance tasks handle long-term storage management: purging old recycle bin files and creating automated backups.

---

## Task 1: Recycle Bin Purge

Permanently deletes files from the recycle bin that have exceeded their retention period.

**Task Name**: `RecycleBinPurge`  
**Default Schedule**: Every maintenance run (8 hours)  
**Default Status**: Enabled  
**Default Retention**: 7 days

### Functionality

#### 1. Identify Expired Files

Based on `RecycleBin.DeletedAt` timestamp:
- Query all recycle bin entries
- Check against configured retention period
- Select files for permanent deletion

#### 2. Permanent Deletion

For each expired file:
- Delete physical file from disk
- Update database entry:
  - Set `IsActive = false` (soft delete)
  - OR permanently delete record (configurable)
- Log deletion for audit trail

#### 3. Statistics

Track:
- Files evaluated
- Files permanently deleted
- Disk space reclaimed
- Deletion errors

### Implementation

**Location**: `Fuzzbin.Services/Maintenance/RecycleBinPurgeMaintenanceTask.cs`

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

namespace Fuzzbin.Services.Maintenance;

/// <summary>
/// Purges expired files from the recycle bin
/// </summary>
public class RecycleBinPurgeMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<RecycleBinPurgeMaintenanceTask> _logger;
    
    public string TaskName => "RecycleBinPurge";
    public string Description => "Permanently delete expired recycle bin files";
    
    public bool IsEnabled
    {
        get
        {
            var config = _unitOfWork.Configurations
                .FirstOrDefault(c => c.Category == "Maintenance" 
                    && c.Key == "RecycleBinPurge.Enabled");
            return config?.Value != "false"; // Enabled by default
        }
    }
    
    public RecycleBinPurgeMaintenanceTask(
        IUnitOfWork unitOfWork,
        ILogger<RecycleBinPurgeMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        var metrics = new Dictionary<string, object>();
        
        try
        {
            var retentionDays = GetRetentionDays();
            var expirationThreshold = DateTime.UtcNow.AddDays(-retentionDays);
            
            _logger.LogInformation(
                "Starting recycle bin purge for files older than {Threshold} (Retention: {Days} days)",
                expirationThreshold, retentionDays);
            
            // Get expired recycle bin entries
            var expiredItems = await _unitOfWork.RecycleBins
                .Where(rb => rb.IsActive && rb.DeletedAt < expirationThreshold)
                .ToListAsync(cancellationToken);
            
            metrics["itemsEvaluated"] = expiredItems.Count;
            
            if (expiredItems.Count == 0)
            {
                _logger.LogInformation("No expired recycle bin items found");
                return new MaintenanceTaskResult
                {
                    Success = true,
                    Summary = "No expired items to purge",
                    ItemsProcessed = 0,
                    Duration = stopwatch.Elapsed,
                    Metrics = metrics
                };
            }
            
            var deletedCount = 0;
            var errorCount = 0;
            long bytesReclaimed = 0;
            
            foreach (var item in expiredItems)
            {
                if (cancellationToken.IsCancellationRequested)
                    break;
                
                try
                {
                    // Delete physical file
                    if (!string.IsNullOrWhiteSpace(item.RecycleBinPath) && 
                        File.Exists(item.RecycleBinPath))
                    {
                        var fileInfo = new FileInfo(item.RecycleBinPath);
                        var fileSize = fileInfo.Length;
                        
                        File.Delete(item.RecycleBinPath);
                        bytesReclaimed += fileSize;
                        
                        _logger.LogInformation(
                            "Permanently deleted: {Path} ({Size} bytes, deleted {Days} days ago)",
                            item.RecycleBinPath,
                            fileSize,
                            (DateTime.UtcNow - item.DeletedAt).Days);
                    }
                    
                    // Update or remove database entry
                    if (GetHardDeleteOption())
                    {
                        _unitOfWork.RecycleBins.Remove(item);
                    }
                    else
                    {
                        item.IsActive = false;
                        item.Notes = $"Purged by maintenance on {DateTime.UtcNow:g}";
                    }
                    
                    deletedCount++;
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, 
                        "Failed to purge recycle bin item: {Path}",
                        item.RecycleBinPath);
                    errorCount++;
                }
            }
            
            await _unitOfWork.SaveChangesAsync();
            
            stopwatch.Stop();
            
            metrics["filesDeleted"] = deletedCount;
            metrics["errors"] = errorCount;
            metrics["bytesReclaimed"] = bytesReclaimed;
            metrics["mbReclaimed"] = Math.Round(bytesReclaimed / 1024.0 / 1024.0, 2);
            
            var summary = $"Purged {deletedCount} files from recycle bin " +
                         $"(reclaimed {metrics["mbReclaimed"]} MB), {errorCount} errors";
            
            _logger.LogInformation(summary);
            
            return new MaintenanceTaskResult
            {
                Success = errorCount == 0,
                Summary = summary,
                ItemsProcessed = expiredItems.Count,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during recycle bin purge");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
    }
    
    private int GetRetentionDays()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "RecycleBinPurge.RetentionDays");
        
        if (int.TryParse(config?.Value, out var days) && days > 0)
        {
            return days;
        }
        
        return 7; // Default: 7 days
    }
    
    private bool GetHardDeleteOption()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "RecycleBinPurge.HardDelete");
        
        return config?.Value == "true"; // Default: false (soft delete)
    }
}
```

### Configuration

```csharp
Category: "Maintenance"
Key: "RecycleBinPurge.Enabled"
Value: "true"
Description: "Enable automatic purging of old recycle bin files"

Category: "Maintenance"
Key: "RecycleBinPurge.RetentionDays"
Value: "7"
Description: "Days to keep files in recycle bin before permanent deletion"

Category: "Maintenance"
Key: "RecycleBinPurge.HardDelete"
Value: "false"
Description: "Permanently delete database records (true) or soft delete (false)"
```

---

## Task 2: Auto Backup

Creates automated database backups on a configurable interval.

**Task Name**: `AutoBackup`  
**Default Schedule**: Independent (default: every 24 hours)  
**Default Status**: Enabled

### Functionality

#### 1. Check Backup Schedule

- Track last backup timestamp
- Compare against configured interval
- Skip if backup too recent

#### 2. Create Backup

- Use existing `IBackupService`
- Create timestamped backup file
- Store in configured backup directory

#### 3. Backup Rotation

- Keep last N backups (configurable)
- Delete oldest backups beyond limit
- Free disk space

#### 4. Statistics

Track:
- Backup created successfully
- Backup file size
- Old backups purged
- Duration

### Implementation

**Location**: `Fuzzbin.Services/Maintenance/AutoBackupMaintenanceTask.cs`

```csharp
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.Maintenance;

/// <summary>
/// Creates automated database backups on a configurable schedule
/// </summary>
public class AutoBackupMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IBackupService _backupService;
    private readonly IConfigurationPathService _configPathService;
    private readonly ILogger<AutoBackupMaintenanceTask> _logger;
    
    public string TaskName => "AutoBackup";
    public string Description => "Create automated database backup";
    
    public bool IsEnabled
    {
        get
        {
            var config = _unitOfWork.Configurations
                .FirstOrDefault(c => c.Category == "Maintenance" 
                    && c.Key == "AutoBackup.Enabled");
            return config?.Value != "false"; // Enabled by default
        }
    }
    
    public AutoBackupMaintenanceTask(
        IUnitOfWork unitOfWork,
        IBackupService backupService,
        IConfigurationPathService configPathService,
        ILogger<AutoBackupMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _backupService = backupService;
        _configPathService = configPathService;
        _logger = logger;
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        var metrics = new Dictionary<string, object>();
        
        try
        {
            // Check if backup is due
            var intervalHours = GetBackupIntervalHours();
            var lastBackup = await GetLastBackupTimestampAsync();
            var nextBackupDue = lastBackup.AddHours(intervalHours);
            
            if (DateTime.UtcNow < nextBackupDue)
            {
                var timeUntilNext = nextBackupDue - DateTime.UtcNow;
                _logger.LogInformation(
                    "Backup not due yet. Next backup in {Hours:F1} hours",
                    timeUntilNext.TotalHours);
                
                return new MaintenanceTaskResult
                {
                    Success = true,
                    Summary = $"Backup not due (next in {timeUntilNext.TotalHours:F1}h)",
                    ItemsProcessed = 0,
                    Duration = stopwatch.Elapsed
                };
            }
            
            _logger.LogInformation("Creating automated backup");
            
            // Create backup
            var backupResult = await _backupService.CreateBackupAsync(cancellationToken);
            
            metrics["backupSizeBytes"] = backupResult.FileSize;
            metrics["backupSizeMb"] = Math.Round(backupResult.FileSize / 1024.0 / 1024.0, 2);
            metrics["backupPath"] = backupResult.FilePath;
            
            // Record backup timestamp
            await RecordBackupTimestampAsync(DateTime.UtcNow);
            
            // Rotate old backups
            var purgedCount = await RotateBackupsAsync();
            metrics["oldBackupsPurged"] = purgedCount;
            
            stopwatch.Stop();
            
            var summary = $"Backup created: {metrics["backupSizeMb"]} MB, " +
                         $"purged {purgedCount} old backups";
            
            _logger.LogInformation(summary);
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = summary,
                ItemsProcessed = 1,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during automated backup");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
    }
    
    private int GetBackupIntervalHours()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "AutoBackup.IntervalHours");
        
        if (int.TryParse(config?.Value, out var hours) && hours > 0)
        {
            return hours;
        }
        
        return 24; // Default: 24 hours
    }
    
    private async Task<DateTime> GetLastBackupTimestampAsync()
    {
        var config = await _unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Category == "Maintenance" 
                && c.Key == "AutoBackup.LastRun");
        
        if (config != null && DateTime.TryParse(config.Value, out var timestamp))
        {
            return timestamp;
        }
        
        return DateTime.MinValue; // Force immediate backup
    }
    
    private async Task RecordBackupTimestampAsync(DateTime timestamp)
    {
        var config = await _unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Category == "Maintenance" 
                && c.Key == "AutoBackup.LastRun");
        
        if (config == null)
        {
            config = new Configuration
            {
                Category = "Maintenance",
                Key = "AutoBackup.LastRun",
                Description = "Timestamp of last automated backup"
            };
            await _unitOfWork.Configurations.AddAsync(config);
        }
        
        config.Value = timestamp.ToString("O"); // ISO 8601 format
        await _unitOfWork.SaveChangesAsync();
    }
    
    private async Task<int> RotateBackupsAsync()
    {
        var maxBackups = GetMaxBackupsToKeep();
        var backupDirectory = _configPathService.GetBackupDirectory();
        
        if (!Directory.Exists(backupDirectory))
        {
            return 0;
        }
        
        // Get all backup files sorted by creation time (newest first)
        var backupFiles = Directory.GetFiles(backupDirectory, "fuzzbin-backup-*.zip")
            .Select(f => new FileInfo(f))
            .OrderByDescending(f => f.CreationTimeUtc)
            .ToList();
        
        // Keep the newest N backups, delete the rest
        var filesToDelete = backupFiles.Skip(maxBackups).ToList();
        
        foreach (var file in filesToDelete)
        {
            try
            {
                file.Delete();
                _logger.LogInformation("Deleted old backup: {FileName}", file.Name);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to delete old backup: {FileName}", file.Name);
            }
        }
        
        return filesToDelete.Count;
    }
    
    private int GetMaxBackupsToKeep()
    {
        var config = _unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "AutoBackup.MaxBackups");
        
        if (int.TryParse(config?.Value, out var max) && max > 0)
        {
            return max;
        }
        
        return 7; // Default: Keep 7 backups
    }
}
```

### Configuration

```csharp
Category: "Maintenance"
Key: "AutoBackup.Enabled"
Value: "true"
Description: "Enable automated database backups"

Category: "Maintenance"
Key: "AutoBackup.IntervalHours"
Value: "24"
Description: "Hours between automated backups"

Category: "Maintenance"
Key: "AutoBackup.MaxBackups"
Value: "7"
Description: "Maximum number of backups to keep (oldest are deleted)"

// Internal state tracking (managed by task)
Category: "Maintenance"
Key: "AutoBackup.LastRun"
Value: "2025-11-03T14:30:00Z"
Description: "Timestamp of last automated backup"
```

---

## Integration with Existing Services

### RecycleBinService

The maintenance task complements the existing `RecycleBinService`:
- `RecycleBinService`: Moves files to recycle bin
- `RecycleBinPurgeMaintenanceTask`: Permanently deletes expired files

**No changes needed** to `RecycleBinService`.

### BackupService

The maintenance task uses the existing `BackupService`:
- `BackupService`: Creates backups (manual or scheduled)
- `AutoBackupMaintenanceTask`: Automates backup creation and rotation

**No changes needed** to `BackupService`.

---

## UI Integration

### Settings Page

Add recycle bin and backup configuration:

```razor
<MudExpansionPanel Text="Recycle Bin" Icon="@Icons.Material.Filled.RestoreFromTrash">
    <MudSwitch @bind-Checked="_recycleBinPurgeEnabled"
               Label="Enable automatic purge"
               Color="Color.Primary" />
    
    <MudNumericField @bind-Value="_recycleBinRetentionDays"
                     Label="Retention period (days)"
                     Min="1"
                     Max="30"
                     HelperText="Files older than this are permanently deleted" />
    
    <MudSwitch @bind-Checked="_recycleBinHardDelete"
               Label="Hard delete database records"
               Color="Color.Warning"
               HelperText="Permanently remove records instead of soft delete" />
    
    <MudButton Variant="Variant.Outlined"
               StartIcon="@Icons.Material.Filled.Delete"
               Color="Color.Warning"
               OnClick="PurgeRecycleBinNow">
        Purge Now
    </MudButton>
</MudExpansionPanel>

<MudExpansionPanel Text="Auto Backup" Icon="@Icons.Material.Filled.Backup">
    <MudSwitch @bind-Checked="_autoBackupEnabled"
               Label="Enable automated backups"
               Color="Color.Primary" />
    
    <MudNumericField @bind-Value="_backupIntervalHours"
                     Label="Backup interval (hours)"
                     Min="1"
                     Max="168"
                     HelperText="How often to create backups" />
    
    <MudNumericField @bind-Value="_maxBackupsToKeep"
                     Label="Backups to keep"
                     Min="1"
                     Max="30"
                     HelperText="Maximum number of backup files to retain" />
    
    <MudText Typo="Typo.caption" Class="mt-2">
        Last backup: @_lastBackupTime?.ToString("g") ?? "Never"
    </MudText>
    
    <MudButton Variant="Variant.Outlined"
               StartIcon="@Icons.Material.Filled.Backup"
               OnClick="CreateBackupNow">
        Create Backup Now
    </MudButton>
</MudExpansionPanel>
```

### Manual Trigger Handlers

```csharp
private async Task PurgeRecycleBinNow()
{
    var confirmed = await DialogService.ShowMessageBox(
        "Confirm Purge",
        "This will permanently delete all expired files from the recycle bin. Continue?",
        yesText: "Purge", cancelText: "Cancel");
    
    if (confirmed != true) return;
    
    try
    {
        _isLoading = true;
        
        var response = await Http.PostAsync("/api/maintenance/run-task/RecycleBinPurge", null);
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<MaintenanceTaskResult>();
            Snackbar.Add(result?.Summary ?? "Purge completed", Severity.Success);
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

private async Task CreateBackupNow()
{
    try
    {
        _isLoading = true;
        
        var response = await Http.PostAsync("/api/maintenance/run-task/AutoBackup", null);
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<MaintenanceTaskResult>();
            Snackbar.Add(result?.Summary ?? "Backup created", Severity.Success);
            await LoadLastBackupTime();
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

---

## Testing

### Recycle Bin Purge Tests

```csharp
[Fact]
public async Task RecycleBinPurge_DeletesExpiredFiles()
{
    // Arrange: Create expired recycle bin item
    var oldFile = CreateTestRecycleBinFile(daysOld: 10);
    await _unitOfWork.RecycleBins.AddAsync(oldFile);
    await _unitOfWork.SaveChangesAsync();
    
    // Act
    var task = new RecycleBinPurgeMaintenanceTask(_unitOfWork, _logger);
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.False(File.Exists(oldFile.RecycleBinPath));
}

[Fact]
public async Task RecycleBinPurge_KeepsRecentFiles()
{
    // Arrange: Create recent recycle bin item
    var recentFile = CreateTestRecycleBinFile(daysOld: 3);
    
    // Act & Assert
    // File should not be deleted
}

[Fact]
public async Task RecycleBinPurge_SoftDeletesByDefault()
{
    // Arrange
    var expiredFile = CreateTestRecycleBinFile(daysOld: 10);
    
    // Act
    var task = new RecycleBinPurgeMaintenanceTask(_unitOfWork, _logger);
    await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    var item = await _unitOfWork.RecycleBins.GetByIdAsync(expiredFile.Id);
    Assert.NotNull(item);
    Assert.False(item.IsActive);
}
```

### Auto Backup Tests

```csharp
[Fact]
public async Task AutoBackup_CreatesBackupWhenDue()
{
    // Arrange: Set last backup to 25 hours ago
    await SetLastBackupTimestamp(DateTime.UtcNow.AddHours(-25));
    
    // Act
    var task = new AutoBackupMaintenanceTask(
        _unitOfWork, _backupService, _configPathService, _logger);
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.Equal(1, result.ItemsProcessed);
    Assert.True(result.Metrics.ContainsKey("backupSizeMb"));
}

[Fact]
public async Task AutoBackup_SkipsWhenNotDue()
{
    // Arrange: Set last backup to 1 hour ago
    await SetLastBackupTimestamp(DateTime.UtcNow.AddHours(-1));
    
    // Act
    var task = new AutoBackupMaintenanceTask(
        _unitOfWork, _backupService, _configPathService, _logger);
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.Equal(0, result.ItemsProcessed);
    Assert.Contains("not due", result.Summary);
}

[Fact]
public async Task AutoBackup_RotatesOldBackups()
{
    // Arrange: Create 10 old backups (max is 7)
    CreateTestBackupFiles(count: 10);
    
    // Act
    var task = new AutoBackupMaintenanceTask(
        _unitOfWork, _backupService, _configPathService, _logger);
    await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    var backupFiles = GetBackupFiles();
    Assert.True(backupFiles.Count <= 7);
    Assert.Equal(3, (int)task.Metrics["oldBackupsPurged"]);
}
```

---

## Error Handling

### Recycle Bin Purge Errors

1. **File in use**: Log warning, skip file, retry on next run
2. **Permission denied**: Log error, continue with other files
3. **File not found**: Update database entry, consider successful deletion

### Backup Errors

1. **Disk full**: Fail gracefully, notify in logs
2. **Backup service failure**: Don't update last run timestamp, retry on next run
3. **Rotation failure**: Don't fail backup, log warning

---

## Performance Considerations

### Recycle Bin Purge

- Batch deletions for large recycle bins (100-500 at a time)
- Use parallel file deletion with caution (filesystem dependent)
- Log progress for long-running operations

### Auto Backup

- Backup creation can be slow for large databases
- Consider running during off-peak hours
- Monitor disk space before creating backup
- Compression settings balance size vs. time

---

## Optional Enhancements

### Email Notifications

Send email when:
- Backup succeeds/fails
- Recycle bin purge completes
- Disk space is low

### Cloud Backup

Upload backups to cloud storage:
- S3, Azure Blob, Google Cloud Storage
- Automatic offsite backup
- Disaster recovery support

### Backup Verification

Verify backup integrity:
- Test restore after creation
- Checksum validation
- Periodic restore tests
