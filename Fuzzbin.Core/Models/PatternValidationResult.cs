using System.Collections.Generic;

namespace Fuzzbin.Core.Models;

/// <summary>
/// Result of file naming pattern validation
/// </summary>
public class PatternValidationResult
{
    /// <summary>
    /// Indicates if the pattern is valid
    /// </summary>
    public bool IsValid { get; set; }

    /// <summary>
    /// List of validation errors (empty if valid)
    /// </summary>
    public List<string> Errors { get; set; } = new();

    /// <summary>
    /// Example filename generated from the pattern
    /// </summary>
    public string? ExampleFilename { get; set; }

    /// <summary>
    /// List of variables used in the pattern
    /// </summary>
    public List<string> UsedVariables { get; set; } = new();

    /// <summary>
    /// Warnings about the pattern (non-critical issues)
    /// </summary>
    public List<string> Warnings { get; set; } = new();
}