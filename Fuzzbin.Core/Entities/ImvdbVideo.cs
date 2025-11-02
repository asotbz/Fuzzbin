using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents an IMVDb music video entity
/// </summary>
public class ImvdbVideo : BaseEntity
{
    /// <summary>
    /// IMVDb numeric identifier
    /// </summary>
    public int ImvdbId { get; set; }
    
    /// <summary>
    /// Song title
    /// </summary>
    public string? SongTitle { get; set; }
    
    /// <summary>
    /// Video title (may differ from song title)
    /// </summary>
    public string? VideoTitle { get; set; }
    
    /// <summary>
    /// Release date in YYYY-MM-DD format
    /// </summary>
    public string? ReleaseDate { get; set; }
    
    /// <summary>
    /// Director credit information
    /// </summary>
    public string? DirectorCredit { get; set; }
    
    /// <summary>
    /// Whether this video has available sources (YouTube/Vimeo)
    /// </summary>
    public bool HasSources { get; set; }
    
    /// <summary>
    /// Last time this video was seen in an IMVDb response
    /// </summary>
    public DateTime LastSeenAt { get; set; }
    
    // Navigation properties
    public virtual ICollection<ImvdbVideoArtist> Artists { get; set; } = new List<ImvdbVideoArtist>();
    public virtual ICollection<ImvdbVideoSource> Sources { get; set; } = new List<ImvdbVideoSource>();
    public virtual ICollection<ImvdbVideoCandidate> Candidates { get; set; } = new List<ImvdbVideoCandidate>();
}