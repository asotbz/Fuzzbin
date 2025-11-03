using System;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces
{
    /// <summary>
    /// Notifies listeners about download queue updates in real-time
    /// </summary>
    public interface IDownloadQueueUpdateNotifier
    {
        /// <summary>
        /// Notify that a new download has been added to the queue
        /// </summary>
        Task DownloadAddedAsync(DownloadQueueItem item);

        /// <summary>
        /// Notify that a download's status has changed
        /// </summary>
        Task DownloadStatusChangedAsync(Guid downloadId, DownloadStatus status, string? errorMessage = null);

        /// <summary>
        /// Notify that a download's progress has been updated
        /// </summary>
        Task DownloadProgressUpdatedAsync(Guid downloadId, double progress, string? downloadSpeed = null, string? eta = null);

        /// <summary>
        /// Notify that a download has been removed from the queue
        /// </summary>
        Task DownloadRemovedAsync(Guid downloadId);

        /// <summary>
        /// Notify that multiple downloads have been cleared by status
        /// </summary>
        Task DownloadsClearedAsync(DownloadStatus status, int count);

        /// <summary>
        /// Notify that a download has been completed
        /// </summary>
        Task DownloadCompletedAsync(Guid downloadId, Guid? videoId = null);

        /// <summary>
        /// Notify that all failed downloads are being retried
        /// </summary>
        Task AllFailedDownloadsRetriedAsync(int count);
    }
}