using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.BackgroundJobs;

/// <summary>
/// Executes metadata refresh background jobs
/// </summary>
public class MetadataRefreshJobExecutor
{
    private readonly IMetadataService _metadataService;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IJobProgressNotifier _progressNotifier;
    private readonly ILogger<MetadataRefreshJobExecutor> _logger;

    public MetadataRefreshJobExecutor(
        IMetadataService metadataService,
        IUnitOfWork unitOfWork,
        IJobProgressNotifier progressNotifier,
        ILogger<MetadataRefreshJobExecutor> logger)
    {
        _metadataService = metadataService;
        _unitOfWork = unitOfWork;
        _progressNotifier = progressNotifier;
        _logger = logger;
    }

    public async Task ExecuteAsync(BackgroundJob job, CancellationToken cancellationToken)
    {
        try
        {
            await _progressNotifier.NotifyJobStartedAsync(job.Id, BackgroundJobType.RefreshMetadata, cancellationToken);

            // Parse video IDs from parameters
            var videoIds = System.Text.Json.JsonSerializer.Deserialize<Guid[]>(job.ParametersJson ?? "[]") ?? Array.Empty<Guid>();

            if (videoIds.Length == 0)
            {
                // Refresh all videos in library
                var allVideos = await _unitOfWork.Videos.GetAllAsync();
                videoIds = allVideos.Select(v => v.Id).ToArray();
            }

            job.TotalItems = videoIds.Length;
            job.ProcessedItems = 0;
            job.FailedItems = 0;
            await _unitOfWork.SaveChangesAsync();

            _logger.LogInformation("Starting metadata refresh for {Count} videos", videoIds.Length);

            for (int i = 0; i < videoIds.Length; i++)
            {
                if (job.CancellationRequested)
                {
                    _logger.LogInformation("Metadata refresh job {JobId} was cancelled", job.Id);
                    await _progressNotifier.NotifyJobCancelledAsync(job.Id, cancellationToken);
                    return;
                }

                var videoId = videoIds[i];

                try
                {
                    _logger.LogDebug("Refreshing metadata for video {VideoId} ({Current}/{Total})", videoId, i + 1, videoIds.Length);

                    var video = await _unitOfWork.Videos.GetByIdAsync(videoId);
                    if (video != null)
                    {
                        await _metadataService.EnrichVideoMetadataAsync(video, true, cancellationToken);
                    }

                    job.ProcessedItems++;
                    job.Progress = (int)((job.ProcessedItems / (double)job.TotalItems) * 100);
                    job.StatusMessage = $"Processed {job.ProcessedItems}/{job.TotalItems} videos";
                    await _unitOfWork.SaveChangesAsync();

                    await _progressNotifier.NotifyJobProgressAsync(job.Id, job.Progress, job.StatusMessage, cancellationToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to refresh metadata for video {VideoId}", videoId);
                    job.FailedItems++;
                    await _unitOfWork.SaveChangesAsync();
                }
            }

            var resultSummary = $"Completed: {job.ProcessedItems - job.FailedItems}/{job.TotalItems} successful, {job.FailedItems} failed";
            _logger.LogInformation("Metadata refresh job {JobId} completed: {Summary}", job.Id, resultSummary);

            await _progressNotifier.NotifyJobCompletedAsync(job.Id, resultSummary, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Metadata refresh job {JobId} failed with exception", job.Id);
            await _progressNotifier.NotifyJobFailedAsync(job.Id, ex.Message, cancellationToken);
            throw;
        }
    }
}