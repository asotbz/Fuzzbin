using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Join table linking recordings to releases with track information
/// </summary>
public class MbRecordingRelease : BaseEntity
{
    public Guid RecordingId { get; set; }
    public Guid ReleaseId { get; set; }
    
    /// <summary>
    /// Track number on the release
    /// </summary>
    public int? TrackNumber { get; set; }
    
    /// <summary>
    /// Disc number for multi-disc releases
    /// </summary>
    public int? DiscNumber { get; set; }
    
    // Navigation properties
    public virtual MbRecording Recording { get; set; } = null!;
    public virtual MbRelease Release { get; set; } = null!;
}