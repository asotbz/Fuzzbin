using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.BackgroundJobs;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services;

/// <summary>
/// Background service that processes queued background jobs and performs cleanup
/// </summary>
public class BackgroundJobProcessorService : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<BackgroundJobProcessorService> _logger;
    private readonly TimeSpan _pollingInterval = TimeSpan.FromSeconds(5);
    private readonly TimeSpan _cleanupInterval = TimeSpan.FromHours(1);
    private DateTime _lastCleanup = DateTime.UtcNow;

    public BackgroundJobProcessorService(
        IServiceScopeFactory scopeFactory,
        ILogger<BackgroundJobProcessorService> logger)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Background job processor service started");

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await ProcessPendingJobsAsync(stoppingToken);
                await PerformCleanupIfNeededAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in background job processor");
            }

            await Task.Delay(_pollingInterval, stoppingToken);
        }

        _logger.LogInformation("Background job processor service stopped");
    }

    private async Task ProcessPendingJobsAsync(CancellationToken cancellationToken)
    {
        using var scope = _scopeFactory.CreateScope();
        var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
        var backgroundJobService = scope.ServiceProvider.GetRequiredService<IBackgroundJobService>();

        // Get pending jobs
        var allJobs = await unitOfWork.BackgroundJobs.GetAllAsync();
        var pendingJobs = allJobs.Where(j => j.Status == BackgroundJobStatus.Pending && j.IsActive).ToList();

        foreach (var job in pendingJobs)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            try
            {
                _logger.LogInformation("Starting background job {JobId} of type {JobType}", job.Id, job.Type);

                // Update job status to running
                job.Status = BackgroundJobStatus.Running;
                job.StartedAt = DateTime.UtcNow;
                await unitOfWork.SaveChangesAsync();

                // Execute the job based on type
                await ExecuteJobAsync(scope.ServiceProvider, job, cancellationToken);

                // Mark as completed
                job.Status = BackgroundJobStatus.Completed;
                job.CompletedAt = DateTime.UtcNow;
                job.Progress = 100;
                await unitOfWork.SaveChangesAsync();

                _logger.LogInformation("Background job {JobId} completed successfully", job.Id);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Background job {JobId} failed", job.Id);

                job.Status = BackgroundJobStatus.Failed;
                job.ErrorMessage = ex.Message;
                job.CompletedAt = DateTime.UtcNow;
                await unitOfWork.SaveChangesAsync();
            }
        }
    }

    private async Task ExecuteJobAsync(IServiceProvider serviceProvider, BackgroundJob job, CancellationToken cancellationToken)
    {
        switch (job.Type)
        {
            case BackgroundJobType.RefreshMetadata:
                var metadataExecutor = ActivatorUtilities.CreateInstance<MetadataRefreshJobExecutor>(serviceProvider);
                await metadataExecutor.ExecuteAsync(job, cancellationToken);
                break;

            case BackgroundJobType.OrganizeFiles:
                var organizationExecutor = ActivatorUtilities.CreateInstance<FileOrganizationJobExecutor>(serviceProvider);
                await organizationExecutor.ExecuteAsync(job, cancellationToken);
                break;

            case BackgroundJobType.VerifySourceUrls:
                var verificationExecutor = ActivatorUtilities.CreateInstance<SourceVerificationJobExecutor>(serviceProvider);
                // Parse video IDs from job parameters
                var videoIds = System.Text.Json.JsonSerializer.Deserialize<List<Guid>>(job.ParametersJson ?? "[]") ?? new List<Guid>();
                await verificationExecutor.ExecuteAsync(job.Id, videoIds, cancellationToken);
                break;

            default:
                _logger.LogWarning("Unknown job type: {JobType}", job.Type);
                throw new InvalidOperationException($"Unknown job type: {job.Type}");
        }
    }

    private async Task PerformCleanupIfNeededAsync(CancellationToken cancellationToken)
    {
        if (DateTime.UtcNow - _lastCleanup < _cleanupInterval)
            return;

        try
        {
            using var scope = _scopeFactory.CreateScope();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

            _logger.LogInformation("Performing background job cleanup");

            // Delete completed jobs older than 7 days
            var cutoffDate = DateTime.UtcNow.AddDays(-7);
            var allJobs = await unitOfWork.BackgroundJobs.GetAllAsync();
            var oldJobs = allJobs.Where(j =>
                (j.Status == BackgroundJobStatus.Completed || j.Status == BackgroundJobStatus.Failed || j.Status == BackgroundJobStatus.Cancelled) &&
                j.CompletedAt.HasValue &&
                j.CompletedAt.Value < cutoffDate).ToList();

            if (oldJobs.Any())
            {
                foreach (var job in oldJobs)
                {
                    await unitOfWork.BackgroundJobs.DeleteAsync(job);
                }

                await unitOfWork.SaveChangesAsync();
                _logger.LogInformation("Cleaned up {Count} old background jobs", oldJobs.Count());
            }

            _lastCleanup = DateTime.UtcNow;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error performing background job cleanup");
        }
    }
}