using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services;

namespace Fuzzbin.Services.BackgroundJobs;

/// <summary>
/// Executes metadata refresh background jobs (refactored to use BaseJobExecutor).
/// </summary>
public class MetadataRefreshJobExecutor : BaseJobExecutor
{
    private readonly IMetadataService _metadataService;
    private readonly IActivityLogService _activityLogService;

    public MetadataRefreshJobExecutor(
        IMetadataService metadataService,
        IUnitOfWork unitOfWork,
        IJobProgressNotifier notifier,
        ILogger<MetadataRefreshJobExecutor> logger,
        IActivityLogService activityLogService)
        : base(unitOfWork, notifier, logger)
    {
        _metadataService = metadataService;
        _activityLogService = activityLogService;
    }

    public async Task ExecuteAsync(BackgroundJob job, CancellationToken ct)
    {
        try
        {
            // Parse provided IDs (optional)
            var videoIds = JsonSerializer.Deserialize<Guid[]>(job.ParametersJson ?? "[]") ?? Array.Empty<Guid>();

            if (videoIds.Length == 0)
            {
                var allVideos = await _unitOfWork.Videos.GetAllAsync();
                videoIds = allVideos.Select(v => v.Id).ToArray();
            }

            await InitializeJobAsync(job, BackgroundJobType.RefreshMetadata, videoIds.Length, ct);
            await LogActivityAsync(() => _activityLogService.LogSuccessAsync(
                ActivityCategories.Video,
                ActivityActions.BulkUpdate,
                entityType: nameof(BackgroundJob),
                entityId: job.Id.ToString(),
                details: $"Started metadata refresh for {videoIds.Length} videos"));
            _logger.LogInformation("Starting metadata refresh for {Count} videos (Job {JobId})", videoIds.Length, job.Id);

            // Track videos requiring manual review
            var lowConfidenceVideoIds = new System.Collections.Generic.List<Guid>();
            var skippedCount = 0;
            const double ConfidenceThreshold = 0.9;

            for (int i = 0; i < videoIds.Length; i++)
            {
                if (job.CancellationRequested)
                {
                    _logger.LogInformation("Metadata refresh job {JobId} cancellation detected mid-loop", job.Id);
                    return;
                }

                var videoId = videoIds[i];
                try
                {
                    var video = await _unitOfWork.Videos.GetByIdAsync(videoId);
                    if (video != null)
                    {
                        // Use enrichment method that returns result with confidence score
                        var result = await _metadataService.EnrichVideoMetadataWithResultAsync(video, true, ct);
                        
                        // Check if manual review is required (low confidence match)
                        if (result.RequiresManualReview || result.MatchConfidence < ConfidenceThreshold)
                        {
                            lowConfidenceVideoIds.Add(videoId);
                            skippedCount++;
                            _logger.LogInformation(
                                "Video {VideoId} requires manual review (confidence: {Confidence:F2})",
                                videoId, result.MatchConfidence);
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to refresh metadata for video {VideoId}", videoId);
                    await LogActivityAsync(() => _activityLogService.LogErrorAsync(
                        ActivityCategories.Video,
                        ActivityActions.Update,
                        ex.Message,
                        entityType: nameof(Video),
                        entityId: videoId.ToString(),
                        entityName: null,
                        details: "Metadata refresh failed"));
                    job.FailedItems++;
                }

                job.ProcessedItems = i + 1;
                if ((i + 1) % 10 == 0 || i == videoIds.Length - 1)
                {
                    var progress = skippedCount > 0
                        ? $"Processed {job.ProcessedItems}/{job.TotalItems} videos ({skippedCount} need review)"
                        : $"Processed {job.ProcessedItems}/{job.TotalItems} videos";
                    await UpdateProgressAsync(job, progress, ct);
                }
            }

            // Store low-confidence video IDs in result for later review
            var resultData = new MetadataRefreshResult
            {
                TotalProcessed = job.ProcessedItems,
                Successful = job.ProcessedItems - job.FailedItems - skippedCount,
                Failed = job.FailedItems,
                RequiringReview = skippedCount,
                LowConfidenceVideoIds = lowConfidenceVideoIds
            };
            
            job.ResultJson = JsonSerializer.Serialize(resultData);

            var summary = skippedCount > 0
                ? $"Completed: {resultData.Successful}/{job.TotalItems} successful, {job.FailedItems} failed, {skippedCount} need manual review"
                : $"Completed: {resultData.Successful}/{job.TotalItems} successful, {job.FailedItems} failed";
            
            _logger.LogInformation("Metadata refresh job {JobId} completed: {Summary}", job.Id, summary);
            await CompleteAsync(job, summary, ct);
            await LogActivityAsync(() => _activityLogService.LogSuccessAsync(
                ActivityCategories.Video,
                ActivityActions.BulkUpdate,
                entityType: nameof(BackgroundJob),
                entityId: job.Id.ToString(),
                details: summary));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Metadata refresh job {JobId} failed", job.Id);
            job.FailedItems = Math.Max(job.FailedItems, 1);
            // Let processor mark Failed & serialize final structured result.
            throw;
        }
    }

    private async Task LogActivityAsync(Func<Task> logOperation)
    {
        try
        {
            await logOperation();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to write activity log entry for metadata refresh job");
        }
    }
}

/// <summary>
/// Result data structure for metadata refresh jobs
/// </summary>
public class MetadataRefreshResult
{
    public int TotalProcessed { get; set; }
    public int Successful { get; set; }
    public int Failed { get; set; }
    public int RequiringReview { get; set; }
    public System.Collections.Generic.List<Guid> LowConfidenceVideoIds { get; set; } = new();
}
