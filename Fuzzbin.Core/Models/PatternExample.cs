namespace Fuzzbin.Core.Models;

/// <summary>
/// Example file naming pattern with description
/// </summary>
public class PatternExample
{
    /// <summary>
    /// The pattern string
    /// </summary>
    public string Pattern { get; set; } = string.Empty;

    /// <summary>
    /// Description of when to use this pattern
    /// </summary>
    public string Description { get; set; } = string.Empty;

    public PatternExample()
    {
    }

    public PatternExample(string pattern, string description)
    {
        Pattern = pattern;
        Description = description;
    }
}