using Microsoft.AspNetCore.SignalR;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Web.Hubs;

namespace Fuzzbin.Web.Services;

/// <summary>
/// Notifies subscribed clients (per-job SignalR group) about background job lifecycle & progress.
/// Unified notifier (replaces duplicate JobProgressNotifier inside hub).
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

    private IClientProxy Group(Guid jobId) => _hubContext.Clients.Group($"job_{jobId}");

    public async Task NotifyJobStartedAsync(Guid jobId, BackgroundJobType type, CancellationToken cancellationToken = default)
    {
        try
        {
            await Group(jobId).SendAsync("JobStarted", new
            {
                JobId = jobId,
                Type = type,
                StartedAt = DateTime.UtcNow
            }, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send JobStarted for {JobId}", jobId);
        }
    }

    public async Task NotifyJobProgressAsync(Guid jobId, int progress, string? statusMessage = null, CancellationToken cancellationToken = default)
    {
        try
        {
            await Group(jobId).SendAsync("JobProgress", new
            {
                JobId = jobId,
                Progress = progress,
                StatusMessage = statusMessage,
                UpdatedAt = DateTime.UtcNow
            }, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send JobProgress for {JobId}", jobId);
        }
    }

    public async Task NotifyJobCompletedAsync(Guid jobId, string? resultSummary = null, CancellationToken cancellationToken = default)
    {
        try
        {
            await Group(jobId).SendAsync("JobCompleted", new
            {
                JobId = jobId,
                ResultSummary = resultSummary,
                CompletedAt = DateTime.UtcNow
            }, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send JobCompleted for {JobId}", jobId);
        }
    }

    public async Task NotifyJobFailedAsync(Guid jobId, string errorMessage, CancellationToken cancellationToken = default)
    {
        try
        {
            await Group(jobId).SendAsync("JobFailed", new
            {
                JobId = jobId,
                ErrorMessage = errorMessage,
                FailedAt = DateTime.UtcNow
            }, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send JobFailed for {JobId}", jobId);
        }
    }

    public async Task NotifyJobCancelledAsync(Guid jobId, CancellationToken cancellationToken = default)
    {
        try
        {
            await Group(jobId).SendAsync("JobCancelled", new
            {
                JobId = jobId,
                CancelledAt = DateTime.UtcNow
            }, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to send JobCancelled for {JobId}", jobId);
        }
    }
}