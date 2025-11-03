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
            .GetQueryable()
            .Where(qsc => qsc.Source == "musicbrainz" && qsc.LastCheckedAt < threshold)
            .Select(qsc => qsc.QueryId)
            .Distinct()
            .ToListAsync(ct);
        
        if (!expiredQueries.Any())
            return 0;
        
        var candidates = await _unitOfWork.MbRecordingCandidates
            .GetQueryable()
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            await _unitOfWork.MbRecordingCandidates.DeleteAsync(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} MusicBrainz candidates", candidates.Count);
        return candidates.Count;
    }
    
    private async Task<int> PurgeImvdbCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(qsc => qsc.Source == "imvdb" && qsc.LastCheckedAt < threshold)
            .Select(qsc => qsc.QueryId)
            .Distinct()
            .ToListAsync(ct);
        
        if (!expiredQueries.Any())
            return 0;
        
        var candidates = await _unitOfWork.ImvdbVideoCandidates
            .GetQueryable()
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            await _unitOfWork.ImvdbVideoCandidates.DeleteAsync(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} IMVDb candidates", candidates.Count);
        return candidates.Count;
    }
    
    private async Task<int> PurgeYtCandidatesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredQueries = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(qsc => qsc.Source == "youtube" && qsc.LastCheckedAt < threshold)
            .Select(qsc => qsc.QueryId)
            .Distinct()
            .ToListAsync(ct);
        
        if (!expiredQueries.Any())
            return 0;
        
        var candidates = await _unitOfWork.YtVideoCandidates
            .GetQueryable()
            .Where(c => expiredQueries.Contains(c.QueryId))
            .ToListAsync(ct);
        
        foreach (var candidate in candidates)
        {
            await _unitOfWork.YtVideoCandidates.DeleteAsync(candidate);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} YouTube candidates", candidates.Count);
        return candidates.Count;
    }
    
    private async Task<int> PurgeQuerySourceCachesAsync(DateTime threshold, CancellationToken ct)
    {
        var expiredCaches = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(qsc => qsc.LastCheckedAt < threshold)
            .ToListAsync(ct);
        
        if (!expiredCaches.Any())
            return 0;
        
        foreach (var cache in expiredCaches)
        {
            await _unitOfWork.QuerySourceCaches.DeleteAsync(cache);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} QuerySourceCache entries", expiredCaches.Count);
        return expiredCaches.Count;
    }
    
    private async Task<int> PurgeOrphanedQueriesAsync(CancellationToken ct)
    {
        // Queries with no active source caches and no resolution
        var orphanedQueries = await _unitOfWork.Queries
            .GetQueryable()
            .Where(q => !q.SourceCaches.Any() && q.Resolution == null)
            .ToListAsync(ct);
        
        if (!orphanedQueries.Any())
            return 0;
        
        foreach (var query in orphanedQueries)
        {
            await _unitOfWork.Queries.DeleteAsync(query);
        }
        
        await _unitOfWork.SaveChangesAsync();
        
        _logger.LogInformation("Purged {Count} orphaned queries", orphanedQueries.Count);
        return orphanedQueries.Count;
    }
    
    private async Task<int> PurgeOrphanedEntitiesAsync(CancellationToken ct)
    {
        var totalPurged = 0;
        
        // Get all MvLink IDs for each type
        var mbRecordingIdsWithLinks = await _unitOfWork.MvLinks
            .GetQueryable()
            .Where(l => l.MbRecordingId != null)
            .Select(l => l.MbRecordingId!.Value)
            .Distinct()
            .ToListAsync(ct);
        
        var imvdbVideoIdsWithLinks = await _unitOfWork.MvLinks
            .GetQueryable()
            .Where(l => l.ImvdbVideoId != null)
            .Select(l => l.ImvdbVideoId!.Value)
            .Distinct()
            .ToListAsync(ct);
        
        var ytVideoIdsWithLinks = await _unitOfWork.MvLinks
            .GetQueryable()
            .Where(l => !string.IsNullOrEmpty(l.YtVideoId))
            .Select(l => l.YtVideoId!)
            .Distinct()
            .ToListAsync(ct);
        
        // MusicBrainz recordings with no candidates and no links
        var orphanedRecordings = await _unitOfWork.MbRecordings
            .GetQueryable()
            .Where(r => !r.Candidates.Any() && !mbRecordingIdsWithLinks.Contains(r.Id))
            .ToListAsync(ct);
        
        foreach (var recording in orphanedRecordings)
        {
            await _unitOfWork.MbRecordings.DeleteAsync(recording);
        }
        totalPurged += orphanedRecordings.Count;
        
        // IMVDb videos with no candidates and no links
        var orphanedImvdbVideos = await _unitOfWork.ImvdbVideos
            .GetQueryable()
            .Where(v => !v.Candidates.Any() && !imvdbVideoIdsWithLinks.Contains(v.Id))
            .ToListAsync(ct);
        
        foreach (var video in orphanedImvdbVideos)
        {
            await _unitOfWork.ImvdbVideos.DeleteAsync(video);
        }
        totalPurged += orphanedImvdbVideos.Count;
        
        // YouTube videos with no candidates and no links
        var orphanedYtVideos = await _unitOfWork.YtVideos
            .GetQueryable()
            .Where(v => !v.Candidates.Any() && !ytVideoIdsWithLinks.Contains(v.VideoId))
            .ToListAsync(ct);
        
        foreach (var video in orphanedYtVideos)
        {
            await _unitOfWork.YtVideos.DeleteAsync(video);
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
