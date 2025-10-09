using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces
{
    public interface IDownloadQueueService
    {
        Task<DownloadQueueItem> AddToQueueAsync(string url, int priority = 5);
        Task<DownloadQueueItem?> GetNextQueueItemAsync();
        Task UpdateProgressAsync(Guid itemId, double progress);
        Task UpdateProgressAsync(Guid itemId, double progress, string? downloadSpeed, string? eta);
        Task UpdateStatusAsync(Guid itemId, DownloadStatus status, string? errorMessage = null);
        Task<DownloadQueueItem?> GetByIdAsync(Guid id);
        Task MarkAsCompletedAsync(Guid itemId, Guid? videoId = null);
        Task<List<DownloadQueueItem>> GetPendingDownloadsAsync();
        Task<bool> RetryDownloadAsync(Guid queueId);
        Task UpdateFilePathAsync(Guid itemId, string? filePath, string? outputPath = null);
    }
}
