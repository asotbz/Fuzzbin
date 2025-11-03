# Maintenance System Architecture

## Overview

A unified, modular background maintenance system that automatically performs periodic housekeeping tasks to maintain database health, storage efficiency, and system performance.

**Key Principles:**
- **Modular Design**: Each maintenance task is an independent, self-contained unit
- **Extensible**: New tasks can be added without modifying the scheduler
- **Configurable**: Each task and the scheduler have independent configuration
- **Observable**: Built-in logging, progress tracking, and statistics collection
- **Resilient**: Task failures don't affect other tasks; errors are logged and reported

---

## Core Architecture

### 1. Maintenance Task Interface

**Location**: `Fuzzbin.Core/Interfaces/IMaintenanceTask.cs`

```csharp
namespace Fuzzbin.Core.Interfaces;

/// <summary>
/// Interface for background maintenance tasks that can be scheduled and executed periodically
/// </summary>
public interface IMaintenanceTask
{
    /// <summary>
    /// Unique identifier for this maintenance task (e.g., "LibraryScan", "CachePurge")
    /// </summary>
    string TaskName { get; }
    
    /// <summary>
    /// Human-readable description of what this task does
    /// </summary>
    string Description { get; }
    
    /// <summary>
    /// Whether this task is enabled and should be executed
    /// Typically reads from configuration
    /// </summary>
    bool IsEnabled { get; }
    
    /// <summary>
    /// Executes the maintenance task
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Result summary of the maintenance operation</returns>
    Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken);
}

/// <summary>
/// Result of a maintenance task execution
/// </summary>
public class MaintenanceTaskResult
{
    /// <summary>
    /// Whether the task completed successfully
    /// </summary>
    public bool Success { get; set; }
    
    /// <summary>
    /// Human-readable summary of what was done
    /// Example: "Scanned 1,245 files, imported 12 new videos, marked 3 as missing"
    /// </summary>
    public string Summary { get; set; } = string.Empty;
    
    /// <summary>
    /// Number of items processed (files scanned, entries purged, etc.)
    /// </summary>
    public int ItemsProcessed { get; set; }
    
    /// <summary>
    /// How long the task took to execute
    /// </summary>
    public TimeSpan Duration { get; set; }
    
    /// <summary>
    /// Error message if task failed
    /// </summary>
    public string? ErrorMessage { get; set; }
    
    /// <summary>
    /// Additional metrics specific to the task
    /// Example: { "imported": 12, "missing": 3, "errors": 0 }
    /// </summary>
    public Dictionary<string, object>? Metrics { get; set; }
}
```

---

### 2. Maintenance Scheduler Service

**Location**: `Fuzzbin.Services/MaintenanceSchedulerService.cs`

The scheduler is a `BackgroundService` that:
1. Discovers all registered `IMaintenanceTask` implementations via DI
2. Runs on a configurable interval (default: 8 hours)
3. Executes enabled tasks sequentially
4. Logs results and errors
5. Records execution history to database

```csharp
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

        // Run immediately on startup, then on interval
        await RunMaintenanceAsync(stoppingToken);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var interval = GetMaintenanceInterval();
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

        _logger.LogInformation("Maintenance scheduler service stopped");
    }

    private async Task RunMaintenanceAsync(CancellationToken cancellationToken)
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
                    StartedAt = runStarted,
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

    private TimeSpan GetMaintenanceInterval()
    {
        using var scope = _scopeFactory.CreateScope();
        var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

        var intervalHours = unitOfWork.Configurations
            .FirstOrDefault(c => c.Category == "Maintenance" && c.Key == "IntervalHours")
            ?.Value;

        if (int.TryParse(intervalHours, out var hours) && hours > 0)
        {
            return TimeSpan.FromHours(hours);
        }

        return TimeSpan.FromHours(8); // Default: 8 hours
    }
}
```

---

### 3. Database Schema

**Location**: New entities in `Fuzzbin.Core/Entities/`

#### MaintenanceExecution Entity

Tracks each execution of maintenance tasks for historical analysis and monitoring.

