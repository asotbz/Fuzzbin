using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Services
{
    public class BackgroundJobService : IBackgroundJobService
    {
        private readonly IUnitOfWork _unitOfWork;
        private readonly ILogger<BackgroundJobService> _logger;

        public BackgroundJobService(
            IUnitOfWork unitOfWork,
            ILogger<BackgroundJobService> logger)
        {
            _unitOfWork = unitOfWork;
            _logger = logger;
        }

        public async Task<BackgroundJob> CreateJobAsync(BackgroundJobType type, string? parametersJson = null, CancellationToken cancellationToken = default)
        {
            var job = new BackgroundJob
            {
                Type = type,
                Status = BackgroundJobStatus.Pending,
                ParametersJson = parametersJson,
                CreatedAt = DateTime.UtcNow
            };

            await _unitOfWork.BackgroundJobs.AddAsync(job);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogInformation("Created background job {JobId} of type {JobType}", job.Id, type);
            return job;
        }

        public async Task<BackgroundJob?> GetJobAsync(Guid jobId, CancellationToken cancellationToken = default)
        {
            return await _unitOfWork.BackgroundJobs.GetByIdAsync(jobId);
        }

        public Task<List<BackgroundJob>> GetJobsAsync(BackgroundJobStatus? status = null, int? limit = null, CancellationToken cancellationToken = default)
        {
            var query = _unitOfWork.BackgroundJobs.GetQueryable();

            if (status.HasValue)
            {
                query = query.Where(j => j.Status == status.Value);
            }

            query = query.OrderByDescending(j => j.CreatedAt);

            if (limit.HasValue)
            {
                query = query.Take(limit.Value);
            }

            return Task.FromResult(query.ToList());
        }

        public async Task UpdateProgressAsync(Guid jobId, int progress, string? statusMessage = null, CancellationToken cancellationToken = default)
        {
            var job = await GetJobAsync(jobId, cancellationToken);
            if (job == null)
            {
                _logger.LogWarning("Attempted to update progress for non-existent job {JobId}", jobId);
                return;
            }

            job.Progress = Math.Clamp(progress, 0, 100);
            if (statusMessage != null)
            {
                job.StatusMessage = statusMessage;
            }
            job.UpdatedAt = DateTime.UtcNow;

            await _unitOfWork.BackgroundJobs.UpdateAsync(job);
            await _unitOfWork.SaveChangesAsync();
        }

        public async Task UpdateItemCountsAsync(Guid jobId, int totalItems, int processedItems, int failedItems, CancellationToken cancellationToken = default)
        {
            var job = await GetJobAsync(jobId, cancellationToken);
            if (job == null)
            {
                _logger.LogWarning("Attempted to update item counts for non-existent job {JobId}", jobId);
                return;
            }

            job.TotalItems = totalItems;
            job.ProcessedItems = processedItems;
            job.FailedItems = failedItems;

            // Auto-calculate progress if total items > 0
            if (totalItems > 0)
            {
                job.Progress = (int)((processedItems / (double)totalItems) * 100);
            }

            job.UpdatedAt = DateTime.UtcNow;

            await _unitOfWork.BackgroundJobs.UpdateAsync(job);
            await _unitOfWork.SaveChangesAsync();
        }

        public async Task StartJobAsync(Guid jobId, CancellationToken cancellationToken = default)
        {
            var job = await GetJobAsync(jobId, cancellationToken);
            if (job == null)
            {
                _logger.LogWarning("Attempted to start non-existent job {JobId}", jobId);
                return;
            }

            job.Status = BackgroundJobStatus.Running;
            job.StartedAt = DateTime.UtcNow;
            job.UpdatedAt = DateTime.UtcNow;

            await _unitOfWork.BackgroundJobs.UpdateAsync(job);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogInformation("Started background job {JobId}", jobId);
        }

        public async Task CompleteJobAsync(Guid jobId, string? resultJson = null, CancellationToken cancellationToken = default)
        {
            var job = await GetJobAsync(jobId, cancellationToken);
            if (job == null)
            {
                _logger.LogWarning("Attempted to complete non-existent job {JobId}", jobId);
                return;
            }

            job.Status = BackgroundJobStatus.Completed;
            job.Progress = 100;
            job.CompletedAt = DateTime.UtcNow;
            job.UpdatedAt = DateTime.UtcNow;
            job.ResultJson = resultJson;

            await _unitOfWork.BackgroundJobs.UpdateAsync(job);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogInformation("Completed background job {JobId}", jobId);
        }

        public async Task FailJobAsync(Guid jobId, string errorMessage, CancellationToken cancellationToken = default)
        {
            var job = await GetJobAsync(jobId, cancellationToken);
            if (job == null)
            {
                _logger.LogWarning("Attempted to fail non-existent job {JobId}", jobId);
                return;
            }

            job.Status = BackgroundJobStatus.Failed;
            job.ErrorMessage = errorMessage;
            job.CompletedAt = DateTime.UtcNow;
            job.UpdatedAt = DateTime.UtcNow;

            await _unitOfWork.BackgroundJobs.UpdateAsync(job);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogError("Failed background job {JobId}: {ErrorMessage}", jobId, errorMessage);
        }

        public async Task CancelJobAsync(Guid jobId, CancellationToken cancellationToken = default)
        {
            var job = await GetJobAsync(jobId, cancellationToken);
            if (job == null)
            {
                _logger.LogWarning("Attempted to cancel non-existent job {JobId}", jobId);
                return;
            }

            if (!job.CanCancel)
            {
                _logger.LogWarning("Attempted to cancel non-cancellable job {JobId}", jobId);
                return;
            }

            if (job.Status == BackgroundJobStatus.Pending || job.Status == BackgroundJobStatus.Running)
            {
                job.CancellationRequested = true;
                job.UpdatedAt = DateTime.UtcNow;

                await _unitOfWork.BackgroundJobs.UpdateAsync(job);
                await _unitOfWork.SaveChangesAsync();

                _logger.LogInformation("Cancellation requested for job {JobId}", jobId);
            }
        }

        public async Task<bool> IsCancellationRequestedAsync(Guid jobId, CancellationToken cancellationToken = default)
        {
            var job = await GetJobAsync(jobId, cancellationToken);
            return job?.CancellationRequested ?? false;
        }

        public async Task CleanupOldJobsAsync(TimeSpan olderThan, CancellationToken cancellationToken = default)
        {
            var cutoffDate = DateTime.UtcNow - olderThan;
            var oldJobs = _unitOfWork.BackgroundJobs
                .GetQueryable()
                .Where(j => j.CompletedAt.HasValue && j.CompletedAt.Value < cutoffDate)
                .ToList();

            foreach (var job in oldJobs)
            {
                await _unitOfWork.BackgroundJobs.DeleteByIdAsync(job.Id);
            }

            if (oldJobs.Count > 0)
            {
                await _unitOfWork.SaveChangesAsync();
                _logger.LogInformation("Cleaned up {Count} old background jobs", oldJobs.Count);
            }
        }
    }
}