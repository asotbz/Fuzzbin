using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents an IMVDb artist entity
/// </summary>
public class ImvdbArtist : BaseEntity
{
    /// <summary>
    /// IMVDb numeric identifier
    /// </summary>
    public int ImvdbId { get; set; }
    
    /// <summary>
    /// Artist name
    /// </summary>
    public string Name { get; set; } = string.Empty;
    
    /// <summary>
    /// Last time this artist was seen in an IMVDb response
    /// </summary>
    public DateTime LastSeenAt { get; set; }
    
    // Navigation properties
    public virtual ICollection<ImvdbVideoArtist> VideoArtists { get; set; } = new List<ImvdbVideoArtist>();
}