```csharp
namespace Fuzzbin.Core.Entities;

/// <summary>
/// Records execution history of maintenance tasks
/// </summary>
public class MaintenanceExecution : BaseEntity
{
    /// <summary>
    /// Name of the maintenance task that was executed
    /// </summary>
    public string TaskName { get; set; } = string.Empty;
    
    /// <summary>
    /// When the task started executing
    /// </summary>
    public DateTime StartedAt { get; set; }
    
    /// <summary>
    /// When the task completed (success or failure)
    /// </summary>
    public DateTime CompletedAt { get; set; }
    
    /// <summary>
    /// Whether the task completed successfully
    /// </summary>
    public bool Success { get; set; }
    
    /// <summary>
    /// Human-readable summary of what was done
    /// </summary>
    public string Summary { get; set; } = string.Empty;
    
    /// <summary>
    /// Number of items processed
    /// </summary>
    public int ItemsProcessed { get; set; }
    
    /// <summary>
    /// Error message if task failed
    /// </summary>
    public string? ErrorMessage { get; set; }
    
    /// <summary>
    /// Duration in milliseconds
    /// </summary>
    public int DurationMs { get; set; }
    
    /// <summary>
    /// Task-specific metrics as JSON
    /// </summary>
    public string? MetricsJson { get; set; }
}
```

---

### 4. Configuration System

Maintenance tasks are configured via the `Configuration` entity with category `"Maintenance"`.

**Default Configuration Keys**:

```csharp
// Scheduler configuration
Category: "Maintenance"
Key: "IntervalHours"
Value: "8"
Description: "How often to run maintenance tasks (in hours). Default: 8"

// Individual task toggles (see task-specific documentation for details)
Category: "Maintenance"
Key: "LibraryScan.Enabled"
Value: "true"

Category: "Maintenance"
Key: "ThumbnailCleanup.Enabled"
Value: "true"

Category: "Maintenance"
Key: "CachePurge.Enabled"
Value: "true"

Category: "Maintenance"
Key: "CacheStats.Enabled"
Value: "true"

Category: "Maintenance"
Key: "RecycleBinPurge.Enabled"
Value: "true"

Category: "Maintenance"
Key: "RecycleBinPurge.RetentionDays"
Value: "7"

Category: "Maintenance"
Key: "AutoBackup.Enabled"
Value: "true"

Category: "Maintenance"
Key: "AutoBackup.IntervalHours"
Value: "24"
```

---

### 5. Service Registration

**Location**: `Fuzzbin.Web/Program.cs`

```csharp
// Register all maintenance tasks (order doesn't matter - scheduler executes sequentially)
builder.Services.AddScoped<IMaintenanceTask, LibraryScanMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, ThumbnailCleanupMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, CachePurgeMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, CacheStatsMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, RecycleBinPurgeMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, AutoBackupMaintenanceTask>();

// Register the scheduler as a hosted service
builder.Services.AddHostedService<MaintenanceSchedulerService>();
```

---

### 6. Manual Trigger API

**Location**: `Fuzzbin.Web/Program.cs` (add endpoint)

Allow administrators to manually trigger maintenance runs via API:

```csharp
// POST /api/maintenance/run - Manual maintenance trigger
app.MapPost("/api/maintenance/run", async (
    IServiceScopeFactory scopeFactory,
    ILogger<Program> logger,
    CancellationToken ct) =>
{
    using var scope = scopeFactory.CreateScope();
    var tasks = scope.ServiceProvider.GetServices<IMaintenanceTask>().ToList();
    var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

    if (tasks.Count == 0)
    {
        return Results.Ok(new { message = "No maintenance tasks registered" });
    }

    var runStarted = DateTime.UtcNow;
    var results = new List<object>();

    foreach (var task in tasks)
    {
        if (!task.IsEnabled)
        {
            results.Add(new { taskName = task.TaskName, skipped = true, reason = "Task is disabled" });
            continue;
        }

        logger.LogInformation("Manually executing maintenance task: {TaskName}", task.TaskName);

        MaintenanceTaskResult result;
        try
        {
            result = await task.ExecuteAsync(ct);
            
            results.Add(new
            {
                taskName = task.TaskName,
                success = result.Success,
                summary = result.Summary,
                itemsProcessed = result.ItemsProcessed,
                duration = result.Duration.ToString("g"),
                errorMessage = result.ErrorMessage,
                metrics = result.Metrics
            });

            // Record execution
            var execution = new MaintenanceExecution
            {
                TaskName = task.TaskName,
                StartedAt = runStarted,
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
            logger.LogError(ex, "Exception executing maintenance task: {TaskName}", task.TaskName);
            results.Add(new
            {
                taskName = task.TaskName,
                success = false,
                errorMessage = ex.Message
            });
        }
    }

    return Results.Ok(new
    {
        message = "Maintenance run completed",
        startedAt = runStarted,
        completedAt = DateTime.UtcNow,
        results
    });
})
.WithName("RunMaintenance")
.RequireAuthorization();

// GET /api/maintenance/history - Get execution history
app.MapGet("/api/maintenance/history", async (
    IUnitOfWork unitOfWork,
    int? limit = 50) =>
{
    var history = await unitOfWork.MaintenanceExecutions
        .OrderByDescending(e => e.StartedAt)
        .Take(limit ?? 50)
        .ToListAsync();

    return Results.Ok(history);
})
.WithName("GetMaintenanceHistory")
.RequireAuthorization();
```

