using System;

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
