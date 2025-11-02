using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Tracks the last time each external source was checked for a query
/// </summary>
public class QuerySourceCache : BaseEntity
{
    public Guid QueryId { get; set; }
    
    /// <summary>
    /// Source identifier: 'musicbrainz', 'imvdb', 'youtube'
    /// </summary>
    public string Source { get; set; } = string.Empty;
    
    /// <summary>
    /// Last time this source was checked for this query
    /// </summary>
    public DateTime LastCheckedAt { get; set; }
    
    /// <summary>
    /// ETag from API response for conditional requests
    /// </summary>
    public string? ResultEtag { get; set; }
    
    /// <summary>
    /// HTTP status code from last request
    /// </summary>
    public int? HttpStatus { get; set; }
    
    /// <summary>
    /// Additional notes about the cache entry (e.g., error messages)
    /// </summary>
    public string? Notes { get; set; }
    
    // Navigation properties
    public virtual Query Query { get; set; } = null!;
}