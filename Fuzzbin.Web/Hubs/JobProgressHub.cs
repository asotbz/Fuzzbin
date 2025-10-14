using Microsoft.AspNetCore.SignalR;
using System;
using System.Threading.Tasks;

namespace Fuzzbin.Web.Hubs
{
    /// <summary>
    /// SignalR hub for broadcasting background job progress updates.
    /// Clients join a per-job group via SubscribeToJob and receive updates
    /// published by SignalRJobProgressNotifier.
    /// </summary>
    public class JobProgressHub : Hub
    {
        public async Task SubscribeToJob(Guid jobId)
        {
            await Groups.AddToGroupAsync(Context.ConnectionId, $"job_{jobId}");
        }

        public async Task UnsubscribeFromJob(Guid jobId)
        {
            await Groups.RemoveFromGroupAsync(Context.ConnectionId, $"job_{jobId}");
        }
    }
}