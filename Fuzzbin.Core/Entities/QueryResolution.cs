using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents the final resolution of a query after candidate evaluation
/// </summary>
public class QueryResolution : BaseEntity
{
    public Guid QueryId { get; set; }
    
    /// <summary>
    /// Whether a music video exists for this query
    /// </summary>
    public bool MvExists { get; set; }
    
    /// <summary>
    /// Chosen source for the final resolution: 'imvdb', 'youtube', or 'none'
    /// </summary>
    public string ChosenSource { get; set; } = string.Empty;
    
    /// <summary>
    /// Reference to the MvLink if cross-references exist
    /// </summary>
    public Guid? MvLinkId { get; set; }
    
    /// <summary>
    /// When this resolution was determined
    /// </summary>
    public DateTime ResolvedAt { get; set; }
    
    // Navigation properties
    public virtual Query Query { get; set; } = null!;
    public virtual MvLink? MvLink { get; set; }
}