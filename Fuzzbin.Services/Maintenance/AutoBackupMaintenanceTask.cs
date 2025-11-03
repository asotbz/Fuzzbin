using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
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
                .GetQueryable()
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
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "AutoBackup.IntervalHours");
        
        if (config != null && int.TryParse(config.Value, out var hours) && hours > 0)
        {
            return hours;
        }
        
        return 24; // Default: 24 hours
    }
    
    private async Task<DateTime> GetLastBackupTimestampAsync()
    {
        var config = await _unitOfWork.Configurations
            .GetQueryable()
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
            .GetQueryable()
            .FirstOrDefaultAsync(c => c.Category == "Maintenance" 
                && c.Key == "AutoBackup.LastRun");
        
        if (config == null)
        {
            config = new Configuration
            {
                Category = "Maintenance",
                Key = "AutoBackup.LastRun",
                Description = "Timestamp of last automated backup",
                IsActive = true
            };
            await _unitOfWork.Configurations.AddAsync(config);
        }
        
        config.Value = timestamp.ToString("O"); // ISO 8601 format
        await _unitOfWork.SaveChangesAsync();
    }
    
    private Task<int> RotateBackupsAsync()
    {
        var maxBackups = GetMaxBackupsToKeep();
        var backupDirectory = _configPathService.GetBackupDirectory();
        
        if (!Directory.Exists(backupDirectory))
        {
            return Task.FromResult(0);
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
        
        return Task.FromResult(filesToDelete.Count);
    }
    
    private int GetMaxBackupsToKeep()
    {
        var config = _unitOfWork.Configurations
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "AutoBackup.MaxBackups");
        
        if (config != null && int.TryParse(config.Value, out var max) && max > 0)
        {
            return max;
        }
        
        return 7; // Default: Keep 7 backups
    }
}
