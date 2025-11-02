using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents cross-references between metadata sources (IMVDb, MusicBrainz, YouTube)
/// </summary>
public class MvLink : BaseEntity
{
    /// <summary>
    /// Reference to IMVDb video (optional)
    /// </summary>
    public Guid? ImvdbVideoId { get; set; }
    
    /// <summary>
    /// Reference to MusicBrainz recording (optional)
    /// </summary>
    public Guid? MbRecordingId { get; set; }
    
    /// <summary>
    /// Reference to YouTube video (optional)
    /// </summary>
    public string? YtVideoId { get; set; }
    
    /// <summary>
    /// Type of link: 'imvdb_to_mb', 'imvdb_to_yt', 'mb_to_yt', 'triad'
    /// </summary>
    public string LinkType { get; set; } = string.Empty;
    
    /// <summary>
    /// Confidence score for this link (0.0-1.0)
    /// </summary>
    public double Confidence { get; set; }
    
    /// <summary>
    /// Additional notes about the link
    /// </summary>
    public string? Notes { get; set; }
    
    // Navigation properties
    public virtual ImvdbVideo? ImvdbVideo { get; set; }
    public virtual MbRecording? MbRecording { get; set; }
    public virtual YtVideo? YtVideo { get; set; }
}