using System;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces
{
    /// <summary>
    /// Interface for notifying clients about background job progress
    /// </summary>
    public interface IJobProgressNotifier
    {
        /// <summary>
        /// Notify that a job has started
        /// </summary>
        Task NotifyJobStartedAsync(Guid jobId, BackgroundJobType type, CancellationToken cancellationToken = default);

        /// <summary>
        /// Notify about job progress update
        /// </summary>
        Task NotifyJobProgressAsync(Guid jobId, int progress, string? statusMessage = null, CancellationToken cancellationToken = default);

        /// <summary>
        /// Notify that a job has completed successfully
        /// </summary>
        Task NotifyJobCompletedAsync(Guid jobId, string? resultSummary = null, CancellationToken cancellationToken = default);

        /// <summary>
        /// Notify that a job has failed
        /// </summary>
        Task NotifyJobFailedAsync(Guid jobId, string errorMessage, CancellationToken cancellationToken = default);

        /// <summary>
        /// Notify that a job has been cancelled
        /// </summary>
        Task NotifyJobCancelledAsync(Guid jobId, CancellationToken cancellationToken = default);
    }
}