using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces
{
    /// <summary>
    /// Service for managing long-running background jobs
    /// </summary>
    public interface IBackgroundJobService
    {
        /// <summary>
        /// Create a new background job
        /// </summary>
        Task<BackgroundJob> CreateJobAsync(BackgroundJobType type, string? parametersJson = null, CancellationToken cancellationToken = default);

        /// <summary>
        /// Get a job by ID
        /// </summary>
        Task<BackgroundJob?> GetJobAsync(Guid jobId, CancellationToken cancellationToken = default);

        /// <summary>
        /// Get all jobs, optionally filtered by status
        /// </summary>
        Task<List<BackgroundJob>> GetJobsAsync(BackgroundJobStatus? status = null, int? limit = null, CancellationToken cancellationToken = default);

        /// <summary>
        /// Update job progress
        /// </summary>
        Task UpdateProgressAsync(Guid jobId, int progress, string? statusMessage = null, CancellationToken cancellationToken = default);

        /// <summary>
        /// Update job item counts
        /// </summary>
        Task UpdateItemCountsAsync(Guid jobId, int totalItems, int processedItems, int failedItems, CancellationToken cancellationToken = default);

        /// <summary>
        /// Mark job as started
        /// </summary>
        Task StartJobAsync(Guid jobId, CancellationToken cancellationToken = default);

        /// <summary>
        /// Mark job as completed
        /// </summary>
        Task CompleteJobAsync(Guid jobId, string? resultJson = null, CancellationToken cancellationToken = default);

        /// <summary>
        /// Mark job as failed
        /// </summary>
        Task FailJobAsync(Guid jobId, string errorMessage, CancellationToken cancellationToken = default);

        /// <summary>
        /// Request cancellation of a job
        /// </summary>
        Task CancelJobAsync(Guid jobId, CancellationToken cancellationToken = default);

        /// <summary>
        /// Check if cancellation has been requested for a job
        /// </summary>
        Task<bool> IsCancellationRequestedAsync(Guid jobId, CancellationToken cancellationToken = default);

        /// <summary>
        /// Delete old completed jobs
        /// </summary>
        Task CleanupOldJobsAsync(TimeSpan olderThan, CancellationToken cancellationToken = default);

        /// <summary>
        /// Get the currently active (Pending or Running) job for a specific type, if any.
        /// </summary>
        Task<BackgroundJob?> GetActiveJobByTypeAsync(BackgroundJobType type, CancellationToken cancellationToken = default);

        /// <summary>
        /// Attempt to enqueue a singleton job of the given type.
        /// If a Pending or Running job of that type already exists, returns (created: false, existingJob).
        /// Otherwise creates a new Pending job and returns (created: true, newJob).
        /// </summary>
        Task<(bool created, BackgroundJob job)> TryEnqueueSingletonJobAsync(BackgroundJobType type, string? parametersJson = null, CancellationToken cancellationToken = default);
    }
}