using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a MusicBrainz release group (album/single/EP grouping)
/// </summary>
public class MbReleaseGroup : BaseEntity
{
    /// <summary>
    /// MusicBrainz identifier (MBID) - stored as Guid
    /// </summary>
    public Guid Mbid { get; set; }
    
    /// <summary>
    /// Release group title
    /// </summary>
    public string Title { get; set; } = string.Empty;
    
    /// <summary>
    /// Primary type: Album, Single, EP, etc.
    /// </summary>
    public string? PrimaryType { get; set; }
    
    /// <summary>
    /// First release date in YYYY-MM-DD format (CRITICAL for year scoring)
    /// </summary>
    public string? FirstReleaseDate { get; set; }
    
    /// <summary>
    /// Last time this release group was seen in a MusicBrainz response
    /// </summary>
    public DateTime LastSeenAt { get; set; }
    
    // Navigation properties
    public virtual ICollection<MbReleaseToGroup> Releases { get; set; } = new List<MbReleaseToGroup>();
    public virtual ICollection<MbTag> Tags { get; set; } = new List<MbTag>();
}