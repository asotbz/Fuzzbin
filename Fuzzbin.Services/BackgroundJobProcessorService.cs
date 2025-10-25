using System;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using System.Linq;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
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
        var progressNotifier = scope.ServiceProvider.GetRequiredService<IJobProgressNotifier>();
        var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();

        // Get pending jobs (query directly to avoid loading all jobs)
        var pendingJobs = await dbContext.BackgroundJobs
            .Where(j => j.Status == BackgroundJobStatus.Pending && j.IsActive)
            .OrderBy(j => j.CreatedAt)
            .ToListAsync(cancellationToken);

        // Enforce singleton per job type: keep the earliest Pending per Type (CreatedAt then Id), cancel the rest.
        var grouped = pendingJobs
            .GroupBy(j => j.Type)
            .Select(g => g
                .OrderBy(j => j.CreatedAt)
                .ThenBy(j => j.Id)
                .ToList())
            .ToList();

        var duplicates = grouped
            .SelectMany(g => g.Skip(1))
            .ToList();

        if (duplicates.Count > 0)
        {
            foreach (var dup in duplicates)
            {
                dup.Status = BackgroundJobStatus.Cancelled;
                dup.CompletedAt = DateTime.UtcNow;
                dup.ErrorMessage = "Cancelled (duplicate pending singleton job of same type)";
            }

            await unitOfWork.SaveChangesAsync();

            foreach (var dup in duplicates)
            {
                await progressNotifier.NotifyJobCancelledAsync(dup.Id, cancellationToken);
            }
        }

        pendingJobs = grouped
            .Select(g => g.First())
            .OrderBy(j => j.CreatedAt)
            .ThenBy(j => j.Id)
            .ToList();

        foreach (var job in pendingJobs)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            try
            {
                _logger.LogInformation("Starting background job {JobId} of type {JobType}", job.Id, job.Type);

                // If cancellation was requested before starting, mark cancelled and skip
                if (job.CancellationRequested)
                {
                    job.Status = BackgroundJobStatus.Cancelled;
                    job.CompletedAt = DateTime.UtcNow;

                    // Serialize structured result
                    job.ResultJson = JsonSerializer.Serialize(
                        BackgroundJobResult.Create(job, "Cancelled before start"));

                    await unitOfWork.SaveChangesAsync();
                    _logger.LogInformation("Background job {JobId} cancelled prior to execution", job.Id);
                    await progressNotifier.NotifyJobCancelledAsync(job.Id, cancellationToken);
                    continue;
                }

                // Update job status to running
                job.Status = BackgroundJobStatus.Running;
                job.StartedAt = DateTime.UtcNow;
                await unitOfWork.SaveChangesAsync();
                await progressNotifier.NotifyJobStartedAsync(job.Id, job.Type, cancellationToken);

                // Execute the job based on type
                await ExecuteJobAsync(scope.ServiceProvider, job, cancellationToken);

                // After execution decide final status (cancelled vs completed)
                if (job.CancellationRequested)
                {
                    job.Status = BackgroundJobStatus.Cancelled;
                    job.CompletedAt = DateTime.UtcNow;
                    if (job.Progress >= 100) job.Progress = 99; // ensure not reported as fully completed

                    job.ResultJson = JsonSerializer.Serialize(
                        BackgroundJobResult.Create(job, "Cancelled during execution"));

                    await unitOfWork.SaveChangesAsync();
                    _logger.LogInformation("Background job {JobId} cancelled during execution", job.Id);
                    await progressNotifier.NotifyJobCancelledAsync(job.Id, cancellationToken);
                }
                else
                {
                    job.Status = BackgroundJobStatus.Completed;
                    job.CompletedAt = DateTime.UtcNow;
                    job.Progress = 100;

                    job.ResultJson = JsonSerializer.Serialize(
                        BackgroundJobResult.Create(job, "Completed successfully"));

                    await unitOfWork.SaveChangesAsync();
                    _logger.LogInformation("Background job {JobId} completed successfully", job.Id);
                    await progressNotifier.NotifyJobCompletedAsync(job.Id, null, cancellationToken);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Background job {JobId} failed", job.Id);

                job.Status = BackgroundJobStatus.Failed;
                job.ErrorMessage = ex.Message;
                job.CompletedAt = DateTime.UtcNow;

                job.ResultJson = JsonSerializer.Serialize(
                    BackgroundJobResult.Create(job, $"Failed: {ex.Message}"));

                await unitOfWork.SaveChangesAsync();
                await progressNotifier.NotifyJobFailedAsync(job.Id, ex.Message, cancellationToken);
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

    /// <summary>
    /// Single processing iteration (no delay loop) exposed for unit tests.
    /// Allows tests to enqueue jobs and invoke processing deterministically.
    /// </summary>
    public Task ProcessOnceForTestsAsync(CancellationToken cancellationToken = default) =>
        ProcessPendingJobsAsync(cancellationToken);
}
