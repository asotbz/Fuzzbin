using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.BackgroundJobs;

/// <summary>
/// Executes metadata refresh background jobs (refactored to use BaseJobExecutor).
/// </summary>
public class MetadataRefreshJobExecutor : BaseJobExecutor
{
    private readonly IMetadataService _metadataService;

    public MetadataRefreshJobExecutor(
        IMetadataService metadataService,
        IUnitOfWork unitOfWork,
        IJobProgressNotifier notifier,
        ILogger<MetadataRefreshJobExecutor> logger)
        : base(unitOfWork, notifier, logger)
    {
        _metadataService = metadataService;
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
            _logger.LogInformation("Starting metadata refresh for {Count} videos (Job {JobId})", videoIds.Length, job.Id);

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
                        await _metadataService.EnrichVideoMetadataAsync(video, true, ct);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to refresh metadata for video {VideoId}", videoId);
                    job.FailedItems++;
                }

                job.ProcessedItems = i + 1;
                if ((i + 1) % 10 == 0 || i == videoIds.Length - 1)
                {
                    await UpdateProgressAsync(job, $"Processed {job.ProcessedItems}/{job.TotalItems} videos", ct);
                }
            }

            var summary = $"Completed: {job.ProcessedItems - job.FailedItems}/{job.TotalItems} successful, {job.FailedItems} failed";
            _logger.LogInformation("Metadata refresh job {JobId} completed: {Summary}", job.Id, summary);
            await CompleteAsync(job, summary, ct);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Metadata refresh job {JobId} failed", job.Id);
            job.FailedItems = Math.Max(job.FailedItems, 1);
            // Let processor mark Failed & serialize final structured result.
            throw;
        }
    }
}