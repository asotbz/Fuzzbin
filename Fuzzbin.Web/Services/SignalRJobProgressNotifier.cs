using Microsoft.AspNetCore.SignalR;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Web.Hubs;

namespace Fuzzbin.Web.Services;

/// <summary>
/// Notifies clients about background job progress via SignalR
/// </summary>
public class SignalRJobProgressNotifier : IJobProgressNotifier
{
    private readonly IHubContext<JobProgressHub> _hubContext;
    private readonly ILogger<SignalRJobProgressNotifier> _logger;

    public SignalRJobProgressNotifier(
        IHubContext<JobProgressHub> hubContext,
        ILogger<SignalRJobProgressNotifier> logger)
    {
        _hubContext = hubContext;
        _logger = logger;
    }

    public async Task NotifyJobStartedAsync(Guid jobId, BackgroundJobType type, CancellationToken cancellationToken = default)
    {
        try
        {
            await _hubContext.Clients.All.SendAsync(
                "JobStarted",
                jobId,
                type.ToString(),
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send job started notification for job {JobId}", jobId);
        }
    }

    public async Task NotifyJobProgressAsync(Guid jobId, int progress, string? statusMessage = null, CancellationToken cancellationToken = default)
    {
        try
        {
            await _hubContext.Clients.All.SendAsync(
                "JobProgress",
                jobId,
                progress,
                statusMessage,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send job progress notification for job {JobId}", jobId);
        }
    }

    public async Task NotifyJobCompletedAsync(Guid jobId, string? resultSummary = null, CancellationToken cancellationToken = default)
    {
        try
        {
            await _hubContext.Clients.All.SendAsync(
                "JobCompleted",
                jobId,
                resultSummary,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send job completion notification for job {JobId}", jobId);
        }
    }

    public async Task NotifyJobFailedAsync(Guid jobId, string errorMessage, CancellationToken cancellationToken = default)
    {
        try
        {
            await _hubContext.Clients.All.SendAsync(
                "JobFailed",
                jobId,
                errorMessage,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send job failed notification for job {JobId}", jobId);
        }
    }

    public async Task NotifyJobCancelledAsync(Guid jobId, CancellationToken cancellationToken = default)
    {
        try
        {
            await _hubContext.Clients.All.SendAsync(
                "JobCancelled",
                jobId,
                cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send job cancelled notification for job {JobId}", jobId);
        }
    }
}