using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a normalized metadata query for caching purposes
/// </summary>
public class Query : BaseEntity
{
    /// <summary>
    /// Raw (unnormalized) title from user input
    /// </summary>
    public string RawTitle { get; set; } = string.Empty;
    
    /// <summary>
    /// Raw (unnormalized) artist from user input
    /// </summary>
    public string RawArtist { get; set; } = string.Empty;
    
    /// <summary>
    /// Normalized title for matching
    /// </summary>
    public string NormTitle { get; set; } = string.Empty;
    
    /// <summary>
    /// Normalized artist for matching
    /// </summary>
    public string NormArtist { get; set; } = string.Empty;
    
    /// <summary>
    /// Combined normalized key for unique index (format: "{NormArtist}||{NormTitle}")
    /// </summary>
    public string NormComboKey { get; set; } = string.Empty;
    
    // Navigation properties
    public virtual ICollection<QuerySourceCache> SourceCaches { get; set; } = new List<QuerySourceCache>();
    public virtual QueryResolution? Resolution { get; set; }
}