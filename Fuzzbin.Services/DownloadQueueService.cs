using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications.DownloadQueue;
using Fuzzbin.Services.Interfaces;
using DownloadStatusEnum = Fuzzbin.Core.Entities.DownloadStatus;

namespace Fuzzbin.Services
{
    public class DownloadQueueService : Fuzzbin.Services.Interfaces.IDownloadQueueService
    {
        private readonly IUnitOfWork _unitOfWork;
        private readonly ILogger<DownloadQueueService> _logger;
        private readonly IDownloadTaskQueue _taskQueue;
        private readonly IDownloadSettingsProvider _settingsProvider;
        
        public DownloadQueueService(
            IUnitOfWork unitOfWork,
            ILogger<DownloadQueueService> logger,
            IDownloadTaskQueue taskQueue,
            IDownloadSettingsProvider settingsProvider)
        {
            _unitOfWork = unitOfWork;
            _logger = logger;
            _taskQueue = taskQueue;
            _settingsProvider = settingsProvider;
        }
        
        public async Task<DownloadQueueItem> AddToQueueAsync(
            string url,
            string outputPath,
            string? format = null,
            int priority = 0,
            string? title = null)
        {
            try
            {
                var options = _settingsProvider.GetOptions();
                var resolvedOutputPath = string.IsNullOrWhiteSpace(outputPath)
                    ? options.OutputDirectory
                    : outputPath;

                if (!Path.IsPathRooted(resolvedOutputPath))
                {
                    resolvedOutputPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, resolvedOutputPath);
                }

                Directory.CreateDirectory(resolvedOutputPath);

                var queueItem = new DownloadQueue
                {
                    Url = url,
                    OutputPath = resolvedOutputPath,
                    Format = string.IsNullOrWhiteSpace(format) ? options.Format : format,
                    Priority = priority,
                    Status = DownloadStatusEnum.Queued,
                    AddedDate = DateTime.UtcNow,
                    RetryCount = 0,
                    IsDeleted = false,
                    UpdatedAt = DateTime.UtcNow
                };
                
                if (!string.IsNullOrWhiteSpace(title))
                {
                    queueItem.Title = title;
                }
                
                await _unitOfWork.DownloadQueueItems.AddAsync(queueItem);
                await _unitOfWork.SaveChangesAsync();

                await _taskQueue.QueueAsync(queueItem.Id);
                
                _logger.LogInformation("Added URL to download queue: {Url}", url);
                return queueItem;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error adding URL to queue: {Url}", url);
                throw;
            }
        }
        
        public async Task<DownloadQueueItem> AddToQueueAsync(
            string url,
            string? customTitle = null,
            int priority = 0)
        {
            // Overload for backward compatibility
            var options = _settingsProvider.GetOptions();
            return await AddToQueueAsync(url, options.OutputDirectory, null, priority, customTitle);
        }
        
        public async Task<List<DownloadQueueItem>> GetPendingDownloadsAsync()
        {
            try
            {
                var specification = new DownloadQueuePendingSpecification(includeFailed: true);
                var items = await _unitOfWork.DownloadQueueItems.ListAsync(specification);
                return items.ToList();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting pending downloads");
                throw;
            }
        }

        public async Task<IEnumerable<DownloadQueueItem>> GetActiveDownloadsAsync()
        {
            try
            {
                var specification = new DownloadQueueActiveSpecification();
                return await _unitOfWork.DownloadQueueItems.ListAsync(specification);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting active downloads");
                throw;
            }
        }

        public async Task<IEnumerable<DownloadQueueItem>> GetQueueHistoryAsync(
            int pageNumber = 1,
            int pageSize = 50)
        {
            try
            {
                var specification = new DownloadQueueHistorySpecification(
                    olderThan: null,
                    page: pageNumber,
                    pageSize: pageSize);

                return await _unitOfWork.DownloadQueueItems.ListAsync(specification);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting queue history");
                throw;
            }
        }
        
