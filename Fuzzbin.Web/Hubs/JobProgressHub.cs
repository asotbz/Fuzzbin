using Microsoft.AspNetCore.SignalR;
using System;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Web.Hubs
{
    /// <summary>
    /// SignalR hub for broadcasting background job progress updates
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

    /// <summary>
    /// Service for sending job progress updates to connected clients
    /// </summary>
    public class JobProgressNotifier : IJobProgressNotifier
    {
        private readonly IHubContext<JobProgressHub> _hubContext;

        public JobProgressNotifier(IHubContext<JobProgressHub> hubContext)
        {
            _hubContext = hubContext;
        }

        public async Task NotifyJobStartedAsync(Guid jobId, BackgroundJobType type, CancellationToken cancellationToken = default)
        {
            await _hubContext.Clients.Group($"job_{jobId}").SendAsync("JobStarted", new
            {
                JobId = jobId,
                Type = type,
                StartedAt = DateTime.UtcNow
            }, cancellationToken);
        }

        public async Task NotifyJobProgressAsync(Guid jobId, int progress, string? statusMessage = null, CancellationToken cancellationToken = default)
        {
            await _hubContext.Clients.Group($"job_{jobId}").SendAsync("JobProgress", new
            {
                JobId = jobId,
                Progress = progress,
                StatusMessage = statusMessage,
                UpdatedAt = DateTime.UtcNow
            }, cancellationToken);
        }

        public async Task NotifyJobCompletedAsync(Guid jobId, string? resultSummary = null, CancellationToken cancellationToken = default)
        {
            await _hubContext.Clients.Group($"job_{jobId}").SendAsync("JobCompleted", new
            {
                JobId = jobId,
                ResultSummary = resultSummary,
                CompletedAt = DateTime.UtcNow
            }, cancellationToken);
        }

        public async Task NotifyJobFailedAsync(Guid jobId, string errorMessage, CancellationToken cancellationToken = default)
        {
            await _hubContext.Clients.Group($"job_{jobId}").SendAsync("JobFailed", new
            {
                JobId = jobId,
                ErrorMessage = errorMessage,
                FailedAt = DateTime.UtcNow
            }, cancellationToken);
        }

        public async Task NotifyJobCancelledAsync(Guid jobId, CancellationToken cancellationToken = default)
        {
            await _hubContext.Clients.Group($"job_{jobId}").SendAsync("JobCancelled", new
            {
                JobId = jobId,
                CancelledAt = DateTime.UtcNow
            }, cancellationToken);
        }
    }
}