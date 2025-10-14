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
/// Executes file organization background jobs (refactored to BaseJobExecutor).
/// </summary>
public class FileOrganizationJobExecutor : BaseJobExecutor
{
    private readonly IFileOrganizationService _organizationService;

    public FileOrganizationJobExecutor(
        IFileOrganizationService organizationService,
        IUnitOfWork unitOfWork,
        IJobProgressNotifier notifier,
        ILogger<FileOrganizationJobExecutor> logger)
        : base(unitOfWork, notifier, logger)
    {
        _organizationService = organizationService;
    }

    public async Task ExecuteAsync(BackgroundJob job, CancellationToken ct)
    {
        try
        {
            var videoIds = JsonSerializer.Deserialize<Guid[]>(job.ParametersJson ?? "[]") ?? Array.Empty<Guid>();

            if (videoIds.Length == 0)
            {
                var allVideos = await _unitOfWork.Videos.GetAllAsync();
                videoIds = allVideos.Select(v => v.Id).ToArray();
            }

            await InitializeJobAsync(job, BackgroundJobType.OrganizeFiles, videoIds.Length, ct);
            _logger.LogInformation("Starting file organization for {Count} videos (Job {JobId})", videoIds.Length, job.Id);

            for (int i = 0; i < videoIds.Length; i++)
            {
                if (job.CancellationRequested)
                {
                    _logger.LogInformation("File organization job {JobId} cancellation detected mid-loop", job.Id);
                    return;
                }

                var videoId = videoIds[i];
                try
                {
                    // TODO: Implement per-video organization when service API supports it.
                    _logger.LogDebug("Organizing (stub) for video {VideoId} ({Current}/{Total})", videoId, i + 1, videoIds.Length);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to organize files for video {VideoId}", videoId);
                    job.FailedItems++;
                }

                job.ProcessedItems = i + 1;
                if ((i + 1) % 10 == 0 || i == videoIds.Length - 1)
                {
                    await UpdateProgressAsync(job, $"Processed {job.ProcessedItems}/{job.TotalItems} videos", ct);
                }
            }

            var summary = $"Completed: {job.ProcessedItems - job.FailedItems}/{job.TotalItems} successful, {job.FailedItems} failed";
            _logger.LogInformation("File organization job {JobId} completed: {Summary}", job.Id, summary);
            await CompleteAsync(job, summary, ct);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "File organization job {JobId} failed", job.Id);
            job.FailedItems = Math.Max(job.FailedItems, 1);
            throw;
        }
    }
}