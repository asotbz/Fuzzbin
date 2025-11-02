using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a MusicBrainz artist entity
/// </summary>
public class MbArtist : BaseEntity
{
    /// <summary>
    /// MusicBrainz identifier (MBID)
    /// </summary>
    public string Mbid { get; set; } = string.Empty;
    
    /// <summary>
    /// Artist name
    /// </summary>
    public string Name { get; set; } = string.Empty;
    
    /// <summary>
    /// Sort name (e.g., "Beatles, The")
    /// </summary>
    public string? SortName { get; set; }
    
    /// <summary>
    /// Disambiguation text to differentiate similar artists
    /// </summary>
    public string? Disambiguation { get; set; }
    
    /// <summary>
    /// Country code (ISO 3166-1 alpha-2)
    /// </summary>
    public string? Country { get; set; }
    
    /// <summary>
    /// Last time this artist was seen in a MusicBrainz response
    /// </summary>
    public DateTime LastSeenAt { get; set; }
    
    // Navigation properties
    public virtual ICollection<MbRecordingArtist> RecordingArtists { get; set; } = new List<MbRecordingArtist>();
}