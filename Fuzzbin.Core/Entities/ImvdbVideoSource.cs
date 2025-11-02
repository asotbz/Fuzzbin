using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a video source (YouTube/Vimeo) for an IMVDb video
/// </summary>
public class ImvdbVideoSource : BaseEntity
{
    public Guid VideoId { get; set; }
    
    /// <summary>
    /// Source platform: 'youtube' or 'vimeo'
    /// </summary>
    public string Source { get; set; } = string.Empty;
    
    /// <summary>
    /// External video ID on the source platform
    /// </summary>
    public string ExternalId { get; set; } = string.Empty;
    
    /// <summary>
    /// Whether this is marked as an official video source
    /// </summary>
    public bool IsOfficial { get; set; }
    
    // Navigation properties
    public virtual ImvdbVideo Video { get; set; } = null!;
}