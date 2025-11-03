using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
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
                .GetQueryable()
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
                .GetQueryable()
                .Where(v => v.IsActive && !string.IsNullOrWhiteSpace(v.ThumbnailPath))
                .ToListAsync(cancellationToken);
            
            var activeThumbnailPaths = new HashSet<string>(
                activeVideos.Select(v => NormalizeThumbnailPath(v.ThumbnailPath!)),
                StringComparer.OrdinalIgnoreCase);
            
            // Step 3: Get deleted videos (for grace period check)
            var gracePeriodDays = GetGracePeriodDays();
            var gracePeriodThreshold = DateTime.UtcNow.AddDays(-gracePeriodDays);
            
            var recentlyDeletedVideos = await _unitOfWork.Videos
                .GetQueryable()
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
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "ThumbnailCleanup.GracePeriodDays");
        
        if (config != null && int.TryParse(config.Value, out var days) && days >= 0)
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