        public async Task UpdateQueueItemStatusAsync(
            Guid queueId,
            DownloadStatusEnum status,
            string? errorMessage = null)
        {
            try
            {
                var item = await GetQueueItemAsync(queueId, track: true);
                
                if (item != null)
                {
                    item.Status = status;
                    item.ErrorMessage = errorMessage;
                    item.UpdatedAt = DateTime.UtcNow;
                    
                    if (status == DownloadStatusEnum.Downloading)
                    {
                        item.StartedDate = DateTime.UtcNow;
                    }
                    else if (status == DownloadStatusEnum.Completed ||
                             status == DownloadStatusEnum.Failed)
                    {
                        item.CompletedDate = DateTime.UtcNow;
                    }
                    
                    await _unitOfWork.DownloadQueueItems.UpdateAsync(item);
                    await _unitOfWork.SaveChangesAsync();
                    _logger.LogInformation("Updated queue item {Id} status to {Status}", queueId, status);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating queue item status: {Id}", queueId);
                throw;
            }
        }
        
        public async Task UpdateProgressAsync(
            Guid queueId,
            double progress,
            string? downloadSpeed = null,
            string? eta = null)
        {
            try
            {
                var item = await GetQueueItemAsync(queueId, track: true);
                
                if (item != null)
                {
                    item.Progress = Math.Clamp(progress, 0, 100);
                    item.DownloadSpeed = downloadSpeed;
                    item.ETA = eta;
                    item.UpdatedAt = DateTime.UtcNow;
                    await _unitOfWork.DownloadQueueItems.UpdateAsync(item);
                    await _unitOfWork.SaveChangesAsync();
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating queue item progress: {Id}", queueId);
                throw;
            }
        }
        
        public async Task<bool> RemoveFromQueueAsync(Guid queueId)
        {
            try
            {
                var item = await GetQueueItemAsync(queueId, track: true);
                
                if (item != null && item.Status != DownloadStatusEnum.Downloading)
                {
                    item.IsDeleted = true;
                    item.DeletedDate = DateTime.UtcNow;
                    item.UpdatedAt = DateTime.UtcNow;
                    await _unitOfWork.DownloadQueueItems.UpdateAsync(item);
                    await _unitOfWork.SaveChangesAsync();
                    _logger.LogInformation("Removed queue item: {Id}", queueId);
                    return true;
                }
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error removing queue item: {Id}", queueId);
                throw;
            }
        }
        
        public async Task<bool> RetryFailedDownloadAsync(Guid queueId)
        {
            try
            {
                var item = await GetQueueItemAsync(queueId, track: true);
                
                if (item != null && item.Status == DownloadStatusEnum.Failed)
                {
                    item.Status = DownloadStatusEnum.Queued;
                    item.RetryCount++;
                    item.ErrorMessage = null;
                    item.StartedDate = null;
                    item.CompletedDate = null;
                    item.Progress = 0;
                    item.DownloadSpeed = null;
                    item.ETA = null;
                    item.UpdatedAt = DateTime.UtcNow;
                    await _unitOfWork.DownloadQueueItems.UpdateAsync(item);
                    await _unitOfWork.SaveChangesAsync();
                    await _taskQueue.QueueAsync(queueId);
                    
                    _logger.LogInformation("Retrying download {QueueId} (attempt #{RetryCount})", 
                        queueId, item.RetryCount);
                    return true;
                }
                return false;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrying download: {Id}", queueId);
                throw;
            }
        }
        
        public async Task<int> ClearCompletedAsync()
        {
            try
            {
                var specification = new DownloadQueueByStatusSpecification(DownloadStatusEnum.Completed, includeVideo: false);
                var completed = await _unitOfWork.DownloadQueueItems.ListAsync(specification);

                foreach (var item in completed)
                {
                    item.IsDeleted = true;
                    item.DeletedDate = DateTime.UtcNow;
                    item.UpdatedAt = DateTime.UtcNow;
                    await _unitOfWork.DownloadQueueItems.UpdateAsync(item);
                }

                await _unitOfWork.SaveChangesAsync();
                var count = completed.Count;
                _logger.LogInformation("Cleared {Count} completed downloads", count);
                return count;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error clearing completed items from queue");
                throw;
            }
        }

        public async Task<int> GetQueuePositionAsync(Guid queueId)
        {
            try
            {
                var item = await GetQueueItemAsync(queueId, track: false);
                
                if (item == null || item.IsDeleted)
                    return -1;
                
                var specification = new DownloadQueuePendingSpecification(includeFailed: false);
                var pendingItems = await _unitOfWork.DownloadQueueItems.ListAsync(specification);

                var orderedItems = pendingItems
                    .OrderByDescending(q => q.Priority)
                    .ThenBy(q => q.AddedDate)
                    .ToList();
                
                var position = orderedItems.FindIndex(q => q.Id == item.Id);
                return position + 1; // 1-based position
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting queue position: {Id}", queueId);
                throw;
            }
        }
        
        public async Task<IEnumerable<DownloadQueueItem>> GetAllQueuedItemsAsync()
        {
            try
            {
                var specification = new DownloadQueuePendingSpecification(includeFailed: true);
                return await _unitOfWork.DownloadQueueItems.ListAsync(specification);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting all queued items");
                throw;
            }
        }
        
        // Additional methods for compatibility
        public async Task<List<DownloadQueueItem>> GetQueueAsync(bool includeCompleted = false)
        {
            try
            {
                var items = (await _unitOfWork.DownloadQueueItems.ListAsync(new DownloadQueueAllSpecification()))
                    .ToList();

                if (!includeCompleted)
                {
                    items = items
                        .Where(q => q.Status != DownloadStatusEnum.Completed && q.Status != DownloadStatusEnum.Failed)
                        .ToList();
                }

                return items;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting download queue");
                throw;
            }
        }
        
        
        
        public async Task<bool> RetryDownloadAsync(Guid queueId)
        {
            return await RetryFailedDownloadAsync(queueId);
        }

        public async Task<DownloadQueueItem?> GetNextDownloadAsync()
        {
            try
            {
                var specification = new DownloadQueuePendingSpecification(includeFailed: false);
                var items = await _unitOfWork.DownloadQueueItems.ListAsync(specification);

                var nextItem = items
                    .OrderByDescending(q => q.Priority)
                    .ThenBy(q => q.AddedDate)
                    .FirstOrDefault();

                return nextItem;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting next download");
                throw;
            }
        }

        // IDownloadQueueService implementation
        public async Task<DownloadQueueItem> AddToQueueAsync(string url, int priority = 5)
        {
            var options = _settingsProvider.GetOptions();
            return await AddToQueueAsync(url, options.OutputDirectory, null, priority);
        }

        public async Task<DownloadQueueItem?> GetNextQueueItemAsync()
        {
            return await GetNextDownloadAsync();
        }

        public async Task UpdateStatusAsync(Guid itemId, DownloadStatusEnum status, string? errorMessage = null)
        {
            await UpdateQueueItemStatusAsync(itemId, status, errorMessage);
        }

        public async Task UpdateProgressAsync(Guid itemId, double progress)
        {
            await UpdateProgressAsync(itemId, progress, null, null);
        }

        public async Task<DownloadQueueItem?> GetByIdAsync(Guid id)
        {
            return await GetQueueItemAsync(id, track: false);
        }

        public async Task UpdateFilePathAsync(Guid itemId, string? filePath, string? outputPath = null)
        {
            try
            {
                var item = await GetQueueItemAsync(itemId, track: true);

                if (item == null)
                {
                    return;
                }

                item.FilePath = filePath;

                if (!string.IsNullOrWhiteSpace(outputPath))
                {
                    item.OutputPath = outputPath;
                }

                item.UpdatedAt = DateTime.UtcNow;
                await _unitOfWork.DownloadQueueItems.UpdateAsync(item);
                await _unitOfWork.SaveChangesAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating queue item file path: {Id}", itemId);
                throw;
            }
        }

        public async Task MarkAsCompletedAsync(Guid itemId, Guid? videoId = null)
        {
            await UpdateQueueItemStatusAsync(itemId, DownloadStatusEnum.Completed, null);

            if (videoId.HasValue)
            {
                var item = await GetQueueItemAsync(itemId, track: true);
                if (item != null)
                {
                    item.VideoId = videoId;
                    item.UpdatedAt = DateTime.UtcNow;
                    await _unitOfWork.DownloadQueueItems.UpdateAsync(item);
                    await _unitOfWork.SaveChangesAsync();
                }
            }
        }

        private async Task<DownloadQueueItem?> GetQueueItemAsync(Guid queueId, bool track = false)
        {
            var specification = new DownloadQueueByIdSpecification(queueId, track);
            return await _unitOfWork.DownloadQueueItems.FirstOrDefaultAsync(specification);
        }
    }
}
