using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a MusicBrainz release (specific album/single edition)
/// </summary>
public class MbRelease : BaseEntity
{
    /// <summary>
    /// MusicBrainz identifier (MBID) - stored as Guid
    /// </summary>
    public Guid Mbid { get; set; }
    
    /// <summary>
    /// Release title
    /// </summary>
    public string Title { get; set; } = string.Empty;
    
    /// <summary>
    /// Release date in YYYY-MM-DD format
    /// </summary>
    public string? ReleaseDate { get; set; }
    
    /// <summary>
    /// Country code (ISO 3166-1 alpha-2)
    /// </summary>
    public string? Country { get; set; }
    
    /// <summary>
    /// Barcode (UPC/EAN)
    /// </summary>
    public string? Barcode { get; set; }
    
    /// <summary>
    /// Number of tracks on this release
    /// </summary>
    public int? TrackCount { get; set; }
    
    /// <summary>
    /// Record label name
    /// </summary>
    public string? RecordLabel { get; set; }
    
    /// <summary>
    /// Last time this release was seen in a MusicBrainz response
    /// </summary>
    public DateTime LastSeenAt { get; set; }
    
    // Navigation properties
    public virtual ICollection<MbRecordingRelease> Recordings { get; set; } = new List<MbRecordingRelease>();
    public virtual ICollection<MbReleaseToGroup> ReleaseGroups { get; set; } = new List<MbReleaseToGroup>();
}