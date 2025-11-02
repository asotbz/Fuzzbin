using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a MusicBrainz recording (song) entity
/// </summary>
public class MbRecording : BaseEntity
{
    /// <summary>
    /// MusicBrainz identifier (MBID)
    /// </summary>
    public string Mbid { get; set; } = string.Empty;
    
    /// <summary>
    /// Recording title
    /// </summary>
    public string Title { get; set; } = string.Empty;
    
    /// <summary>
    /// Length in milliseconds
    /// </summary>
    public int? LengthMs { get; set; }
    
    /// <summary>
    /// Last time this recording was seen in a MusicBrainz response
    /// </summary>
    public DateTime LastSeenAt { get; set; }
    
    // Navigation properties
    public virtual ICollection<MbRecordingArtist> Artists { get; set; } = new List<MbRecordingArtist>();
    public virtual ICollection<MbRecordingRelease> Releases { get; set; } = new List<MbRecordingRelease>();
    public virtual ICollection<MbTag> Tags { get; set; } = new List<MbTag>();
    public virtual ICollection<MbRecordingCandidate> Candidates { get; set; } = new List<MbRecordingCandidate>();
}