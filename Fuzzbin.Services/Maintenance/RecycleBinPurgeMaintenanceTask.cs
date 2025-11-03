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
                .GetQueryable()
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
                .GetQueryable()
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
                        await _unitOfWork.RecycleBins.DeleteAsync(item);
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
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "RecycleBinPurge.RetentionDays");
        
        if (config != null && int.TryParse(config.Value, out var days) && days > 0)
        {
            return days;
        }
        
        return 7; // Default: 7 days
    }
    
    private bool GetHardDeleteOption()
    {
        var config = _unitOfWork.Configurations
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "RecycleBinPurge.HardDelete");
        
        return config?.Value == "true"; // Default: false (soft delete)
    }
}
