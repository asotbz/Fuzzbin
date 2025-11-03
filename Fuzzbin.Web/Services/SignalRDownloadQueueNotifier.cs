using System;
using System.Threading.Tasks;
using Microsoft.AspNetCore.SignalR;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Web.Hubs;

namespace Fuzzbin.Web.Services
{
    /// <summary>
    /// Broadcasts download queue events to connected SignalR clients
    /// </summary>
    public class SignalRDownloadQueueNotifier : IDownloadQueueUpdateNotifier
    {
        private readonly IHubContext<DownloadQueueHub> _hubContext;
        private readonly ILogger<SignalRDownloadQueueNotifier> _logger;

        public SignalRDownloadQueueNotifier(
            IHubContext<DownloadQueueHub> hubContext,
            ILogger<SignalRDownloadQueueNotifier> logger)
        {
            _hubContext = hubContext;
            _logger = logger;
        }

        public async Task DownloadAddedAsync(DownloadQueueItem item)
        {
            try
            {
                await _hubContext.Clients.Group("download_queue").SendAsync("DownloadAdded", new
                {
                    item.Id,
                    item.Url,
                    item.Title,
                    item.Status,
                    item.Priority,
                    item.AddedDate,
                    UpdatedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to send DownloadAdded notification for {DownloadId}", item.Id);
            }
        }

        public async Task DownloadStatusChangedAsync(Guid downloadId, DownloadStatus status, string? errorMessage = null)
        {
            try
            {
                await _hubContext.Clients.Group("download_queue").SendAsync("DownloadStatusChanged", new
                {
                    DownloadId = downloadId,
                    Status = status,
                    ErrorMessage = errorMessage,
                    UpdatedAt = DateTime.UtcNow
                });

                // Also notify specific download subscribers
                await _hubContext.Clients.Group($"download_{downloadId}").SendAsync("StatusChanged", new
                {
                    Status = status,
                    ErrorMessage = errorMessage,
                    UpdatedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to send DownloadStatusChanged notification for {DownloadId}", downloadId);
            }
        }

        public async Task DownloadProgressUpdatedAsync(Guid downloadId, double progress, string? downloadSpeed = null, string? eta = null)
        {
            try
            {
                await _hubContext.Clients.Group("download_queue").SendAsync("DownloadProgressUpdated", new
                {
                    DownloadId = downloadId,
                    Progress = progress,
                    DownloadSpeed = downloadSpeed,
                    ETA = eta,
                    UpdatedAt = DateTime.UtcNow
                });

                // Also notify specific download subscribers
                await _hubContext.Clients.Group($"download_{downloadId}").SendAsync("ProgressUpdated", new
                {
                    Progress = progress,
                    DownloadSpeed = downloadSpeed,
                    ETA = eta,
                    UpdatedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Failed to send DownloadProgressUpdated notification for {DownloadId}", downloadId);
            }
        }

        public async Task DownloadRemovedAsync(Guid downloadId)
        {
            try
            {
                await _hubContext.Clients.Group("download_queue").SendAsync("DownloadRemoved", new
                {
                    DownloadId = downloadId,
                    UpdatedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to send DownloadRemoved notification for {DownloadId}", downloadId);
            }
        }

        public async Task DownloadsClearedAsync(DownloadStatus status, int count)
        {
            try
            {
                await _hubContext.Clients.Group("download_queue").SendAsync("DownloadsCleared", new
                {
                    Status = status,
                    Count = count,
                    UpdatedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to send DownloadsCleared notification for status {Status}", status);
            }
        }

        public async Task DownloadCompletedAsync(Guid downloadId, Guid? videoId = null)
        {
            try
            {
                await _hubContext.Clients.Group("download_queue").SendAsync("DownloadCompleted", new
                {
                    DownloadId = downloadId,
                    VideoId = videoId,
                    UpdatedAt = DateTime.UtcNow
                });

                // Also notify specific download subscribers
                await _hubContext.Clients.Group($"download_{downloadId}").SendAsync("Completed", new
                {
                    VideoId = videoId,
                    UpdatedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to send DownloadCompleted notification for {DownloadId}", downloadId);
            }
        }

        public async Task AllFailedDownloadsRetriedAsync(int count)
        {
            try
            {
                await _hubContext.Clients.Group("download_queue").SendAsync("AllFailedDownloadsRetried", new
                {
                    Count = count,
                    UpdatedAt = DateTime.UtcNow
                });
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to send AllFailedDownloadsRetried notification");
            }
        }
    }
}