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
                .GetQueryable()
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
                .GetQueryable()
                .Where(s => s.SnapshotAt < threshold)
                .ToListAsync(cancellationToken);
            
            foreach (var stat in oldStats)
            {
                await _unitOfWork.CacheStatSnapshots.DeleteAsync(stat);
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
        var totalQueries = await _unitOfWork.Queries.GetQueryable().CountAsync(ct);
        
        var mbSourceCaches = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(qsc => qsc.Source == "musicbrainz")
            .CountAsync(ct);
        
        var imvdbSourceCaches = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(qsc => qsc.Source == "imvdb")
            .CountAsync(ct);
        
        var ytSourceCaches = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(qsc => qsc.Source == "youtube")
            .CountAsync(ct);
        
        var totalResolutions = await _unitOfWork.QueryResolutions.GetQueryable().CountAsync(ct);
        
        var mbCandidates = await _unitOfWork.MbRecordingCandidates.GetQueryable().CountAsync(ct);
        var imvdbCandidates = await _unitOfWork.ImvdbVideoCandidates.GetQueryable().CountAsync(ct);
        var ytCandidates = await _unitOfWork.YtVideoCandidates.GetQueryable().CountAsync(ct);
        
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
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "CacheStats.RetentionDays");
        
        if (config != null && int.TryParse(config.Value, out var days) && days > 0)
        {
            return days;
        }
        
        return 14; // Default: 14 days
    }
}
