using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

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
