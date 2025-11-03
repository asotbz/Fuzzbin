using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Services;

/// <summary>
/// Background service that executes registered maintenance tasks on a configurable schedule
/// </summary>
public class MaintenanceSchedulerService : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<MaintenanceSchedulerService> _logger;
    
    public MaintenanceSchedulerService(
        IServiceScopeFactory scopeFactory,
        ILogger<MaintenanceSchedulerService> logger)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Maintenance scheduler service started");

        try
        {
            // Wait a short delay on startup before first run
            await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
            
            // Run immediately after delay, then on interval
            await RunMaintenanceAsync(stoppingToken);

            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    var interval = await GetMaintenanceIntervalAsync();
                    await Task.Delay(interval, stoppingToken);
                    await RunMaintenanceAsync(stoppingToken);
                }
                catch (OperationCanceledException)
                {
                    // Expected during shutdown
                    break;
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error in maintenance scheduler");
                    // Wait 1 hour before retrying on error
                    await Task.Delay(TimeSpan.FromHours(1), stoppingToken);
                }
            }
        }
        catch (OperationCanceledException)
        {
            // Expected during shutdown, including test environment
            _logger.LogInformation("Maintenance scheduler service stopped (cancellation requested)");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Critical error in maintenance scheduler service");
        }

        _logger.LogInformation("Maintenance scheduler service stopped");
    }

    /// <summary>
    /// Runs all enabled maintenance tasks sequentially
    /// </summary>
    public async Task RunMaintenanceAsync(CancellationToken cancellationToken)
    {
        using var scope = _scopeFactory.CreateScope();
        var tasks = scope.ServiceProvider.GetServices<IMaintenanceTask>().ToList();
        var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

        if (tasks.Count == 0)
        {
            _logger.LogInformation("No maintenance tasks registered");
            return;
        }

        var runStarted = DateTime.UtcNow;
        _logger.LogInformation("Starting maintenance run with {TaskCount} registered tasks", tasks.Count);

        var results = new List<(string TaskName, MaintenanceTaskResult Result)>();

        foreach (var task in tasks)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            if (!task.IsEnabled)
            {
                _logger.LogInformation("Skipping disabled task: {TaskName}", task.TaskName);
                continue;
            }

            _logger.LogInformation("Executing maintenance task: {TaskName} - {Description}", 
                task.TaskName, task.Description);

            var taskStarted = DateTime.UtcNow;
            var stopwatch = Stopwatch.StartNew();
            MaintenanceTaskResult result;

            try
            {
                result = await task.ExecuteAsync(cancellationToken);
                stopwatch.Stop();
                result.Duration = stopwatch.Elapsed;

                if (result.Success)
                {
                    _logger.LogInformation(
                        "Maintenance task completed: {TaskName} - {Summary} (Duration: {Duration:g})",
                        task.TaskName, result.Summary, result.Duration);
                }
                else
                {
                    _logger.LogWarning(
                        "Maintenance task failed: {TaskName} - {Error}",
                        task.TaskName, result.ErrorMessage ?? "Unknown error");
                }
            }
            catch (Exception ex)
            {
                stopwatch.Stop();
                _logger.LogError(ex, "Exception executing maintenance task: {TaskName}", task.TaskName);
                
                result = new MaintenanceTaskResult
                {
                    Success = false,
                    ErrorMessage = ex.Message,
                    Duration = stopwatch.Elapsed
                };
            }

            results.Add((task.TaskName, result));

            // Record execution in database
            try
            {
                var execution = new MaintenanceExecution
                {
                    TaskName = task.TaskName,
                    StartedAt = taskStarted,
                    CompletedAt = DateTime.UtcNow,
                    Success = result.Success,
                    Summary = result.Summary,
                    ItemsProcessed = result.ItemsProcessed,
                    ErrorMessage = result.ErrorMessage,
                    DurationMs = (int)result.Duration.TotalMilliseconds,
                    MetricsJson = result.Metrics != null 
                        ? System.Text.Json.JsonSerializer.Serialize(result.Metrics) 
                        : null
                };

                await unitOfWork.MaintenanceExecutions.AddAsync(execution);
                await unitOfWork.SaveChangesAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to record maintenance execution for task: {TaskName}", task.TaskName);
            }
        }

        var totalDuration = DateTime.UtcNow - runStarted;
        var successCount = results.Count(r => r.Result.Success);
        var failureCount = results.Count - successCount;

        _logger.LogInformation(
            "Maintenance run completed: {SuccessCount} succeeded, {FailureCount} failed (Total Duration: {Duration:g})",
            successCount, failureCount, totalDuration);
    }

    private async Task<TimeSpan> GetMaintenanceIntervalAsync()
    {
        using var scope = _scopeFactory.CreateScope();
        var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

        var config = await unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Category == "Maintenance" && c.Key == "IntervalHours");

        if (config != null && int.TryParse(config.Value, out var hours) && hours > 0)
        {
            return TimeSpan.FromHours(hours);
        }

        return TimeSpan.FromHours(8); // Default: 8 hours
    }
}