---

## Extensibility Pattern

Adding a new maintenance task is straightforward:

### Step 1: Implement IMaintenanceTask

```csharp
public class MyNewMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<MyNewMaintenanceTask> _logger;
    
    public string TaskName => "MyNewTask";
    public string Description => "Does something useful";
    
    public bool IsEnabled
    {
        get
        {
            var config = _unitOfWork.Configurations
                .FirstOrDefault(c => c.Category == "Maintenance" 
                    && c.Key == "MyNewTask.Enabled");
            return config?.Value == "true";
        }
    }
    
    public MyNewMaintenanceTask(
        IUnitOfWork unitOfWork,
        ILogger<MyNewMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        
        try
        {
            // Do your maintenance work here
            var itemsProcessed = 0;
            
            // ... implementation ...
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = $"Processed {itemsProcessed} items",
                ItemsProcessed = itemsProcessed,
                Duration = stopwatch.Elapsed
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error in MyNewMaintenanceTask");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed
            };
        }
    }
}
```

### Step 2: Register in Program.cs

```csharp
builder.Services.AddScoped<IMaintenanceTask, MyNewMaintenanceTask>();
```

### Step 3: Add Configuration (Optional)

```csharp
Category: "Maintenance"
Key: "MyNewTask.Enabled"
Value: "true"
Description: "Enable/disable MyNewTask maintenance task"
```

That's it! The scheduler will automatically discover and execute your task.

---

## Testing Strategy

### Unit Tests

Test individual maintenance tasks in isolation:

```csharp
[Fact]
public async Task MyNewMaintenanceTask_ExecutesSuccessfully()
{
    // Arrange
    var unitOfWork = CreateMockUnitOfWork();
    var logger = CreateMockLogger();
    var task = new MyNewMaintenanceTask(unitOfWork, logger);
    
    // Act
    var result = await task.ExecuteAsync(CancellationToken.None);
    
    // Assert
    Assert.True(result.Success);
    Assert.True(result.ItemsProcessed > 0);
}
```

### Integration Tests

Test the scheduler with multiple tasks:

```csharp
[Fact]
public async Task MaintenanceScheduler_ExecutesAllEnabledTasks()
{
    // Arrange
    var services = CreateServiceCollection();
    services.AddScoped<IMaintenanceTask, Task1>();
    services.AddScoped<IMaintenanceTask, Task2>();
    var provider = services.BuildServiceProvider();
    
    // Act
    // Run scheduler once
    
    // Assert
    // Verify all enabled tasks executed
    // Verify executions recorded in database
}
```

---

## Monitoring & Observability

### Logging

All maintenance operations are logged with structured logging:

```csharp
_logger.LogInformation(
    "Maintenance task completed: {TaskName} - {Summary} (Duration: {Duration:g})",
    task.TaskName, result.Summary, result.Duration);
```

### Database History

Query `MaintenanceExecutions` table for:
- Success/failure rates by task
- Average execution duration
- Items processed over time
- Error patterns

### Metrics

Each task can provide custom metrics via `MaintenanceTaskResult.Metrics`:

```csharp
return new MaintenanceTaskResult
{
    Success = true,
    Summary = "Scan completed",
    ItemsProcessed = totalFiles,
    Metrics = new Dictionary<string, object>
    {
        ["imported"] = importedCount,
        ["missing"] = missingCount,
        ["errors"] = errorCount,
        ["scanDurationMs"] = scanDuration.TotalMilliseconds
    }
};
```

---

## Next Steps

See individual task specification documents:
- [02-library-scan-task.md](./02-library-scan-task.md)
- [03-thumbnail-cleanup-task.md](./03-thumbnail-cleanup-task.md)
- [04-cache-tasks.md](./04-cache-tasks.md)
- [05-recycle-bin-and-backup-tasks.md](./05-recycle-bin-and-backup-tasks.md)
- [06-database-schema.md](./06-database-schema.md)
