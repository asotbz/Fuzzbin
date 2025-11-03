using Microsoft.AspNetCore.SignalR;

namespace Fuzzbin.Web.Hubs
{
    /// <summary>
    /// SignalR hub for broadcasting download queue updates in real-time.
    /// Clients can subscribe to receive notifications about download progress,
    /// status changes, and queue modifications.
    /// </summary>
    public class DownloadQueueHub : Hub
    {
        /// <summary>
        /// Subscribe to download queue updates
        /// </summary>
        public async Task SubscribeToQueue()
        {
            await Groups.AddToGroupAsync(Context.ConnectionId, "download_queue");
        }

        /// <summary>
        /// Unsubscribe from download queue updates
        /// </summary>
        public async Task UnsubscribeFromQueue()
        {
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, "download_queue");
        }

        /// <summary>
        /// Subscribe to updates for a specific download item
        /// </summary>
        public async Task SubscribeToDownload(Guid downloadId)
        {
            await Groups.AddToGroupAsync(Context.ConnectionId, $"download_{downloadId}");
        }

        /// <summary>
        /// Unsubscribe from updates for a specific download item
        /// </summary>
        public async Task UnsubscribeFromDownload(Guid downloadId)
        {
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, $"download_{downloadId}");
        }
    }
}