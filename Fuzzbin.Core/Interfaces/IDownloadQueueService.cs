using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces
{
    public interface IDownloadQueueService
    {
        /// <summary>
        /// Adds a new download to the queue
        /// </summary>
        Task<DownloadQueueItem> AddToQueueAsync(string url, string? customTitle = null, int priority = 0);
        
        /// <summary>
        /// Gets all items in the queue
        /// </summary>
        Task<List<DownloadQueueItem>> GetQueueAsync(bool includeCompleted = false);
        
        /// <summary>
        /// Gets items pending download
        /// </summary>
        Task<List<DownloadQueueItem>> GetPendingDownloadsAsync();
        
        /// <summary>
        /// Updates the status of a queue item
        /// </summary>
        Task UpdateStatusAsync(Guid queueId, DownloadStatus status, string? errorMessage = null);
        
        /// <summary>
        /// Updates download progress
        /// </summary>
        Task UpdateProgressAsync(Guid queueId, double percentage, string? speed = null, string? eta = null);
        
        /// <summary>
        /// Removes an item from the queue
        /// </summary>
        Task<bool> RemoveFromQueueAsync(Guid queueId);
        
        /// <summary>
        /// Clears completed downloads from the queue
        /// </summary>
        Task<int> ClearCompletedAsync();
        
        /// <summary>
        /// Retries a failed download
        /// </summary>
        Task<bool> RetryDownloadAsync(Guid queueId);
        
        /// <summary>
        /// Gets the next item to download based on priority
        /// </summary>
        Task<DownloadQueueItem?> GetNextDownloadAsync();
    }
    
    public enum DownloadStatus
    {
        Pending,
        Searching,
        Downloading,
        Processing,
        Completed,
        Failed,
        Cancelled
    }
}
