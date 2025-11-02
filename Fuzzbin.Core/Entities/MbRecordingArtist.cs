using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Join table linking recordings to artists with credit information
/// </summary>
public class MbRecordingArtist
{
    public Guid RecordingId { get; set; }
    public Guid ArtistId { get; set; }
    
    /// <summary>
    /// Order of this artist in the credit (0-based)
    /// </summary>
    public int ArtistOrder { get; set; }
    
    /// <summary>
    /// Whether the join phrase indicates a featured artist (e.g., "feat.", "ft.")
    /// </summary>
    public bool IsJoinPhraseFeat { get; set; }
    
    // Navigation properties
    public virtual MbRecording Recording { get; set; } = null!;
    public virtual MbArtist Artist { get; set; } = null!;
}